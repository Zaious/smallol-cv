# BP 畫面判斷藍紅方：BP 列中央左右各一個隊伍 logo（轉播為白色單色），左邊固定是藍方。
# 官方 API 開局前給的藍紅方會先錯、開打後才更正（Day 2：7 局中 5 局在 BP 中出現顛倒），所以 BP 中改用畫面判斷。
# 方法：轉播 logo 取白色像素剪影、API logo（getEventDetails 的 team.image）取不透明區域剪影，裁到外框後縮成 64x64 比 IoU。
# 用法：from draft_sides import sides; sides(bgr_frame, {"KC": logo_path, "C9": logo_path}) -> ("KC", "C9", 信心差)
import os, sys, urllib.request
import numpy as np, cv2
LOGO = {"L": (900, 990, 810, 910), "R": (900, 990, 1005, 1110)}   # (y0, y1, x0, x1)，畫面 1920x1080
CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "team_logos")

def _norm_mask(m):
    ys, xs = np.where(m)
    if len(xs) < 30: return None
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255
    return cv2.resize(m, (64, 64), interpolation=cv2.INTER_AREA) > 127

def broadcast_mask(frame, side):
    y0, y1, x0, x1 = LOGO[side]; g = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    return _norm_mask(g > 170)

def logo_mask(path):
    a = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if a is None: return None
    if a.ndim == 3 and a.shape[2] == 4: m = a[:, :, 3] > 128
    else:
        g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY); m = np.abs(g.astype(int) - int(np.median(g[0]))) > 40   # 無透明層：與邊緣底色不同者
    return _norm_mask(m)

def fetch_logo(code, url):
    os.makedirs(CACHE, exist_ok=True); p = os.path.join(CACHE, f"{code}.png")
    if not os.path.exists(p): urllib.request.urlretrieve(url.replace("http://", "https://"), p)
    return p

def iou(a, b): return float((a & b).sum() / max(1, (a | b).sum()))

def sides(frame, logos):
    """logos：{隊伍代碼: logo 檔路徑}（兩隊）。回傳 (藍方代碼, 紅方代碼, 信心差) 或 None。信心差 = 兩種配對的 IoU 總和差。"""
    L, R = broadcast_mask(frame, "L"), broadcast_mask(frame, "R")
    if L is None or R is None: return None
    (a, pa), (b, pb) = [(k, logo_mask(v)) for k, v in logos.items()]
    if pa is None or pb is None: return None
    s1 = iou(L, pa) + iou(R, pb); s2 = iou(L, pb) + iou(R, pa)
    return (a, b, s1 - s2) if s1 >= s2 else (b, a, s2 - s1)
