# 下載 Data Dragon 英雄原畫（經典造型 _0，1215×717）到 hero-art/splash/（BP 選角辨識用；原畫不進 repo）。
# 用法：python tools/fetch_ddragon_splash.py [版本，預設 16.20.1]（版本只用來取英雄清單）
import json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
v = sys.argv[1] if len(sys.argv) > 1 else "16.20.1"
ROOT = os.path.join(os.path.dirname(__file__), "..")
meta = os.path.join(ROOT, "hero-icons", f"{v}_champion.json")
if not os.path.exists(meta): sys.exit(f"缺 {meta}：先跑 tools/fetch_ddragon_icons.py {v}")
out = os.path.join(ROOT, "hero-art", "splash"); os.makedirs(out, exist_ok=True)
ids = list(json.load(open(meta, encoding="utf-8"))["data"])
def get(cid):
    p = os.path.join(out, f"{cid}_0.jpg")
    if os.path.exists(p): return 0
    urllib.request.urlretrieve(f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{cid}_0.jpg", p); return 1
with ThreadPoolExecutor(4) as ex: n = sum(ex.map(get, ids))
print(f"new {n}, total {len(ids)}")
