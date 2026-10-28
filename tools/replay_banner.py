# Is the broadcast showing a replay? The 2026 Worlds broadcast puts a "REPLAY" label in the top-left corner during
# replays: a saturated blue Worlds badge, then white capitals on black. During a replay the minimap shows the past,
# so towers already down look standing again (2026-10-25 GEN vs LYON 29:00-31:00: two inner towers "stood" for
# 90 s after the feed had them down, and the service named them late).
# Input: the top-left 300x70 corner (what live_classify saves as obj_<run>_<n>.png, every 5 frames).
import cv2, numpy as np

def scores(corner):
    """(share of saturated blue in the badge, share of bright white in the text area)."""
    hsv = cv2.cvtColor(corner, cv2.COLOR_BGR2HSV)
    badge = hsv[8:62, 8:100]
    blue = ((badge[..., 0] >= 100) & (badge[..., 0] <= 125) & (badge[..., 1] >= 150) & (badge[..., 2] >= 120)).mean()
    text = hsv[10:60, 165:300]
    white = ((text[..., 1] <= 50) & (text[..., 2] >= 200)).mean()
    return float(blue), float(white)

def is_replay(corner):
    if corner is None or corner.shape[0] < 62 or corner.shape[1] < 300: return False
    blue, white = scores(corner)
    return blue >= 0.4 and white >= 0.12
