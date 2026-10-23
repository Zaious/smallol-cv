// 無人值守的官方 feed 記錄：每 30 秒問 getLive 找進行中的小局，對每個進行中的小局輪詢 livestats window，
// 把每幀的塔／水晶／龍／男爵計數寫成 JSONL（含本機牆鐘時間）。金鑰只讀環境變數 LOL_API_KEY，不寫進任何檔案。
// 用法：LOL_API_KEY=... node tools/live_feed_log.mjs <out_dir>
import fs from "node:fs";
import { spawn } from "node:child_process";
const OUT = process.argv[2]; fs.mkdirSync(OUT, { recursive: true });
const KEY = process.env.LOL_API_KEY; if (!KEY) { console.error("缺 LOL_API_KEY"); process.exit(1); }
const log = (m) => { const l = `${new Date().toISOString()} ${m}`; console.log(l); fs.appendFileSync(`${OUT}/feed.log`, l + "\n"); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const seen = new Map();   // gameId -> 最後寫入的 rfc460Timestamp
const polling = new Set();
const backfilled = new Set();
const done = new Set();     // 已結束的小局：getLive 結束後仍會列出一陣子，不再重複追蹤
// 連線卡住：Node 的 fetch 一旦連續失敗就一直失敗，重開行程才恢復（2026-10-19 Day 4：半小時沒有 feed，手動重啟後才接上）。
// FEED_EXIT_ON_STUCK=1（outpost_run.py 設）時，連續失敗這麼多次就結束，讓外層 10 秒後重開一個新的。
const STUCK_AFTER = 6;
let failsInARow = 0;
const failed = (what, e) => {
  log(`${what} 例外 ${e}`);
  if (++failsInARow >= STUCK_AFTER && process.env.FEED_EXIT_ON_STUCK === "1") { log(`連續失敗 ${failsInARow} 次，結束行程讓外層重開`); process.exit(3); }
};

async function getLive() {
  const r = await fetch("https://esports-api.lolesports.com/persisted/gw/getLive?hl=en-US", { headers: { "x-api-key": KEY } });
  if (!r.ok) throw new Error(`getLive HTTP ${r.status}`);
  const d = await r.json(); const games = [];
  // 只追指定聯賽（預設 Worlds）：getLive 也會列出其他賽事，例如 2026-10-17 的 Demacia Cup（DCGI）
  const LEAGUE = process.env.WATCH_LEAGUE ?? "Worlds";
  for (const e of d?.data?.schedule?.events ?? []) if (!LEAGUE || e.league?.name === LEAGUE) for (const g of e.match?.games ?? e.games ?? []) if (g.state === "inProgress") games.push({ id: g.id, league: e.league?.name, match: e.match?.id });
  return games;
}

async function pollGame(g) {
  polling.add(g.id); log(`開始追蹤 game ${g.id} (${g.league}) match ${g.match}`);
  let idle = 0;
  while (idle < 40) {                                     // 連續 40 次沒有新幀（約 7 分鐘）就當作結束
    const t = Math.floor((Date.now() - 60000) / 10000) * 10000;   // feed 拒絕結束時間不到 50 秒前的窗（2026-10-24 起回 400）：往前 60 秒、對齊 10 秒
    const ts = new Date(t).toISOString().replace(/\.\d+Z$/, "Z");
    try {
      const r = await fetch(`https://feed.lolesports.com/livestats/v1/window/${g.id}?startingTime=${ts}`);
      failsInARow = 0;
      if (r.status === 200) {
        const d = await r.json(); let wrote = 0; const wall = new Date().toISOString();
        for (const f of d.frames ?? []) {
          if ((seen.get(g.id) ?? "") >= f.rfc460Timestamp) continue;
          seen.set(g.id, f.rfc460Timestamp); wrote++;
          const row = { wall, game: g.id, ts: f.rfc460Timestamp, state: f.gameState,
            B: { t: f.blueTeam.towers, i: f.blueTeam.inhibitors, b: f.blueTeam.barons, d: f.blueTeam.dragons, k: f.blueTeam.totalKills, g: f.blueTeam.totalGold },
            R: { t: f.redTeam.towers, i: f.redTeam.inhibitors, b: f.redTeam.barons, d: f.redTeam.dragons, k: f.redTeam.totalKills, g: f.redTeam.totalGold } };
          fs.appendFileSync(`${OUT}/feed_${g.id}.jsonl`, JSON.stringify(row) + "\n");
        }
        if (wrote && !backfilled.has(g.id)) {             // 第一次寫入本局：補抓開局到現在漏掉的幀（晚開始追蹤時，Day 2 第 3、5 局）
          backfilled.add(g.id);
          spawn("python", [new URL("./feed_backfill.py", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"), OUT, g.id], { stdio: "ignore", detached: true }).unref();
          log(`補抓 game ${g.id} 開局片段`);
        }
        idle = wrote ? 0 : idle + 1;
        if (d.frames?.some((f) => f.gameState === "finished")) { log(`game ${g.id} finished`); done.add(g.id); break; }
      } else idle++;
    } catch (e) { failed("window", e); idle++; }
    await sleep(10000);
  }
  polling.delete(g.id); log(`停止追蹤 game ${g.id}`);
}

log("feed 記錄啟動");
while (true) {
  try {
    const games = await getLive();
    failsInARow = 0;
    for (const g of games) if (!polling.has(g.id) && !done.has(g.id)) pollGame(g);
  } catch (e) { failed("getLive", e); }
  await sleep(30000);
}
