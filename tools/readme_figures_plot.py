# The README's figures, part 2 (anywhere with matplotlib): draws docs/media/*.png from the JSON that
# tools/readme_figures_data.py made on the server. Our own charts of our own readings; the only
# broadcast picture is the annotated minimap crop.
# Usage: python tools/readme_figures_plot.py <game.json> <out dir>
import sys, os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
import cv2

src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
d = json.load(open(src, encoding="utf-8"))
T = d["teams"]; BLUE, RED, GREY, AMBER, INK, MUTED = "#4C93E6", "#E0574C", "#8B93A1", "#E8B04A", "#15171C", "#565D69"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#C9CDD4", "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})
mmss = lambda s: f"{int(s) // 60}:{int(s) % 60:02d}"
VIDEO_LAG = 46   # the stream's delay behind the feed the service assumes for Twitch

# Feed time (seconds since the feed's first in-game frame) -> game clock, through the scoreboard reads.
hud = np.array(d["hud"]); hx, hc = hud[:, 0], hud[:, 1]
def feed_to_clock(sec):
    v = sec + VIDEO_LAG; i = np.argsort(np.abs(hx - v))[:5]
    return float(v + np.median(hc[i] - hx[i]))

# ---------- 1. towers: per-site readings, the feed's events, the names given ----------
SITES = [f"{t}_{l}_{k}" for t in "BR" for l in ("top", "mid", "bot") for k in ("outer", "inner", "inhib_tower")] + [f"{t}_nexus_t{i}" for t in "BR" for i in (1, 2)]
SITES = [s for s in SITES if s in d["series"]]
fig, ax = plt.subplots(figsize=(10, 6.2), dpi=150)
col = {"A": None, "D": "#3A3F48", "O": "#F3E3B5"}
for i, s in enumerate(SITES):
    team = BLUE if s[0] == "B" else RED
    pts = d["series"][s]
    for (t0, st), (t1, _) in zip(pts, pts[1:] + [[pts[-1][0] + 5, None]]):
        ax.add_patch(Rectangle((t0 / 60, i - 0.38), (t1 - t0) / 60, 0.76, color=col[st] or team, alpha=0.85 if st == "A" else 1, lw=0))
named = {f"{tm}_{x['site']}": x["sec"] for tm in "BR" for x in d["named"].get(tm, [])}
for s, sec in named.items():
    if s in SITES: ax.plot(sec / 60, SITES.index(s), marker="v", color=AMBER, markersize=8, markeredgecolor=INK, markeredgewidth=0.6, zorder=5)
for e in d["events"]:
    c = feed_to_clock(e["sec"]); rows = [i for i, s in enumerate(SITES) if s[0] == e["lost"]]
    ax.vlines(c / 60, min(rows) - 0.45, max(rows) + 0.45, color=BLUE if e["lost"] == "B" else RED, lw=1.2, linestyles=(0, (2, 2)), zorder=4)
ax.set_yticks(range(len(SITES)), [f"{T[s[0]]} {s[2:].replace('_tower', '').replace('_', ' ')}" for s in SITES], fontsize=8)
ax.invert_yaxis(); ax.set_xlabel("game clock (minutes)")
ax.set_xlim(0, max(p[0] for v in d["series"].values() for p in v) / 60 + 0.5)
ax.set_title(f"Which tower fell: minimap readings, one Worlds 2026 game ({T['B']} vs {T['R']}, {d['duration']})", loc="left", fontsize=11, color=INK)
from matplotlib.lines import Line2D
ax.legend(handles=[Rectangle((0, 0), 1, 1, color=BLUE, alpha=.85, label="standing (team colour on the icon)"), Rectangle((0, 0), 1, 1, color="#3A3F48", label="gone"),
                   Rectangle((0, 0), 1, 1, color="#F3E3B5", label="can't tell (a champion or effect on it)"),
                   Line2D([], [], color=GREY, ls=(0, (2, 2)), label="official feed: a tower of this team fell"),
                   Line2D([], [], marker="v", color=AMBER, ls="", markeredgecolor=INK, label="the service names it")],
          loc="lower left", fontsize=7.5, frameon=False, ncol=2, bbox_to_anchor=(0, -0.28))
fig.tight_layout(); fig.savefig(f"{out}/towers.png", bbox_inches="tight"); plt.close(fig)

# ---------- 2. the stream's delay: the scoreboard clock against the feed ----------
fig, ax = plt.subplots(figsize=(10, 3.6), dpi=150)
ax.plot(hx / 60, hc / 60, ".", color=BLUE, markersize=4, label="game clock read off the broadcast's scoreboard")
ax.plot(hx / 60, hx / 60, color=GREY, lw=1, ls=(0, (3, 3)), label="the official feed's time since its game started")
mid = len(hx) // 2
ax.annotate(f"{hx[mid] - hc[mid]:.0f} s behind", xy=(hx[mid] / 60, hc[mid] / 60), xytext=(hx[mid] / 60 + 2, hc[mid] / 60 - 6),
            arrowprops=dict(arrowstyle="->", color=MUTED), color=INK, fontsize=9)
ax.set_xlabel("minutes since the feed's game started"); ax.set_ylabel("minutes")
ax.set_title("Lining the stream up with the feed: the gap is the broadcast's delay plus loading, pauses and the stream's own lag", loc="left", fontsize=10, color=INK)
ax.legend(fontsize=8, frameon=False, loc="upper left")
fig.tight_layout(); fig.savefig(f"{out}/delay.png", bbox_inches="tight"); plt.close(fig)

# ---------- 3. the draft: each card, frame by frame ----------
fr = d["draft"]; t0 = fr[0]["t"]
fig, ax = plt.subplots(figsize=(10, 3.9), dpi=150)
slots = [(s, i) for s in "BR" for i in range(5)]
for r, (side, i) in enumerate(slots):
    run, start, said = None, None, None
    for k, f in enumerate(fr + [None]):
        c = None if f is None else next(c for c in f["cards"] if c["side"] == side and c["slot"] == i)
        key = None if c is None or not c["champ"] else (c["champ"], c["state"])
        if key != run:
            if run is not None:
                t_end = fr[k - 1]["t"] + 3 if f is None else f["t"]
                colr = (BLUE if side == "B" else RED) if run[1] == "locked" else AMBER
                ax.add_patch(Rectangle((start, r - 0.36), t_end - start, 0.72, color=colr, alpha=0.9 if run[1] == "locked" else 0.75, lw=0))
                if t_end - start > 12 and run[0] != said: said = run[0]; ax.text(start + 2, r, run[0], va="center", fontsize=7.5, color="white" if run[1] == "locked" else INK)
            run, start = key, (f["t"] if f else None)
ax.set_yticks(range(10), [f"{T[s]} card {i + 1}" for s, i in slots], fontsize=8)
ax.set_xlim(t0 - 5, 5); ax.set_ylim(9.6, -0.6); ax.set_xlabel("seconds before the game (in the last half minute the broadcast reorders the cards by role)")
ax.set_title("Reading the draft off the broadcast: each card's champion, hovering (amber) or locked (team colour)", loc="left", fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(f"{out}/draft.png", bbox_inches="tight"); plt.close(fig)

# ---------- 4. the minimap, annotated ----------
im = cv2.imread(src.replace(".json", "_minimap.png")); Z = 3
big = cv2.resize(im, None, fx=Z, fy=Z, interpolation=cv2.INTER_NEAREST)
rd = d["minimap"]["reading"]
for s in d["sites"]:
    x, y = int(s["x"] * Z), int(s["y"] * Z); st = rd[s["id"]]["state"]; r = 7 * Z
    c = {"A": (230, 147, 76) if s["id"][0] == "B" else (76, 87, 224), "D": (200, 200, 200), "O": (74, 176, 232)}[st]
    cv2.rectangle(big, (x - r, y - r), (x + r, y + r), (20, 20, 20), 4); cv2.rectangle(big, (x - r, y - r), (x + r, y + r), c, 2)
    if st == "D": cv2.line(big, (x - r, y - r), (x + r, y + r), c, 2); cv2.line(big, (x - r, y + r), (x + r, y - r), c, 2)
pad = np.full((big.shape[0] + 70, big.shape[1], 3), 245, np.uint8); pad[:big.shape[0]] = big
cv2.putText(pad, f"minimap at {mmss(d['minimap']['clock'])}: box = standing (team colour), X = gone, orange = can't tell", (12, big.shape[0] + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 40), 1, cv2.LINE_AA)
cv2.putText(pad, "each box: share of the team's colour in a 13x13 px patch, read once a second", (12, big.shape[0] + 56), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1, cv2.LINE_AA)
cv2.imwrite(f"{out}/minimap.png", pad)

# ---------- 5. the pipeline ----------
fig, ax = plt.subplots(figsize=(10, 3.3), dpi=150); ax.set_xlim(0, 100); ax.set_ylim(0, 34); ax.axis("off")
def box(x, y, w, h, title, sub, fc="#FFFFFF"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec="#C9CDD4", lw=1))
    ax.text(x + w / 2, y + h - 2.6, title, ha="center", va="top", fontsize=9.5, weight="bold", color=INK)
    ax.text(x + w / 2, y + h - 6.6, sub, ha="center", va="top", fontsize=7.5, color=MUTED, linespacing=1.35)
def arrow(x0, y0, x1, y1): ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.1))
box(1, 19, 18, 13, "Official stream", "Twitch, 1080p\n(yt-dlp + ffmpeg)")
box(24, 19, 22, 13, "One frame a second", "minimap crop, draft cards,\nscoreboard clock, banners")
box(51, 19, 22, 13, "Computer vision", "OpenCV: team-colour masks,\nSIFT + template matching")
box(1, 2, 18, 13, "Official live feed", "score, gold, kills,\ndrakes, Barons, items")
box(24, 2, 22, 13, "Line them up", "the scoreboard clock gives\nthe stream's delay")
box(51, 2, 22, 13, "Merge", "which tower fell, the draft,\nthe Herald + the feed's numbers")
box(78, 10, 21, 14, "state.json", "every 5 s, read by the\ndesktop app", fc="#FFF6E3")
arrow(19, 25.5, 24, 25.5); arrow(46, 25.5, 51, 25.5); arrow(62, 19, 62, 15); arrow(19, 8.5, 24, 8.5); arrow(46, 8.5, 51, 8.5); arrow(73, 8.5, 78, 14)
ax.text(1, 33.6, "smallol-cv on a cloud server, around the clock", fontsize=10, color=INK, weight="bold", va="bottom")
fig.savefig(f"{out}/pipeline.png", bbox_inches="tight"); plt.close(fig)
print("written", sorted(os.listdir(out)))
