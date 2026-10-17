# 轉播左上角的物件計時框（2026 世界賽版面，畫面 1920x1080）：
#   一格是上方野怪坑的「下一隻」（三蟲 grubs／預示者 herald／巴龍 baron），一格是「下一條龍」（6 種元素或遠古 elder），
#   各附重生倒數；倒數不見代表已出現在場上。格子寬度隨有無倒數而變，龍的圖示可能在 x=12／62／122，三處都判讀。
# 圖示模板（assets/objective_icons.npz）：Day 1、Day 2 全畫面的圖示 k-means 分群後由人工目視標定（不是用 feed 訓練）。
# 用法：python tools/objective_box.py validate <RUN> [...]   → 以 feed 的龍事件驗證「下一條龍」
import sys, os, glob, json, csv, datetime as dt
import numpy as np, cv2
SLOTS = {"A": (12, 52, 12, 50), "M": (12, 52, 62, 100), "B": (12, 52, 122, 160)}   # 上方那格有倒數時龍在 x=122，沒倒數（野怪在場上）時在 x=62；上方那格不存在時龍在 x=12
PIT = {"grubs", "herald", "baron"}
DRAGON = {"infernal", "ocean", "mountain", "cloud", "hextech", "chemtech", "elder"}
TPL_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "objective_icons.npz")
_T = dict(np.load(TPL_PATH)) if os.path.exists(TPL_PATH) else {}
MIN_SCORE = 0.7

def feat(c):
    c = cv2.resize(c, (24, 24), interpolation=cv2.INTER_AREA).astype(np.float32); c -= c.mean(axis=(0, 1)); return (c / (np.linalg.norm(c) + 1e-6)).ravel()

def read(img, x_off=0, y_off=0):
    """img：全畫面或至少含左上角 (0..70, 0..300) 的裁切。回傳 {"pit": 名稱|None, "dragon": 名稱|None, "scores": {...}}。"""
    out = {"pit": None, "dragon": None, "scores": {}}
    for s, (y0, y1, x0, x1) in SLOTS.items():
        c = img[y0 + y_off:y1 + y_off, x0 + x_off:x1 + x_off]
        if c.size == 0: continue
        f = feat(c); sc, name = max((float(v @ f), k) for k, v in _T.items())
        out["scores"][s] = (name, round(sc, 2))
        if sc < MIN_SCORE: continue
        if name in PIT and out["pit"] is None: out["pit"] = name
        if name in DRAGON and out["dragon"] is None: out["dragon"] = name
    return out

def read_grubs(img, x_off=0, y_off=0):
    """計分列第二排兩端「⬡ 數字」＝各隊已拿的三蟲數（Day 2：15 分鐘後不再變，預示者不計入）。
    img 為全畫面時 x_off=0；為 hud_<RUN>_*.png（全畫面 x 500–1420 的裁切）時 x_off=-500。數字只可能 0–3。
    回傳 {"B": n|None, "R": n|None}。"""
    sys.path.insert(0, os.path.dirname(__file__)); import hud_clock as HC
    T = np.load(HC.TPL)["t"][:4]                                   # 三蟲整局只有 3 隻，數字只可能 0–3（避開模板 0↔6、0↔8 混淆）
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32); out = {}
    for side, (x0, x1) in (("B", (741, 753)), ("R", (1165, 1177))):        # 全畫面座標
        best = (None, -9.0)
        for dy in (-2, -1, 0, 1, 2):
            for dx in (-2, -1, 0, 1, 2):
                c = g[79 + dy + y_off:100 + dy + y_off, x0 + dx + x_off:x1 + dx + x_off]
                if c.shape != (21, 12): continue
                s = (T * HC._norm(c)).sum(axis=(1, 2)); k = int(s.argmax())
                if s[k] > best[1]: best = (k, float(s[k]))
        out[side] = best[0] if best[1] >= 0.6 else None
    return out

if __name__ == "__main__" and sys.argv[1] == "validate":
    sys.stdout.reconfigure(encoding="utf-8")
    D = "data/live_worlds2026"; ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    tot = ok = 0; conf = {}
    for RUN in sys.argv[2:]:
        rows = list(csv.DictReader(open(f"{D}/clf_live_{RUN}.csv", encoding="utf-8")))
        anchor = float(np.median([ts(r["wall_utc"]) - int(r["n"]) for r in rows])); lay = {int(r["n"]): r["layout"] for r in rows}
        w0, w1 = int(rows[0]["n"]) + anchor, int(rows[-1]["n"]) + anchor
        for fp in sorted(glob.glob(f"{D}/feed_*.jsonl")):
            r = [json.loads(l) for l in open(fp, encoding="utf-8")]; ig = [x for x in r if x["state"] == "in_game"]
            if not ig: continue
            st0, end = ts(ig[0]["ts"]), ts(r[-1]["ts"])
            if not (w0 <= st0 <= w1): continue
            LAG = 46.0 if RUN >= "1016T1" else 31.0
            kills = []; prev = None
            for x in r:
                if prev:
                    for sd in "BR":
                        for i in range(len(prev[sd]["d"]), len(x[sd]["d"])): kills.append((ts(x["ts"]) + LAG, x[sd]["d"][i]))
                prev = x
            for p in sorted(glob.glob(f"{D}/snap/full_{RUN}_*.jpg")):
                n = int(p[-11:-4]); w = n + anchor
                if not (st0 + LAG + 60 <= w <= end + LAG - 20) or lay.get(n) != "1": continue
                if any(abs(t - w) < 20 for t, _ in kills): continue          # 剛拿龍的前後 20 秒不算（框在換圖）
                truth = next((e for t, e in kills if t > w), None)
                if truth is None: continue                                   # 比賽結束前沒人再拿龍：無正解
                pred = read(cv2.imread(p))["dragon"]
                tot += 1; ok += pred == truth; conf[(truth, pred)] = conf.get((truth, pred), 0) + 1
    print(f"下一條龍：{ok}/{tot} 正確（{ok / max(1, tot) * 100:.1f}%）")
    for (t, p), c in sorted(conf.items(), key=lambda x: -x[1]):
        if t != p: print("  錯：正解", t, "判讀", p, "×", c)
