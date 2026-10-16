# 小地圖塔存在判斷（PoC）：以早期畫面截下的塔圖示為模板，在各塔推算位置附近搜尋最佳比對分數。
import cv2, sys, subprocess
import numpy as np

X0, Y0, S, M = 1105.0, 540.0, 165.0, 14870.0
SITES = {
 "B": {"top_outer": (981, 10441), "top_inner": (1512, 6699), "top_inhib": (1169, 4287),
       "mid_outer": (5846, 6396), "mid_inner": (5048, 4812), "mid_inhib": (3651, 3696),
       "bot_outer": (10504, 1029), "bot_inner": (6919, 1483), "bot_inhib": (4281, 1253),
       "nexus_a": (1748, 2270), "nexus_b": (2177, 1807)},
 "R": {"top_outer": (4318, 13875), "top_inner": (7943, 13411), "top_inhib": (10481, 13651),
       "mid_outer": (8955, 8510), "mid_inner": (9767, 10113), "mid_inhib": (11134, 11207),
       "bot_outer": (13866, 4505), "bot_inner": (13327, 8226), "bot_inhib": (13624, 10572),
       "nexus_a": (12611, 13084), "nexus_b": (13052, 12612)}}
def px(g): return X0 + g[0] / M * S, Y0 + (1 - g[1] / M) * S

def grab(vod, t):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t), "-i", vod, "-frames:v", "1", "-vf", "scale=1280:720",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, np.uint8).reshape(720, 1280, 3)

def crop_tpl(im, cx, cy, r=6):
    return im[int(cy - r):int(cy + r + 1), int(cx - r):int(cx + r + 1)].copy()

if __name__ == "__main__":
    vod, early_t = sys.argv[1], int(sys.argv[2])
    times = [int(x) for x in sys.argv[3:]]
    early = grab(vod, early_t)
    # 模板：藍 top_outer、紅 top_outer 的最佳局部位置（在推算位置附近 ±8px 取最「像塔」的點：以飽和度峰值近似）
    def snap(im, g, side, rad=8):
        cx, cy = px(g); best = None
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                x, y = int(cx + dx), int(cy + dy)
                w = hsv[y - 3:y + 4, x - 3:x + 4]
                hue = w[:, :, 0].astype(int); sat = w[:, :, 1].astype(int); val = w[:, :, 2].astype(int)
                if side == "R":
                    m = ((hue < 8) | (hue > 170)) & (sat > 120) & (val > 90)
                else:
                    m = (hue > 85) & (hue < 110) & (sat > 90) & (val > 90)
                sc = int(m.sum())
                if best is None or sc > best[0]: best = (sc, x, y)
        return best
    sites = []
    for side in "BR":
        for name, g in SITES[side].items():
            sc, x, y = snap(early, g, side)
            sites.append((side, name, x, y, sc))
    print("early snap scores (colored px of 49):")
    for s in sites: print(f"  {s[0]}-{s[1]:10s} at ({s[2]},{s[3]}) score {s[4]}")
    for t in times:
        im = grab(vod, t)
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
        cnt = {"B": 0, "R": 0}
        for side, name, x, y, _ in sites:
            w = hsv[y - 3:y + 4, x - 3:x + 4]
            hue = w[:, :, 0].astype(int); sat = w[:, :, 1].astype(int); val = w[:, :, 2].astype(int)
            if side == "R": m = ((hue < 8) | (hue > 170)) & (sat > 120) & (val > 90)
            else: m = (hue > 85) & (hue < 110) & (sat > 90) & (val > 90)
            if int(m.sum()) >= 8: cnt[side] += 1
        print(f"clip {t}s: blue sites present {cnt['B']}/11, red sites present {cnt['R']}/11")
