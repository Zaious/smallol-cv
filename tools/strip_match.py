# 底部列選角比對（PoC）：每格頭像區 vs Data Dragon 方形圖，回傳最佳英雄與分數
import glob, os, sys, cv2, numpy as np

SLOTS = [(0, 53), (53, 107), (107, 160), (160, 213), (213, 267),
         (373, 427), (427, 480), (480, 533), (533, 587), (587, 640)]
Y0, Y1 = 268, 321   # 頭像區（53x53）
S = 40               # 比對解析度

def load_icons():
    names, feats = [], []
    for p in sorted(glob.glob("hero-icons/*.png")):
        im = cv2.imread(p)
        im = cv2.resize(im, (S, S), interpolation=cv2.INTER_AREA).astype(np.float32)
        names.append(os.path.splitext(os.path.basename(p))[0])
        feats.append(im.ravel())
    return names, np.stack(feats)

def slot_feat(im, a, b):
    c = im[Y0:Y1, a:b]
    c = cv2.resize(c, (S, S), interpolation=cv2.INTER_AREA).astype(np.float32)
    return c.ravel()

def best(names, F, v):
    v = v - v.mean()
    Fn = F - F.mean(axis=1, keepdims=True)
    sc = (Fn @ v) / (np.linalg.norm(Fn, axis=1) * np.linalg.norm(v) + 1e-6)
    i = int(sc.argmax())
    return names[i], float(sc[i])

if __name__ == "__main__":
    names, F = load_icons()
    for path in sys.argv[1:]:
        im = cv2.imread(path)
        out = []
        for a, b in SLOTS:
            n, s = best(names, F, slot_feat(im, a, b))
            out.append(f"{n}({s:.2f})")
        print(os.path.basename(path), " | ".join(out))
