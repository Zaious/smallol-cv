# 畫面核對用對照圖：每件被指派的事件，取 v-25, v+8, v+25, v+60, v+120 的站點特寫。
import json, subprocess, sys
import numpy as np, cv2
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8")); pos = {s["id"]: s for s in cfg["sites"]}
X0, Y0, K = int(1085 * 1.5), int(525 * 1.5), 1.5 / 5
G = {"g1": ("vod/probe1080/seg_10000_11304.mp4", 9144, 10000), "g2": ("vod/probe1080/g2_13500_15300.mp4", 12730, 13500),
     "g3": ("vod/probe1080/g3_17546_19008.mp4", 16760, 17546), "g4": ("vod/probe1080/g4_21094_22183.mp4", 20366, 21094),
     "g5": ("vod/probe1080/g5_24270_25741.mp4", 23499, 24270),
     "s1": ("vod/semi/s1.mp4", 427, 0), "s2": ("vod/semi/s2.mp4", 447, 0), "s3": ("vod/semi/s3.mp4", 467, 0), "s4": ("vod/semi/s4.mp4", 456, 0)}
def frame(g, gs):
    f, g0, t0 = G[g]; ss = max(0, g0 + int(gs) - t0)
    raw = subprocess.run(["ffmpeg","-v","error","-ss",str(ss),"-i",f,"-frames:v","1","-f","rawvideo","-pix_fmt","bgr24","-"], stdout=subprocess.PIPE).stdout
    if len(raw) < 1920*1080*3: return np.zeros((1080,1920,3), np.uint8)
    return np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3)
items = []
for g in ["s1", "s2", "s3", "s4"]:
    asg = sorted([a for a in json.load(open(f"data/assign_v12_{g}.json")) if a["site"]], key=lambda a: a["event"])
    for a in asg[::2]:                      # 系統性抽樣：每局被指派的事件，隔一件取一件
        items.append((g, a["team"], a["event"], a["site"]))
print("assigned events:", len(items))
OFFS = [(-25, "-25"), (8, "+8"), (25, "+25"), (60, "+60"), (120, "+120")]
per = 5; k = 0
for s in range(0, len(items), per):
    rows = []
    for g, team, ev, site in items[s:s + per]:
        cx, cy = X0 + int(round(pos[site]["x"] * K)), Y0 + int(round(pos[site]["y"] * K)); tiles = []
        for o, lab in OFFS:
            f = frame(g, ev + o); t = cv2.resize(f[cy-18:cy+19, cx-18:cx+19], (130, 130), interpolation=cv2.INTER_CUBIC)
            cv2.putText(t, f"{g} {site[:13]} {lab}", (2, 11), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (0, 255, 255), 1); tiles.append(t)
        rows.append(np.hstack(tiles))
    cv2.imwrite(f"frames/verify_semi_{k}.png", np.vstack(rows)); k += 1
print("sheets:", k)
for i, it in enumerate(items): print(i, it[0], f"{int(it[2])//60}:{int(it[2])%60:02d}", it[3])
