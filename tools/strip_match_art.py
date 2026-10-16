# 底部列選角比對（PoC，立繪版）：格子 vs Data Dragon centered 立繪（預設皮膚）
# 立繪以多個縮放與水平位移取最大相關，因為格子是立繪的局部裁切。
import glob, os, sys, cv2, numpy as np

SLOTS = [(0, 53), (53, 107), (107, 160), (160, 213), (213, 267),
         (373, 427), (427, 480), (480, 533), (533, 587), (587, 640)]
Y0, Y1 = 262, 360
W, H = 53, 98

def gray_feat(im):
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = g - g.mean()
    return g / (np.linalg.norm(g) + 1e-6)

def load_art():
    arts = {}
    for p in sorted(glob.glob("hero-art/*.jpg")):
        im = cv2.imread(p)
        if im is not None:
            arts[os.path.splitext(os.path.basename(p))[0]] = im
    return arts

def best_for_slot(slot_img, arts):
    f = gray_feat(cv2.resize(slot_img, (W, H), interpolation=cv2.INTER_AREA))
    best = ("", -1.0)
    for name, art in arts.items():
        ah, aw = art.shape[:2]
        # 立繪高度取多個尺度，格子高度 H 對應到立繪的上半部
        for scale in (0.6, 0.8, 1.0, 1.2):
            h = int(H * 1.0 / scale) if scale else H
            w = int(aw * h / ah)
            if w < W or h > ah:
                continue
            resized = cv2.resize(art, (w, h), interpolation=cv2.INTER_AREA)
            for x in range(0, w - W + 1, max(1, (w - W) // 6 or 1)):
                for y in range(0, h - H + 1, max(1, (h - H) // 4 or 1)):
                    crop = resized[y:y + H, x:x + W]
                    s = float((gray_feat(crop) * f).sum())
                    if s > best[1]:
                        best = (name, s)
    return best

if __name__ == "__main__":
    arts = load_art()
    for path in sys.argv[1:]:
        im = cv2.imread(path)
        out = []
        for a, b in SLOTS:
            n, s = best_for_slot(im[Y0:Y1, a:b], arts)
            out.append(f"{n}({s:.2f})")
        print(os.path.basename(path), " | ".join(out))
