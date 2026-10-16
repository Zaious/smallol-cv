// 以 10 秒窗口掃整局 feed，找出每隊 towers／inhibitors／barons／dragons 計數增加的確切幀時間。
// 用法：node tools/feed_tower_events.mjs <gameId> <startISO(10秒對齊)> <分鐘數>
const [G, startISO, mins] = process.argv.slice(2);
let t = Date.parse(startISO);
const end = t + Number(mins) * 60000;
let prev = null;
const events = [];
while (t < end) {
  const ts = new Date(t).toISOString().replace(/\.\d+Z$/, "Z");
  const res = await fetch(`https://feed.lolesports.com/livestats/v1/window/${G}?startingTime=${ts}`);
  const d = await res.json();
  if (d.frames) {
    for (const f of d.frames) {
      const cur = {
        B_towers: f.blueTeam.towers, R_towers: f.redTeam.towers,
        B_inhib: f.blueTeam.inhibitors, R_inhib: f.redTeam.inhibitors,
        B_baron: f.blueTeam.barons, R_baron: f.redTeam.barons,
        B_dragons: f.blueTeam.dragons.length, R_dragons: f.redTeam.dragons.length,
      };
      if (prev) for (const k of Object.keys(cur)) if (cur[k] > prev[k]) events.push({ time: f.rfc460Timestamp, key: k, from: prev[k], to: cur[k] });
      prev = cur;
    }
  }
  t += 10000;
}
for (const e of events) console.log(`${e.time} ${e.key} ${e.from}->${e.to}`);
console.log("events", events.length);
