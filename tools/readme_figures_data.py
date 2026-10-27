# The README's figures, part 1 (on the server, where the recordings are): one game's data as a JSON file.
#   towers: each site's per-frame reading (alive / destroyed / unsure) on the game clock, the feed's tower
#           events, and the names the service gave;
#   lag:    the scoreboard clock read off the broadcast against the feed's time (the stream's delay);
#   draft:  the draft cards read frame by frame (champion, hovering or locked);
#   minimap: one minimap frame mid-game and its per-site reading.
# No broadcast picture leaves here except the minimap crop (285x285) the figure annotates.
# Usage: python tools/readme_figures_data.py <gameId> <run> <out.json> [--minimap-at 29:20]
import sys, os, json, glob, csv, shutil, datetime as dt
gid, run, out = sys.argv[1], sys.argv[2], sys.argv[3]
mm_at = sys.argv[sys.argv.index("--minimap-at") + 1] if "--minimap-at" in sys.argv else "29:20"
sys.argv = [sys.argv[0], "--dir", "data/live_worlds2026"]
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, cv2
import live_service as L, draft_picks as DP
D = L.D; ts = L.ts

feed = sorted((json.loads(l) for l in open(f"{D}/feed_{gid}.jsonl", encoding="utf-8")), key=lambda r: r["ts"])
ig = [r for r in feed if r["state"] == "in_game"]; st0 = ts(ig[0]["ts"]); end = ts(feed[-1]["ts"])
events, prev = [], None
for r in feed:
    if prev:
        for s in "BR":
            for _ in range(r[s]["t"] - prev[s]["t"]): events.append({"by": s, "lost": "R" if s == "B" else "B", "sec": round(ts(r["ts"]) - st0)})
    prev = r

# Screen time -> game clock, from the scoreboard reads (the nearest five, as the service does).
reads = L.hud_clock_reads(st0, end + 120)
ws = np.array([w for w, _ in reads]); offs = np.array([o for _, o in reads])
def clock_at(w):
    i = np.argsort(np.abs(ws - w))[:5]
    return float(w + np.median(offs[i]))
lag = float(np.median([(-o) - st0 for o in offs]))

rows = list(csv.DictReader(open(f"{D}/clf_live_{run}.csv", encoding="utf-8")))
anc = float(np.median([ts(r["wall_utc"]) - int(r["n"]) for r in rows[-3000:]]))
sites = [k[:-2] for k in rows[0] if k.endswith("_A")]
series = {s: [] for s in sites}; t_last = -99
for r in rows:
    w = int(r["n"]) + anc
    if not (st0 + lag - 30 <= w <= end + lag + 20) or r["layout"] != "1": continue
    c = clock_at(w)
    if c - t_last < 5: continue
    t_last = c
    for s in sites: series[s].append([round(c), "A" if r[f"{s}_A"] == "1" else "D" if r[f"{s}_D"] == "1" else "O"])

arch = json.load(open(os.path.join(L.ROOT, "data", "archive", "games", f"{gid}.json"), encoding="utf-8"))
named = arch.get("towersLost") or {}

# The draft: the broadcast's draft frames before the game, read card by card.
R = DP.Reader(); draft = []
offf = sorted((int(f[-11:-4]) + anc, f) for f in glob.glob(f"{D}/snap/off_{run}_*.jpg"))
for w, f in offf:
    if not (st0 + lag - 1500 <= w <= st0 + lag): continue
    im = cv2.imread(f)
    if im is None or R.overlay(im) < 0.6: continue
    cards = R.cards(im)
    draft.append({"t": round(w - (st0 + lag)), "cards": [{"side": c["side"], "slot": c["slot"], "champ": c.get("champ"), "state": DP.state(c) if c.get("champ") else None} for c in cards]})
# One minimap frame mid-game and its per-site reading.
m, s_ = mm_at.split(":"); want = int(m) * 60 + int(s_)
best = None
for r in rows:
    if r["layout"] != "1": continue
    n = int(r["n"]); w = n + anc
    if not (st0 + lag <= w <= end + lag): continue
    p = f"{D}/snap/mm_{run}_{n:07d}.png"
    if not os.path.exists(p): continue
    d_ = abs(clock_at(w) - want)
    if best is None or d_ < best[0]: best = (d_, p, r, round(clock_at(w)))
mm = None
if best:
    _, p, r, c = best
    shutil.copy(p, out.replace(".json", "_minimap.png"))
    mm = {"clock": c, "reading": {s: {"state": "A" if r[f"{s}_A"] == "1" else "D" if r[f"{s}_D"] == "1" else "O", "frac": float(r[f"{s}_frac"])} for s in sites}}

geo = json.load(open(os.path.join(L.ROOT, "assets", "minimap_sites_2026_worlds.json"), encoding="utf-8"))
json.dump({"game": gid, "teams": arch["teams"], "winner": arch.get("winner"), "duration": arch.get("duration"), "lag": round(lag, 1),
           "hud": [[round(w - st0, 1), round(w + o)] for w, o in reads], "events": events, "series": series, "named": named,
           "draft": draft, "bans": arch.get("bans"), "minimap": mm,
           "sites": [{"id": s["id"], "x": s["x"] * 0.3, "y": s["y"] * 0.3} for s in geo["sites"] if s["kind"] == "tower"]},
          open(out, "w", encoding="utf-8"), ensure_ascii=False)
print("ok", len(reads), "reads, lag", round(lag, 1), "draft frames", len(draft), "minimap", best[3] if best else None)
