# Stream CV 服務輸出合約（v0，2026-10-16）

桌面工具（DesktopLOL）讀這份資料。服務由 `tools/live_service.py` 產生，每 5 秒更新一次。

- HTTP：`GET http://127.0.0.1:8787/state.json`（日後上 VPS 改成對外網址；欄位不變）
- 檔案：`data/live_worlds2026/state.json`（目前狀態）、`data/live_worlds2026/events.jsonl`（新事件逐行附加）
- 範例：`docs/samples/state_finished_game.json`（Worlds 2026 Play-In，MVK vs FUR 第 3 局結束時的真實輸出）

## 慣例

- 隊伍一律用 `B`（藍方，小地圖左下）與 `R`（紅方，小地圖右上），不是戰隊名。戰隊名與 logo 由桌面工具從官方 API 取得。
- 遊戲時間：`gameTime` / `spawnAt` / `until` 等字串為 `M:SS`；同名的 `sec` 為秒數，方便排序與倒數。
- `status`：`idle`（無進行中的小局）、`waiting`、`in_game`、`finished`。`idle` 時只有 `status` 與 `updated`。
- 資料來源標示：龍、巴龍、水晶、擊殺、金錢來自官方 feed（準確）；「哪一座塔」來自畫面辨識（CV）；計時欄位是依規則表推算。

## 欄位

| 欄位 | 型別 | 來源 | 說明 |
| --- | --- | --- | --- |
| `game` | string | feed | 官方小局 ID |
| `updated` | ISO 時間 | 服務 | 本次更新時間 |
| `gameClock` | `M:SS` | feed＋計分列時鐘 | 目前遊戲時間 |
| `clockSource` | string | 服務 | 時間換算依據（計分列時鐘或 feed 時間戳） |
| `videoLagSec` / `measuredLagSec` | number | 服務 | 直播畫面落後 feed 的秒數（設定值／實測值） |
| `dragons.B` / `dragons.R` | string[] | feed | 依序拿到的龍屬性：`infernal` `ocean` `mountain` `cloud` `hextech` `chemtech` `elder` |
| `riftElement` | string \| null | feed | 地圖屬性（第三條龍起固定）；第三條龍被拿之前為 null |
| `soul` | `{team, element}` \| null | feed | 龍魂 |
| `elderKills` | `{B, R}` | feed | 遠古龍次數 |
| `barons` / `inhibitors` / `kills` / `gold` | `{B, R}` | feed | 累計（`inhibitors` 為該隊**打掉**的水晶數） |
| `towersDestroyedBy` | `{B, R}` | feed | 該隊**打掉**的塔數（含重生後再打掉的主堡塔） |
| `towersLost.B` / `towersLost.R` | `{site, gameTime, sec}[]` | CV | 該隊**失去**的塔是哪幾座；`site` 見下 |
| `towersLost.nexusTurretsDown` | `{teamLost, site, respawnAt}[]` | CV＋規則 | 已倒的主堡塔與重生時間（3 分鐘） |
| `towersLost.nexusRespawnsSeen` | 陣列 | CV | 畫面確認的主堡塔重生 |
| `timers.nextDragon` | `{kind, element, elementNote, spawnAt, sec}` | 規則 | `kind`=`elemental`/`elder`；`element` 不確定時為 null，原因在 `elementNote` |
| `timers.nextBaron` | `{spawnAt, sec}` | 規則 | |
| `timers.activeBuffs` | `{buff, team, until, untilSec}[]` | 規則 | `buff`=`baron`（180 秒）/`elder`（150 秒） |
| `timers.inhibitorsDown` | `{teamLost, respawnAt}[]` | 規則 | 水晶 5 分鐘重生 |
| `timers.grubsWindow` / `heraldWindow` | string | 規則 | 三蟲 8:00–14:45、預示者 15:00–19:45（被誰拿：尚未支援） |
| `events` | 陣列 | feed | `{type: dragon/baron/inhibitor/tower, team, element?, sec, gameTime}`，`team` 為**取得者** |

## 系列賽與 BP（v0.1，2026-10-16 加入；依 DesktopLOL `docs/CONTRACT_PROPOSAL.md`）

`series` 與 `draft` 在 `in_game`、`finished`、`waiting` 時都會附上（服務需有 `LOL_API_KEY` 環境變數；沒有時兩欄不出現）。
BP 中或局與局之間（沒有進行中的小局、但系列賽仍在直播）時 `status` 為 `waiting`，此時只有 `status`、`updated`、`series`、`draft`。

| 欄位 | 型別 | 來源 | 說明 |
| --- | --- | --- | --- |
| `series.bestOf` | number | esports-api getEventDetails（`strategy.count`） | 1/3/5 |
| `series.game` | number | 同上 | 本局是第幾局 |
| `series.matchId` | string | 同上 | 官方系列賽 ID（提案外新增） |
| `series.sidesSource` | string | 服務（v0.4） | 藍紅方的依據。`api`：開打後的官方資料。`broadcast`：BP 中由畫面中央隊伍 logo 判斷（Day 1+2 共 1295 張 BP 畫面全對）。`api_unconfirmed`：BP 中但畫面判斷不出來，此時藍紅方**可能是錯的**（官方 API 開打前常顛倒，Day 2 七局中五局）。**服務收到該局第一個 feed 幀之後一律是 `api`**；開打後到 feed 記錄器開始記錄之前的短暫空窗（通常數十秒），仍可能出現 `api_unconfirmed` |
| `series.teams.B` / `.R` | `{code, wins}` | 同上（每局的 `side`） | **這一局**誰在藍方、誰在紅方（會換邊）。`wins` = 本局開始前的勝場 |
| `series.winsNote` | string（可無） | 服務 | 服務沒在本局開始前看到系列賽時出現，此時 `wins` 為 null |
| `draft.current` | `{game, B, R, turn}` | | 本局 |
| `draft.current.B.picks` | string[5] | feed `gameMetadata`（免金鑰） | Data Dragon 英雄 ID（已驗證：8 局 60 個 ID 全部對得上 16.20.1，例：`KSante` `MonkeyKing` `Velkoz`）。**開局後才有**；BP 中為 5 個 null |
| `draft.current.B.bans` | (string\|null)[5] | 畫面辨識（v0.3） | 依禁用順序（第 1–5 手）；Data Dragon 英雄 ID。**開局後**：BP 列最後 3 張畫面、10 格一對一指派（Day 1 共 8 局 80/80 對照 Leaguepedia，其中規則凍結後的盲測 40/40）。**BP 進行中**：只回報連續 3 張（約 9 秒）穩定的格子，其餘 null（此模式尚未驗證）。服務沒有該局的 BP 畫面時為 5 個 null |
| `draft.current.turn` | null | — | **尚未支援**：BP 進行中的下一手需要畫面辨識。目前一律 null |
| `draft.earlier` | `{game, B, R}[]` | feed `gameMetadata` | 同系列已結束的局（全局 BP 鎖定名單由此而來）；各局的 B/R 是**那一局**的藍紅方 |
| `draft.picksOrder` | `"role"` | 服務 | **與提案不同**：picks 的順序是位置（上、野、中、下、輔），不是 BP 順序。feed 只給位置，不給選角順序 |
| `draft.bansSupported` / `turnSupported` | boolean | 服務 | v0.3 起 `bansSupported` 為 true；`turnSupported` 仍為 false |
| `draft.bansOrder` | `"ban"` | 服務 | v0.3 新增：bans 依禁用順序排列（藍紅兩方各自的第 1–5 手） |

## 選手（v0.2，2026-10-16 加入；依 DesktopLOL `docs/CONTRACT_PROPOSAL.md`「選手」一節）

`players` 在 `in_game`、`finished` 時附上（免金鑰）。`players.B` / `players.R` 各 5 人，順序為 participantId（實際上就是上、野、中、下、輔）。

| 欄位 | 型別 | 來源 | 說明 |
| --- | --- | --- | --- |
| `players.asOf` | ISO 時間 | feed | 這份數據對應的 feed 幀時間（約比 feed 最新幀晚 0–10 秒；feed 本身又比直播畫面快約 30 秒） |
| `role` | string | window `gameMetadata` | `top` `jungle` `mid` `bottom` `support`（原樣） |
| `name` | string | 同上 `summonerName` | 原樣，含隊伍代碼前綴（例 `MVK Kratos`） |
| `champion` | string | 同上 `championId` | Data Dragon ID |
| `level` `kills` `deaths` `assists` | number | window 幀 `participants` | |
| `cs` | number | 同上 `creepScore` | |
| `gold` | number | 同上 `totalGold` | |
| `hp` / `maxHp` | number | 同上 `currentHealth` / `maxHealth` | 陣亡時 `hp` 為 0 |
| `items` | number[] \| null | details 幀 `participants[].items` | Data Dragon 裝備 ID，含飾品與藥水；details 取不到時為 null |

已驗證：8 局 participantId 皆為藍方 1–5、紅方 6–10；window 與 details 每秒約 5 幀、時間戳一致；樣本局各隊 5 人擊殺加總等於隊伍擊殺數。

## 轉播畫面物件（v0.4，2026-10-17 加入）

來源是轉播畫面左上角的物件計時框，以及計分列兩端的三蟲數（`tools/objective_box.py`）。只在 `in_game`、`finished` 時出現；畫面資料不足時欄位不出現。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `timers.nextDragon.element` | string \| null | 下一條龍屬性。v0.4 起優先取轉播計時框（`elementSource: "broadcast"`），讀不到時退回規則推算（`"rules"`）。轉播顯示遠古時 `kind` 改為 `"elder"` |
| `timers.nextDragon.elementSource` | `"broadcast"` \| `"rules"` | 屬性來源 |
| `voidgrubs` | `{B: n\|null, R: n\|null}` | 兩隊已拿的三蟲數（0–3）。Day 2 七局皆從 0/0 開始、最後兩隊合計 3 |
| `pitNext` | `"grubs"` \| `"herald"` \| `"baron"` \| null | 上方野怪坑的下一隻（計時框上方那格） |
| `herald.status` | string | `upcoming`（尚未出現）、`alive_or_upcoming`、`taken`（19:40 前被打掉）、`taken_or_despawned`（19:40 後才換圖，可能是消失） |
| `herald.at` / `herald.sec` | `M:SS` / number | 預示者被打掉的時間（計時框換圖前後兩次讀值的中點；畫面每 5 秒一張，誤差約 ±5 秒） |
| `herald.team` | "B" / "R" / null | v0.5：預示者歸屬，來自畫面上方公告「Blue/Red team has defeated（或 summoned）the Rift Herald!」（此時 `herald.teamSource` 為 "announcement"）。Day 1+2 共 12 局留一局驗證 12/12（對照 Leaguepedia）。沒看到公告時為 null。1080p 直播畫面目前只以 1 局驗證 |

驗證（Day 1、Day 2 共 9 局）：下一條龍屬性 161/170 張畫面正確，其餘 9 張讀不到（多為重播字卡蓋住），沒有讀成錯誤屬性。模板由人工目視分群標定，答案取自 feed 的龍事件；但測試畫面與建模板的畫面是同一批，真正的盲測待 Day 3。

## 賽程與歷史（v0.6，2026-10-17 加入）

另開的端點，給「沒有比賽時」用。都是 GET、回 JSON。

| 端點 | 內容 |
| --- | --- |
| `/schedule.json` | Worlds 2026 全賽程（官方 getSchedule，5 分鐘快取）。`matches[]`：`matchId`、`start`（UTC）、`state`（`unstarted`／`inProgress`／`completed`）、`stage`（Play-Ins／Swiss／Quarterfinals／Semifinals／Finals）、`bestOf`、`teams[]`（`code`、`name`、`image`；未定為 `TBD`）、**`result`**（`{wins: [n, n], winner}`，未開打為 null）。**不爆雷：整個 `result` 不顯示即可**，其他欄位不含比分 |
| `/schedule.json` 的 `teamsSpoiler` | 每場一個值：`true` 表示該場的對戰組合本身會洩露先前比賽結果（來自官方 getStandings 的 `flags.isSpoiler`，lolesports 官網的防雷依據）；`false` 表示預先排好的組合，或隊伍仍是 TBD；`null` 表示該場不在 getStandings 裡，或 getStandings 抓取失敗。TBD 場次目前為 `false`，隊伍確定後由官方重新標記，服務每 5 分鐘更新。**維護者 2026-10-17 決定不爆雷只藏比分，此欄位僅供參考，桌面工具不使用** |
| `/history/games.json` | 已結束小局的索引：`gameId`、`matchId`、`stage`、`game`、`bestOf`、`start`、`duration`、`teams`（`{B, R}` 代碼）、`winner`（`"B"`／`"R"`）|
| `/history/game/<gameId>.json` | 單局回顧：上列欄位＋`bans`、`players`（同 `state.json` 的 players，最終值）、`final`（兩隊擊殺、金錢、打掉的塔／水晶、巴龍、龍）、`voidgrubs`、`heralds`、`towersLost`（哪幾座塔，畫面辨識）、`goldDiffPerMin`（`[[分鐘, 藍−紅金錢], …]`）、`sources`（每個欄位的來源） |
| `/history/teams.json` | `teams.<代碼>[]`：每局的 `side`、`opponent`、`win`、`bans`、`picks[]`（`role`、`player`、`champion`）|
| `/history/players.json` | `players.<選手名>`：`team`、`role`、`games[]`（`champion`、`win`、`k`、`d`、`a`）、`pool.<英雄>`（`games`、`wins`、`k`、`d`、`a`）|

資料來源與驗證：
- 勝方：Leaguepedia；限流抓不到時用本服務的塔命名（主堡塔被打掉的一方輸），`sources.winner = "cv_nexus"`。Play-In 4 個系列賽 15 局推算的勝負，加總與官方系列賽比分全部一致。
- 禁用：本服務直播當下的辨識（`cv`）＞錄影版畫面辨識（`cv_vod`，Day 1 共 80/80）＞ Leaguepedia。
- 每局結束約 2 分鐘後，服務自動重建歷史資料；範圍只含本服務有記錄 feed 的小局（Worlds 2026 Play-In 起）。
- **比分會出現在 `/history/*` 的 `winner`、`win`、`final`、`goldDiffPerMin`**：不爆雷模式下，這些也要藏起來。

`site` 值：`top_outer` `top_inner` `top_inhib_tower` `mid_outer` `mid_inner` `mid_inhib_tower` `bot_outer` `bot_inner` `bot_inhib_tower` `nexus_t1` `nexus_t2`。

## 已知限制（v0）

- 塔的命名平均比畫面晚約 7 秒（需累積 8 秒的消失證據）；被英雄頭像遮住時會更晚。比賽結束時的最後幾座可能是由 feed 數量推算補上。
- 三蟲、預示者由誰取得、紅藍 buff 尚未支援（評估中）。
- 欄位可能在 v1 增加，但 v0 既有欄位的意義不變。
