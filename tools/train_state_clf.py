# 站點三狀態分類器（A 存活 / D 消失 / O 遮擋）：以標註小圖訓練，「留一場」交叉驗證（按場次切，避免相鄰秒洩漏）。
# 用法：python tools/train_state_clf.py [--save]
import json, sys
import numpy as np, cv2
from collections import Counter
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

d = np.load("data/labels/train.npz")["crops"]; meta = json.load(open("data/labels/train_meta.json"))
lab = dict(l.split() for l in open("data/labels/train_labels.txt").read().splitlines())
keep = [i for i in range(len(meta)) if lab[str(i)] in "ADO"]
X_img = d[keep]; y = np.array([lab[str(i)] for i in keep]); game = np.array([meta[i]["game"] for i in keep])
print("樣本", len(y), dict(Counter(y)))

def feats(img):
    """45x45 彩色小圖 -> 特徵：中心 27x27 灰階（正規化）+ 中心 27x27 HSV 的 H/S 通道降採樣 + 中心 15x15 邊緣強度。"""
    c = img[9:36, 9:36]
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float32); g = (g - g.mean()) / (g.std() + 1e-6)
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV).astype(np.float32)
    h = cv2.resize(hsv[:, :, 0] / 180.0, (9, 9), interpolation=cv2.INTER_AREA).ravel()
    s = cv2.resize(hsv[:, :, 1] / 255.0, (9, 9), interpolation=cv2.INTER_AREA).ravel()
    v = cv2.resize(hsv[:, :, 2] / 255.0, (9, 9), interpolation=cv2.INTER_AREA).ravel()
    sx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); sy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    e = cv2.resize(np.hypot(sx, sy)[6:21, 6:21], (8, 8), interpolation=cv2.INTER_AREA).ravel()
    return np.concatenate([cv2.resize(g, (14, 14), interpolation=cv2.INTER_AREA).ravel(), h, s, v, e])
X = np.stack([feats(im) for im in X_img])
print("特徵維度", X.shape[1])

models = {
    "邏輯迴歸": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced")),
    "SVM(RBF)": lambda: make_pipeline(StandardScaler(), SVC(C=3, gamma="scale", class_weight="balanced")),
    "隨機森林": lambda: RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=0, n_jobs=-1),
}
for name, mk in models.items():
    pred = np.empty(len(y), dtype="<U1")
    for g in sorted(set(game)):
        tr, te = game != g, game == g
        m = mk().fit(X[tr], y[tr]); pred[te] = m.predict(X[te])
    acc = (pred == y).mean()
    cm = confusion_matrix(y, pred, labels=list("ADO"))
    rec = cm.diagonal() / cm.sum(axis=1); prec = cm.diagonal() / np.maximum(cm.sum(axis=0), 1)
    print(f"\n{name}  留一場總正確率 {acc*100:.1f}%")
    print("  混淆矩陣（列=真實 A/D/O，欄=預測 A/D/O）：")
    for lbl, row in zip("ADO", cm): print(f"    {lbl}: {row}")
    print("  召回率 A/D/O：", [f"{r*100:.0f}%" for r in rec], " 精確率 A/D/O：", [f"{p*100:.0f}%" for p in prec])
    per_game = {g: float((pred[game == g] == y[game == g]).mean()) for g in sorted(set(game))}
    print("  各場正確率：", {g: f"{v*100:.0f}%" for g, v in per_game.items()})
if "--save" in sys.argv:
    import pickle
    m = make_pipeline(StandardScaler(), SVC(C=3, gamma="scale", class_weight="balanced", probability=True, random_state=0)).fit(X, y)
    pickle.dump({"model": m, "classes": list(m.classes_)}, open("data/state_clf.pkl", "wb")); print("已儲存 data/state_clf.pkl，類別", list(m.classes_))
