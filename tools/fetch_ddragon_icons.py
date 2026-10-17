# 下載 Data Dragon 英雄方形圖示到 hero-icons/<版本>/（禁用辨識用；圖示不進 repo）。
# 用法：python tools/fetch_ddragon_icons.py [版本，預設 16.20.1]
import json, os, sys, urllib.request
v = sys.argv[1] if len(sys.argv) > 1 else "16.20.1"
root = os.path.join(os.path.dirname(__file__), "..", "hero-icons"); os.makedirs(os.path.join(root, v), exist_ok=True)
meta = os.path.join(root, f"{v}_champion.json")
urllib.request.urlretrieve(f"https://ddragon.leagueoflegends.com/cdn/{v}/data/en_US/champion.json", meta)
ids = json.load(open(meta, encoding="utf-8"))["data"]; n = 0
for cid in ids:
    p = os.path.join(root, v, f"{cid}.png")
    if not os.path.exists(p): urllib.request.urlretrieve(f"https://ddragon.leagueoflegends.com/cdn/{v}/img/champion/{cid}.png", p); n += 1
print(f"{v}: 新下載 {n}，共 {len(ids)} 個英雄")
