# BP 進行中的即時選角：轉播 BP 介面最下面一排選手卡（左 5 藍、右 5 紅，每張 160 px 寬），選到英雄後卡上顯示該英雄原畫（經典造型）。
# 1. BP 介面在不在畫面上：中央面板上下兩段（HYPERX／BLUE SIDE／1ST PICK 標籤、PATCH 字樣）比對中位數模板（Day 3：BP 中 ≥ 0.9、其他 < 0.2）。
# 2. 哪隻英雄：卡片裁切以臉為中心、每隻縮放不同，所以用 SIFT 特徵點比對 Data Dragon 原畫（hero-art/splash/，不進 repo），
#    RANSAC 相似變換的內點數最多者；內點 < MIN_INL 視為空格。
#    第二階段（經典誤判的進階判讀）：轉播有些英雄的卡片用的是別隻英雄的原畫（Rakan 的卡是 Xayah 原畫裡 Rakan 那一塊，
#    Rakan 自己的 Data Dragon 原畫對不到）。所以記下卡片對到原畫上的位置，查 assets/draft_card_alias.json（從已知正解的卡片學來：
#    同一張原畫上不同位置對應不同英雄）。這張原畫在表上、但位置離表上每一點都超過 ALIAS_FRAC（原畫寬高比例），就回報讀不到，不猜。
# 3. 選擇中或已鎖定：選擇中的原畫蒙上隊伍色調（藍方偏藍、紅方偏暗），用對齊後卡片與原畫同區域的顏色比值判斷。
# 用法：from draft_picks import Reader; R = Reader(); R.overlay(frame) -> 分數；R.cards(frame) -> 10 張卡的讀值
import os, glob, json
import numpy as np, cv2
ROOT = os.path.join(os.path.dirname(__file__), "..")
Y0, Y1 = 792, 1010                                         # 卡片原畫區（避開下方的名字與位置圖示）
def card_box(side, i):
    x0 = i * 160 if side == "B" else 1120 + i * 160
    return x0 + 30, x0 + 158                              # 左側 30 px 是直排的選手名
MIN_INL = 12
MIN_INL_CARD = 25                                          # 對到卡片庫（轉播卡片截圖）要更多內點：卡片截圖含介面線條
# 特徵點太少、原畫比不上的英雄（鄂爾：卡片是放大到臉、又暗又糊的經典原畫，整張只有 20 個特徵點，連跟自己比都過不了 25）：
# 一般辨識失敗時，改用整張圖相關係數比卡片庫。2026-10-24 瑞士輪第 1 場 BP 畫面量測：鄂爾對另一局鄂爾卡 0.935–0.945，
# 其他 9 隻英雄 ≤ 0.44。但 10/18 的空格（近黑底＋選手名字）也對到 0.80–0.86：所以另外要求飽和度跟卡片相近
# （鄂爾卡 190–200；那些空格 ≤ 101），門檻也提高到 0.88（今晚真的鄂爾格 0.97–0.99，跨局 0.945）。
NCC_CARD = 0.88
SAT_TOL = 0.3
ALIAS_FRAC = 0.05                                          # 卡片中心對到原畫上的位置（原畫寬高的比例）離別名表上的點多遠以內才採用

def _ncc(a, b):
    a = a.astype(float) - a.mean(); b = b.astype(float) - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-9))

class Reader:
    def __init__(self, art_dir=os.path.join(ROOT, "hero-art", "splash"), overlay_tpl=os.path.join(ROOT, "assets", "draft_overlay.npz")):
        self.sift_db = cv2.SIFT_create(nfeatures=1500); self.sift = cv2.SIFT_create(); self.bf = cv2.BFMatcher()
        self.db = {}; self.exclude = set()
        for p in sorted(glob.glob(os.path.join(art_dir, "*_0.jpg"))):
            col = cv2.imread(p)                               # 全尺寸：0.6 倍時 Yone 這種把臉放很大的卡只剩 10 個內點（Day 1 第 5 局漏讀）
            kp, de = self.sift_db.detectAndCompute(cv2.cvtColor(col, cv2.COLOR_BGR2GRAY), None)
            self.db[os.path.basename(p)[:-6]] = (np.float32([k.pt for k in kp]), de, col)
        # 轉播實際出現過的卡片（tools/draft_cards_build.py 從已知正解的局存下；不進 repo）：轉播原畫與 Data Dragon 不同的英雄（Ornn、Rakan）靠這個
        for p in sorted(glob.glob(os.path.join(os.path.dirname(art_dir), "cards", "*.png"))):
            col = cv2.imread(p); kp, de = self.sift_db.detectAndCompute(cv2.cvtColor(col, cv2.COLOR_BGR2GRAY), None)
            if de is not None: self.db["card:" + os.path.basename(p)[:-4]] = (np.float32([k.pt for k in kp]), de, col)
        if not self.db: print("draft_picks：缺原畫，先跑 tools/fetch_ddragon_splash.py", flush=True)
        t = np.load(overlay_tpl); self.top, self.bot = t["top"], t["bot"]
        ap = os.path.join(ROOT, "assets", "draft_card_alias.json")
        self.alias = json.load(open(ap, encoding="utf-8")) if os.path.exists(ap) else {}

    def overlay(self, frame):
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return min(_ncc(g[790:900, 800:1120], self.top), _ncc(g[1045:1080, 800:1120], self.bot))

    def ident(self, crop):
        kp, de = self.sift.detectAndCompute(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None)
        if de is None or len(kp) < 5: return None
        pts = np.float32([k.pt for k in kp]); sc = []
        for c, (pts2, de2, _) in self.db.items():
            if self.exclude and c.startswith("card:") and any(g in c for g in self.exclude): continue   # 驗證時排除當局學來的卡片
            m = self.bf.knnMatch(de, de2, k=2); good = [a for a, b in (x for x in m if len(x) == 2) if a.distance < 0.75 * b.distance]
            if len(good) < 4: continue
            M, mask = cv2.estimateAffinePartial2D(pts[[a.queryIdx for a in good]], pts2[[a.trainIdx for a in good]], method=cv2.RANSAC, ransacReprojThreshold=4)
            if M is not None and (not c.startswith("card:") or mask.sum() >= MIN_INL_CARD): sc.append((int(mask.sum()), c, M))
        if not sc: return None
        sc.sort(key=lambda x: -x[0])
        M = sc[0][2]; at = M @ np.array([crop.shape[1] / 2, crop.shape[0] / 2, 1.0]); h, w = self.db[sc[0][1]][2].shape[:2]
        return sc[0][1], sc[0][0], (sc[1][0] if len(sc) > 1 else 0), M, [round(float(at[0]) / w, 4), round(float(at[1]) / h, 4)]

    def by_picture(self, crop):
        """卡片庫中整張圖最像的一張（相關係數 >= NCC_CARD）：(分數, 名稱, 圖) 或 None。取卡片中央一塊，在幾個縮放下找。"""
        h, w = crop.shape[:2]; q = crop[int(h * .15):int(h * .75), int(w * .15):int(w * .85)]
        sat = float(cv2.cvtColor(q, cv2.COLOR_BGR2HSV)[..., 1].mean())
        best = None
        for name, (_, _, col) in self.db.items():
            if not name.startswith("card:"): continue
            ch, cw = col.shape[:2]
            ref = float(cv2.cvtColor(col[int(ch * .15):int(ch * .75), int(cw * .15):int(cw * .85)], cv2.COLOR_BGR2HSV)[..., 1].mean())
            if abs(sat - ref) > SAT_TOL * ref: continue          # 近黑的空格：圖形對得上，顏色對不上
            for f in (0.85, 0.92, 1.0, 1.08, 1.16, 1.25):
                c = cv2.resize(col, None, fx=f, fy=f)
                if c.shape[0] < q.shape[0] or c.shape[1] < q.shape[1]: continue
                sc = float(cv2.matchTemplate(c, q, cv2.TM_CCOEFF_NORMED).max())
                if sc >= NCC_CARD and (best is None or sc > best[0]): best = (round(sc, 3), name, col)
        return best

    def ident_one(self, crop, champ):
        """卡片對某一隻英雄原畫的內點數（建卡片庫用）。"""
        kp, de = self.sift.detectAndCompute(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None)
        if de is None or champ not in self.db: return 0
        pts = np.float32([k.pt for k in kp]); pts2, de2, _ = self.db[champ]
        m = self.bf.knnMatch(de, de2, k=2); good = [a for a, b in (x for x in m if len(x) == 2) if a.distance < 0.75 * b.distance]
        if len(good) < 4: return 0
        M, mask = cv2.estimateAffinePartial2D(pts[[a.queryIdx for a in good]], pts2[[a.trainIdx for a in good]], method=cv2.RANSAC, ransacReprojThreshold=4)
        return int(mask.sum()) if M is not None else 0

    def resolve(self, art, at):
        """第二階段：原畫 art、卡片中心對到原畫上的 at → 英雄。art 不在別名表上就是 art 本身；在表上取最近的已知位置，太遠回 None。"""
        if art.startswith("card:"): return art[5:].split("__")[0]
        pts = self.alias.get(art)
        if not pts: return art
        d, champ = min((np.hypot(at[0] - x, at[1] - y), c) for x, y, c in pts)
        return champ if d <= ALIAS_FRAC else None

    def colour(self, crop, champ, M):
        """對齊後卡片與原畫同區域的 (藍/紅比值之比, 亮度比, 飽和度比)。鎖定 ≈ (0.8–1.1, 常數, 常數)。"""
        w = cv2.warpAffine(self.db[champ][2], cv2.invertAffineTransform(M), (crop.shape[1], crop.shape[0]), flags=cv2.INTER_AREA)
        valid = w.sum(axis=2) > 30
        if valid.sum() < 500: return None
        a = crop[valid].astype(float).mean(axis=0) + 1; b = w[valid].astype(float).mean(axis=0) + 1
        ha = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[valid].astype(float).mean(axis=0) + 1
        hb = cv2.cvtColor(w, cv2.COLOR_BGR2HSV)[valid].astype(float).mean(axis=0) + 1
        return round((a[0] / a[2]) / (b[0] / b[2]), 3), round(ha[2] / hb[2], 3), round(ha[1] / hb[1], 3)

    def cards(self, frame):
        """10 張卡的讀值。某格畫面與上一次幾乎相同（平均絕對差 < 4）就沿用上一次的結果：BP 中大部分卡片幾秒內不變。"""
        out = []
        if not hasattr(self, "_last"): self._last = {}
        for side in "BR":
            for i in range(5):
                x0, x1 = card_box(side, i); crop = frame[Y0:Y1, x0:x1]
                prev = self._last.get((side, i))
                if prev is not None and np.abs(crop.astype(np.int16) - prev[0]).mean() < 4:
                    out.append(prev[1]); continue
                res = self._card(side, i, crop); self._last[(side, i)] = (crop.astype(np.int16), res); out.append(res)
        return out

    def _card(self, side, i, crop):
        r = self.ident(crop)
        if not r or r[1] < MIN_INL:
            sp = self.by_picture(crop)
            if sp:
                score, name, col = sp
                # 卡片庫的圖是鎖定後的卡，顏色直接跟它比；內點數記成門檻值，同一畫面重複時讓真正特徵比對到的那格優先
                return {"side": side, "slot": i, "champ": name[5:].split("__")[0], "art": name, "at": None, "inl": MIN_INL, "second": 0,
                        "ncc": score, "colour": plain_colour(crop, col)}
            return {"side": side, "slot": i, "champ": None, "inl": r[1] if r else 0}
        art, inl, second, M, at = r
        return {"side": side, "slot": i, "champ": self.resolve(art, at), "art": art, "at": at, "inl": inl, "second": second, "colour": self.colour(crop, art, M)}

def plain_colour(crop, card):
    """跟 Reader.colour 同樣的三個比值，但對象是同大小的轉播卡片截圖（不必對齊）。"""
    a = crop.reshape(-1, 3).astype(float).mean(axis=0) + 1; b = card.reshape(-1, 3).astype(float).mean(axis=0) + 1
    ha = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(float).mean(axis=0) + 1
    hb = cv2.cvtColor(card, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(float).mean(axis=0) + 1
    return round((a[0] / a[2]) / (b[0] / b[2]), 3), round(ha[2] / hb[2], 3), round(ha[1] / hb[1], 3)

# ── 選擇中／已鎖定（Day 2+3 共 10 局 BP 量測，2026-10-18）──
# 藍方選擇中：藍/紅比值之比中位數 1.70（p5 1.07），鎖定 0.96（p95 1.12）；紅方選擇中 0.72（p95 1.03），鎖定 1.00（p5 0.84）。
# 飽和度比：選擇中 1.28–1.54（中位數），鎖定 1.12（p95 1.28–1.40）。
def state(card):
    """'locked' / 'hover' / None（空格）。"""
    if not card.get("champ") or not card.get("colour"): return None
    tint, lum, sat = card["colour"]
    if card["side"] == "B": hover = tint > 1.15 or sat > 1.45
    else: hover = tint < 0.82 or sat > 1.35
    return "hover" if hover else "locked"

def dedupe(cards):
    """同一畫面同一隻英雄只能在一格：重複時保留內點多的那格，其他格當作讀不到（Xayah／Rakan 原畫是同一張圖）。"""
    best = {}
    for k, c in enumerate(cards):
        if c.get("champ") and (c["champ"] not in best or c["inl"] > cards[best[c["champ"]]]["inl"]): best[c["champ"]] = k
    return [c if not c.get("champ") or best[c["champ"]] == k else {**c, "champ": None, "dup": True} for k, c in enumerate(cards)]

class Tracker:
    """依時間餵入每張 BP 畫面的 cards()，維護兩隊已鎖定的英雄；鎖定後不撤回。鎖定條件（任一）：
    (a) 顏色：連續 NEED 張畫面都是「已鎖定」。
    (b) 輪到對方（維護者 2026-10-14 的判定準則：一個環節開始後，上一環節的結果定案）：對方出現一隻「比我方這隻晚出現」的新英雄
        （連續 NEED 張），而我方這隻仍在卡上。同一隊同時輪到兩手（紅 1-2、藍 2-3、藍 4-5）不互相封存。
    (c) 交換階段：某隊有英雄換了位置 → 該隊已選完，該隊卡上全部鎖定（只鎖該隊：Day 2 第 5 局紅方開始交換時，藍方最後一手還在選擇中）。
    (d) 10 格全滿、連續 SETTLE 秒沒有變化 → 全部鎖定（每手限時 30 秒，選擇中不會停這麼久）。
    (e) 之後又有英雄出現，而且比這隻晚 LATER 秒以上 → 這隻已鎖定（每手限時 30 秒，選擇中撐不到那麼久）。
        顏色判不準的英雄靠這條：2026-10-24 第 3 場 MKOI 的卡瑪原畫偏藍，鎖定後藍紅比 1.158（門檻 1.15）一直被當成選擇中。
        暫停時不會有新英雄出現，所以不會誤鎖。"""
    NEED = 2; SETTLE = 45; LATER = 60
    def __init__(self):
        self.locked = {"B": set(), "R": set()}; self.run = {}; self.seen_n = {}; self.first = {}; self.slot_of = {}
        self.view = None; self.full_since = None; self.last_sig = None
    def _lock(self, side, champ):
        if champ not in self.locked["B"] | self.locked["R"]: self.locked[side].add(champ)
    def feed(self, cards, t):
        cards = dedupe(cards); shown = {}
        for c in cards:
            if c.get("champ"): shown[(c["side"], c["champ"])] = c
        for key in shown: self.seen_n[key] = self.seen_n.get(key, 0) + 1
        for key in list(self.seen_n):
            if key not in shown: self.seen_n[key] = 0
        for key in shown:
            if self.seen_n[key] >= self.NEED and key not in self.first: self.first[key] = t
        # (a) 顏色
        for key, c in shown.items():
            self.run[key] = self.run.get(key, 0) + 1 if state(c) == "locked" else 0
            if self.run[key] >= self.NEED: self._lock(*key)
        # (b) 輪到對方
        for (s, ch) in shown:
            if (s, ch) not in self.first: continue
            o = "R" if s == "B" else "B"
            if any(k[0] == o and k in self.first and self.first[k] > self.first[(s, ch)] for k in shown): self._lock(s, ch)
        # (c) 交換階段
        for key, c in shown.items():
            if self.slot_of.get(key) is not None and self.slot_of[key] != c["slot"] and self.seen_n[key] >= self.NEED:
                for k2 in shown:
                    if k2[0] == key[0]: self._lock(*k2)
            if self.seen_n[key] >= self.NEED: self.slot_of[key] = c["slot"]
        # (e) 之後又有英雄出現、而且晚了 LATER 秒以上
        if self.first:
            newest = max(self.first.values())
            for key in shown:
                if key in self.first and newest - self.first[key] >= self.LATER: self._lock(*key)
        # (d) 全滿且穩定
        sig = tuple(c.get("champ") for c in cards)
        if all(sig):
            if sig != self.last_sig: self.full_since = t
            elif t - self.full_since >= self.SETTLE:
                for k2 in shown: self._lock(*k2)
        else: self.full_since = None
        self.last_sig = sig; self.view = cards
    def result(self):
        """{"B": {"picks": [5], "hovering": [5]}, "R": …}：picks 只放已鎖定、依目前卡片位置；hovering 放卡上還沒鎖定的英雄。"""
        out = {}
        for s in "BR":
            cs = [c for c in (self.view or []) if c["side"] == s]
            if len(cs) != 5: out[s] = {"picks": [None] * 5, "hovering": [None] * 5}; continue
            picks = [c["champ"] if c.get("champ") in self.locked[s] else None for c in cs]
            hovering = [c["champ"] if c.get("champ") and c["champ"] not in self.locked[s] else None for c in cs]
            # 已鎖定、但最新一張畫面讀不到的（剛鎖定時卡片閃光、轉播切畫面那一瞬間）：留在上次出現的格子，
            # 不要在 BP 視窗裡消失一下又回來（2026-10-24 瑞士輪第 2 場）。那格現在有別的英雄就不放。
            for champ in self.locked[s]:
                i = self.slot_of.get((s, champ))
                if champ not in picks and i is not None and picks[i] is None and hovering[i] is None: picks[i] = champ
            out[s] = {"picks": picks, "hovering": hovering}
        return out
