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
| `series.teams.B` / `.R` | `{code, wins}` | 同上（每局的 `side`） | **這一局**誰在藍方、誰在紅方（會換邊）。`wins` = 本局開始前的勝場 |
| `series.winsNote` | string（可無） | 服務 | 服務沒在本局開始前看到系列賽時出現，此時 `wins` 為 null |
| `draft.current` | `{game, B, R, turn}` | | 本局 |
| `draft.current.B.picks` | string[5] | feed `gameMetadata`（免金鑰） | Data Dragon 英雄 ID（已驗證：8 局 60 個 ID 全部對得上 16.20.1，例：`KSante` `MonkeyKing` `Velkoz`）。**開局後才有**；BP 中為 5 個 null |
| `draft.current.B.bans` | (string\|null)[5] | — | **尚未支援**：feed 沒有禁用（搜尋 0 命中），畫面辨識還沒做。目前一律 5 個 null |
| `draft.current.turn` | null | — | **尚未支援**：BP 進行中的下一手需要畫面辨識。目前一律 null |
| `draft.earlier` | `{game, B, R}[]` | feed `gameMetadata` | 同系列已結束的局（全局 BP 鎖定名單由此而來）；各局的 B/R 是**那一局**的藍紅方 |
| `draft.picksOrder` | `"role"` | 服務 | **與提案不同**：picks 的順序是位置（上、野、中、下、輔），不是 BP 順序。feed 只給位置，不給選角順序 |
| `draft.bansSupported` / `turnSupported` | boolean | 服務 | 目前皆為 false；支援後改為 true |

`site` 值：`top_outer` `top_inner` `top_inhib_tower` `mid_outer` `mid_inner` `mid_inhib_tower` `bot_outer` `bot_inner` `bot_inhib_tower` `nexus_t1` `nexus_t2`。

## 已知限制（v0）

- 塔的命名平均比畫面晚約 7 秒（需累積 8 秒的消失證據）；被英雄頭像遮住時會更晚。比賽結束時的最後幾座可能是由 feed 數量推算補上。
- 三蟲、預示者由誰取得、紅藍 buff 尚未支援（評估中）。
- 欄位可能在 v1 增加，但 v0 既有欄位的意義不變。
