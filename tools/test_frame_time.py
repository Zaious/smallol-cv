# Checks for the frame clock and the replay check (2026-10-27). Run: python tools/test_frame_time.py
import os, sys, datetime as dt
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.argv = [sys.argv[0], "--dir", os.path.join(HERE, "..", "data", "_test")]
import live_service as L
import replay_banner as RB

iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

# 1. Frames dropped mid-run (a reconnect): the frame count falls 90 s behind the wall clock at n = 1000.
#    Each frame keeps its own time; a single anchor (what the service used before) would put frames before the
#    drop 90 s late.
t0 = 1_760_000_000.0
rows = [{"n": str(n), "wall_utc": iso(t0 + n + (90 if n >= 1000 else 0) + 0.3 * np.sin(n))} for n in range(2000)]
wt = L.frame_clock(rows)
for n in (0, 500, 990, 1010, 1500, 1999):
    want = t0 + n + (90 if n >= 1000 else 0)
    assert abs(wt(n) - want) < 1.0, (n, wt(n) - want)
old_anchor = float(np.median([L.ts(r["wall_utc"]) - int(r["n"]) for r in rows[-600:]]))
assert abs((500 + old_anchor) - (t0 + 500)) > 80          # the old way: 90 s off before the drop
print("frame_clock: per-frame times follow a 90 s jump; the old single anchor was 90 s off")

# 2. Replay label: blue badge + white capitals vs the objective timer box (purple and green icons, dark ground).
rep = np.zeros((70, 300, 3), np.uint8); rep[5:65, 5:105] = (230, 60, 10)            # saturated blue (BGR)
for x in range(170, 300, 22): rep[15:55, x:x + 14] = (240, 240, 240)                 # white letters
normal = np.full((70, 300, 3), 40, np.uint8); normal[10:60, 10:55] = (160, 60, 140); normal[10:60, 60:105] = (40, 170, 120)
assert RB.is_replay(rep) and not RB.is_replay(normal)
badge_only = rep.copy(); badge_only[:, 110:] = 0                                      # badge with a sponsor bar: not a replay
assert not RB.is_replay(badge_only)
print("replay_banner: replay corner yes, timer box no, badge without the label no")
print("ok")
