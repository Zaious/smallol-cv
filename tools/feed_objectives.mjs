// 官方 feed 目標計數（每分鐘取一個窗口）：塔、龍、大龍。用來當小地圖判讀的驗收。
const G = process.argv[2];
const start = Date.parse(process.argv[3]);
const minutes = Number(process.argv[4] || 30);
for (let m = 0; m <= minutes; m++) {
  const ts = new Date(start + m * 60000).toISOString().replace(/\.\d+Z$/, "Z");
  const res = await fetch(`https://feed.lolesports.com/livestats/v1/window/${G}?startingTime=${ts}`);
  const d = await res.json();
  if (!d.frames) { console.log(`${m}min ${ts} no-frames`); continue; }
  const l = d.frames[d.frames.length - 1];
  console.log(`${m}min ${ts} blueTowers=${l.blueTeam.towers} blueDragons=${l.blueTeam.dragons.join("/")} blueBaron=${l.blueTeam.barons} | redTowers=${l.redTeam.towers} redDragons=${l.redTeam.dragons.join("/")} redBaron=${l.redTeam.barons}`);
}
