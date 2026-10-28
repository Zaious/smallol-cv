# Tower naming, replayed: runs the live service's own clock and naming code (live_service.game_clock /
# towers_named) every --step seconds through each recorded game, giving it only what existed at that moment
# (frames with wall_utc <= now, feed lines fetched by now, scoreboard reads of those frames), and scores what
# the app would have shown against the minimap itself.
#
# Truth (independent of the code under test): the tower icon's shape. --icon is icon_ncc.json, made on the server: every
# saved minimap crop (every 15 frames), each site's grey patch against that site's own icon template. A standing,
# visible tower scores 0.9-1.0; rubble 0.5 or less, and champions on it don't bring it back (colour does: a team's own
# champions defending their fallen tower read as "standing" in the colour reading). Replay frames are left out
# (--replays, replay_scores.json from tools/replay_banner.py). A tower fell after its last two crops in a row >= 0.7.
# --check-truth compares those times with the feed's tower counts (median 28 s apart, the feed being the later).
# Nexus turrets respawn and are left out.
#
# Scores: wrongSec = seconds a name was shown while the minimap still shows that icon plainly there more than 20 s
# later; finalExtra = such names in the final list; timeErr = |shown game time - truth| for the final names.
# --statelog scores what the service actually published (statelog.jsonl) the same way: old against new.
#
# Usage: python tools/naming_replay.py --dir <data/live_worlds2026> --hud <hud_reads.json> [--statelog <statelog.jsonl>]
#        [--step 15] [--games id,id] [--out replay.json] [--tmp <scratch dir>] [--sim-dir <tools dir>] [--check-truth]
# hud_reads.json: {run: [[n, clock or null], ...]}, every scoreboard read (made on the server, where the images are).
import sys, os, json, csv, glob, bisect, time as _time, types
import datetime as dt

arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
DATA, HUD, SLOG = arg("--dir"), arg("--hud"), arg("--statelog")
STEP = float(arg("--step", "15")); ONLY = set(arg("--games", "").split(",")) - {""}; OUT = arg("--out")
TMP, SIMDIR, CHECK, ICONF, REPLAYF = arg("--tmp"), arg("--sim-dir"), "--check-truth" in sys.argv, arg("--icon"), arg("--replays")
REVOKE_RUN, NO_REVOKE_STICKY = arg("--revoke-run"), "--no-revoke-sticky" in sys.argv     # try other settings than the service's
NEED_DEAD, REVOKE_WINDOW = arg("--need-dead"), arg("--revoke-window")
os.environ.setdefault("VIDEO_LAG", "46")          # what outpost_run sets for a Twitch source
sys.argv = [sys.argv[0], "--dir", DATA]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import live_service as L

ts = L.ts
ARCH = os.path.join(DATA, "..", "archive", "games")
# --tmp: where tower_naming writes its scratch files (L.D is only used for that once the hooks below are in;
#        give each concurrent replay its own). --sim-dir: a tools/ folder holding another trigger_sim_clf4.py to try.
if TMP: L.D = TMP; os.makedirs(L.D, exist_ok=True)
if SIMDIR: L.HERE = SIMDIR
if REVOKE_RUN: L.REVOKE_RUN = int(REVOKE_RUN)
if NO_REVOKE_STICKY: L.REVOKE_STICKY = False
if NEED_DEAD: L.NEED_DEAD = int(NEED_DEAD)
if REVOKE_WINDOW: L.REVOKE_WINDOW = int(REVOKE_WINDOW)
GRACE, STEP_CAP = 20, 30
# The truth stops 90 s after the feed's last line (the screen runs ~48 s behind): after the game the broadcast shows
# highlights without the REPLAY label, and their minimap has the towers standing again (GEN vs LYON 10-25, game 1).
END_SCREEN = 90

# --- every run's raw lines, with each frame's wall time ---
RUNS = {}
for p in sorted(glob.glob(os.path.join(DATA, "clf_live_*.csv"))):
    with open(p, encoding="utf-8") as f:
        head = next(csv.reader([f.readline()])); lines = f.readlines()
    wi = head.index("wall_utc")
    walls = np.array([ts(l.split(",", wi + 1)[wi]) for l in lines])
    RUNS[os.path.basename(p)[9:-4]] = (p, head, lines, walls)
HUDR = json.load(open(HUD)) if HUD else {}

def window(t0, t1):
    """{run: (walls, parsed rows)} for frames with wall in [t0, t1] (dicts, as csv.DictReader gives)."""
    out = {}
    for run, (p, head, lines, walls) in RUNS.items():
        i, j = bisect.bisect_left(walls, t0), bisect.bisect_right(walls, t1)
        if j > i: out[run] = (walls[i:j], [dict(zip(head, r)) for r in csv.reader(lines[i:j])])
    return out

ICON = json.load(open(ICONF)) if ICONF else {}
ICON_HI, ICON_AFTER = 0.7, 4
# replay_scores.json: {run: [[n, blue, white], ...]} for every saved top-left corner (tools/replay_banner.py on the server)
REPLAY = {run: {n for n, b, w in v if b >= 0.4 and w >= 0.12} for run, v in json.load(open(REPLAYF)).items()} if REPLAYF else {}
def replay_at(run, n): return (n - n % 5) in REPLAY.get(run, ()) or (n - n % 5 + 5) in REPLAY.get(run, ())
L.replay_at = replay_at

def truth(win, team, t0, t1):
    """{site: wall time it fell}, from the tower icon's shape (icon_ncc.json: every saved minimap crop, each site's grey
    patch against that site's own icon template). Standing and visible: 0.9-1.0. Fallen: 0.5 or less, and champions
    standing on the rubble don't bring it back (a team's own champions defending it read as "standing" in colour).
    A site fell at the first crop after its last >= 0.8, if at least 4 crops (a minute) follow; earlier = still standing."""
    seq = []
    for run, (walls, rows) in win.items():
        if run not in ICON: continue
        wt = L.frame_clock(rows); n0, n1 = int(rows[0]["n"]), int(rows[-1]["n"]); ids = ICON[run]["sites"]
        seq += [(wt(n), dict(zip(ids, v))) for n, v in ICON[run]["rows"] if n0 <= n <= n1 and t0 <= wt(n) <= t1 and not replay_at(run, n)]
    seq.sort(key=lambda x: x[0]); on = {}; stand = {}
    if not seq: return on, stand
    for s in [k for k in seq[0][1] if k.startswith(team + "_") and "nexus" not in k]:
        v = np.array([x[1][s] for x in seq]); hi = np.flatnonzero((v[:-1] >= ICON_HI) & (v[1:] >= ICON_HI))   # two crops in a row
        if not len(hi): continue
        stand[s[2:]] = seq[hi[-1] + 1][0]                       # the last time the icon was plainly there
        i = hi[-1] + 2
        if len(v) - i >= ICON_AFTER: on[s[2:]] = seq[i][0]
    return on, stand

def clock_map(win):
    """wall time -> game clock, from the scoreboard reads (per-frame wall time, nearest five reads)."""
    pts = []
    for run, (walls, rows) in win.items():
        wt = L.frame_clock(rows); n0, n1 = int(rows[0]["n"]), int(rows[-1]["n"])
        pts += [(wt(n), c - wt(n)) for n, c in HUDR.get(run, []) if c is not None and n0 <= n <= n1]
    if len(pts) < 5: return None
    pts.sort(); ws = np.array([p[0] for p in pts]); off = np.array([p[1] for p in pts])
    return lambda w: float(w + np.median(off[np.argsort(np.abs(ws - w))[:5]]))

def check_truth(feed, tru, cmap, st0):
    """Does the truth agree with the feed? Per team, towers lost before its first inhibitor fell (nexus turrets
    come after): the truth's fall times in order against the feed's, both on the screen's wall clock.
    Returns (time differences truth - feed in s, number of such feed towers, number of such truth towers)."""
    if cmap is None: return [], 0, 0
    lag = float(np.median([w - st0 - cmap(w) for w in np.linspace(st0 + 120, st0 + 900, 20)]))   # screen delay vs feed
    diffs, nf, nt = [], 0, 0; prev = None; fe = {"B": [], "R": []}; inh = {"B": None, "R": None}
    for x in feed:
        if prev:
            for tm, by in (("B", "R"), ("R", "B")):
                if x[tm]["i"] > prev[tm]["i"] and inh[tm] is None: inh[tm] = ts(x["ts"]) + lag
                if x[by]["t"] > prev[by]["t"] and inh[tm] is None: fe[tm] += [ts(x["ts"]) + lag] * (x[by]["t"] - prev[by]["t"])
        prev = x
    for tm in "BR":
        cut = inh[tm] or 1e18
        tr = sorted(w for w in tru[tm].values() if w < cut - 20)
        nf += len(fe[tm]); nt += len(tr)
        diffs += [round(a - b) for a, b in zip(tr, fe[tm])]
    return diffs, nf, nt

def score(snaps, tru, stand, cmap, lost_at):
    """snaps: [(wall, {team: {site: shown game seconds}})] in time order.
    A shown name is wrong while the minimap still shows that tower's icon plainly there later on (> 20 s after).
    flicker: a name shown, then taken away (not a nexus turret). unnamedSec: feed says more towers down than are named ("?")."""
    wrong_s, bad, flick, unnamed = 0.0, set(), 0, 0.0
    for k, (w, named) in enumerate(snaps):
        dur = min((snaps[k + 1][0] if k + 1 < len(snaps) else w + STEP) - w, STEP_CAP)
        if k + 1 < len(snaps):
            flick += sum(1 for tm in "BR" for s in named.get(tm, {}) if not s.startswith("nexus") and s not in snaps[k + 1][1].get(tm, {}))
        for tm in "BR":
            unnamed += dur * max(0, lost_at(tm, w) - len(named.get(tm, {})))
            for s in named.get(tm, {}):
                if s.startswith("nexus"): continue
                if stand[tm].get(s, 0) > w + GRACE: wrong_s += dur; bad.add(f"{tm}_{s}")
    final = snaps[-1][1] if snaps else {}
    err = [abs(sec - cmap(tru[tm][s])) for tm in "BR" for s, sec in final.get(tm, {}).items() if s in tru[tm] and cmap]
    miss = sum(1 for tm in "BR" for s in tru[tm] if s not in final.get(tm, {}))
    extra = sum(1 for tm in "BR" for s in final.get(tm, {}) if not s.startswith("nexus") and stand[tm].get(s, 0) > (snaps[-1][0] if snaps else 0))
    return {"wrongSec": round(wrong_s), "wrongNames": sorted(bad), "flicker": flick, "unnamedSec": round(unnamed), "finalMissing": miss, "finalExtra": extra,
            "timeErrMedian": round(float(np.median(err))) if err else None, "timeErrOver60": sum(1 for e in err if e > 60), "timed": len(err)}

# --- the hooks: the service sees only what existed at NOW ---
NOW = [0.0]; WIN = {}
L.time = types.SimpleNamespace(time=lambda: NOW[0], strftime=_time.strftime, gmtime=_time.gmtime, sleep=_time.sleep)
L.print = lambda *a, **k: None
L.run_files = lambda: [RUNS[r][0] for r in sorted(WIN) if WIN[r][0][0] <= NOW[0]]
def _read_run(p):
    run = os.path.basename(p)[9:-4]; walls, rows = WIN[run]
    return rows[:bisect.bisect_right(walls, NOW[0])]
L.read_run = _read_run
def _snaps(kind, run):
    if kind != "hud" or run not in WIN: return []
    walls, rows = WIN[run]; j = bisect.bisect_right(walls, NOW[0])
    if not j: return []
    n0, nmax = int(rows[0]["n"]), int(rows[j - 1]["n"]); out = []
    for n, c in HUDR.get(run, []):
        if n0 <= n <= nmax:
            hp = f"hud_{run}_{n:07d}.png"; L._HUD_CACHE[hp] = c; out.append(hp)
    return out
L.snaps = _snaps

def replay(gid, feed, st0, end):
    snaps = []
    walls = [ts(x["wall"]) if x.get("wall") else ts(x["ts"]) + 60 for x in feed]
    t = st0 + 14 * 60
    while t <= end + 300:
        NOW[0] = t
        fd = feed[:bisect.bisect_right(walls, t)]
        if fd and any(x["state"] == "in_game" for x in fd):
            finished = fd[-1]["state"] == "finished"
            Lg, measured, clock_of, _ = L.game_clock(st0, ts(fd[-1]["ts"]) if finished else t)
            towers, err = L.towers_named(gid, fd, finished, round(Lg, 1) if (Lg is not None and measured) else L.LAG, clock_of, st0)
            if towers: snaps.append((t, {tm: {x["site"]: x["sec"] for x in towers[tm]} for tm in "BR"}))
        t += STEP
    return snaps

def published(gid):
    out = []
    for l in open(SLOG, encoding="utf-8"):
        if f'"{gid}"' not in l: continue
        d = json.loads(l)
        if d.get("game") == gid and d.get("towersLost") and d.get("status") in ("in_game", "finished"):
            out.append((ts(d["updated"]), {tm: {x["site"]: x["sec"] for x in d["towersLost"].get(tm, [])} for tm in "BR"}))
    return out

fmt = lambda x: f"wrong {x['wrongSec']:>4}s {x['wrongNames']} flicker {x['flicker']} ? {x['unnamedSec']}s final miss {x['finalMissing']} extra {x['finalExtra']} time err med {x['timeErrMedian']} >60s {x['timeErrOver60']}/{x['timed']}"
res = {}; tot = {k: {"wrongSec": 0, "wrongNames": 0, "flicker": 0, "unnamedSec": 0, "finalMissing": 0, "finalExtra": 0, "timeErrOver60": 0, "timed": 0} for k in ("new", "old")}
tchk = [[], 0]
for g in sorted(glob.glob(os.path.join(ARCH, "*.json"))):
    a = json.load(open(g, encoding="utf-8")); gid = a["gameId"]
    if ONLY and gid not in ONLY: continue
    fp = os.path.join(DATA, f"feed_{gid}.jsonl")
    if not os.path.exists(fp): continue
    feed = [json.loads(l) for l in open(fp, encoding="utf-8")]
    ig = [x for x in feed if x["state"] == "in_game"]
    if not ig: continue
    st0, end = ts(ig[0]["ts"]), ts(feed[-1]["ts"])
    WIN.clear(); WIN.update(window(st0 - 1800, end + 600))
    if not WIN: continue
    tw = {tm: truth(WIN, tm, st0, end + END_SCREEN) for tm in "BR"}
    tru = {tm: tw[tm][0] for tm in "BR"}; stand = {tm: tw[tm][1] for tm in "BR"}
    if not any(tru.values()): continue
    cmap = clock_map(WIN)
    if CHECK:
        df, nf, nt = check_truth(feed, tru, cmap, st0); tchk[0] += df; tchk[1] += nf - nt and 1
        print(f"{gid} {a['teams']['B']}-{a['teams']['R']} feed {nf} truth {nt}  truth - feed (s): {df}", flush=True); continue
    fw = [ts(x["wall"]) if x.get("wall") else ts(x["ts"]) + 60 for x in feed]
    def lost_at(tm, w, feed=feed, fw=fw):
        i = bisect.bisect_right(fw, w) - 1
        return feed[i]["R" if tm == "B" else "B"]["t"] if i >= 0 else 0
    t1 = _time.time(); sn = replay(gid, feed, st0, end); r = {"teams": a["teams"], "new": score(sn, tru, stand, cmap, lost_at), "snaps": sn}
    if SLOG:
        pub = published(gid)
        if pub: r["old"] = score(pub, tru, stand, cmap, lost_at)
    r["secs"] = round(_time.time() - t1); res[gid] = r
    for k in ("new", "old"):
        if k in r:
            for f in tot[k]: tot[k][f] += len(r[k][f]) if f == "wrongNames" else r[k][f]
    print(f"{gid} {a['teams']['B']}-{a['teams']['R']}  NEW {fmt(r['new'])}" + (f"  | OLD {fmt(r['old'])}" if "old" in r else "") + f"  ({r['secs']}s)", flush=True)
if CHECK:
    d = np.abs(np.array(tchk[0]))
    print(f"games where truth and feed count differ: {tchk[1]}; pairs {len(d)}: |truth - feed| median {np.median(d):.0f} s, "
          f"<=30 s {int((d <= 30).sum())}, <=60 s {int((d <= 60).sum())}, >60 s {int((d > 60).sum())}")
else: print("TOTAL", json.dumps(tot))
if OUT: json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
