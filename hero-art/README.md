# hero-art（不在 repo 裡）

英雄原畫是 Riot Games 的素材，不放進這個 repo。要跑選角辨識（`tools/draft_picks.py`）時，自己下載到這個資料夾：

```bash
python tools/fetch_ddragon_splash.py          # 版本預設 16.20.1，只用來取英雄清單
```

會產生：

| 位置 | 內容 | 從哪來 |
| --- | --- | --- |
| `hero-art/splash/<英雄>_0.jpg` | 每隻英雄的預設原畫（約 170 張） | Riot Data Dragon |
| `hero-art/cards/*.png` | 原畫比對不出來的選角卡（目前只有 Ornn） | `tools/draft_cards_build.py` 從自己錄的轉播畫面裁出來 |

沒有這個資料夾時，服務照常跑，只是 BP 進行中讀不到選角（官方 feed 在開打後仍會給最終選角）。

---

Champion splash art belongs to Riot Games and is not in this repo. Download it with `python tools/fetch_ddragon_splash.py` before running the draft reader; `hero-art/cards/` is built from your own broadcast captures by `tools/draft_cards_build.py`. Without it the service still runs, but picks are not read during the draft.
