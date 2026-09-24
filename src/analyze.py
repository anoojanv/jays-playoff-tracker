"""What it takes: the rest-of-season points Toronto needs, and at what pace.

The baseball version of this file broke the run-in into three-game series and asked what a
qualifying season took from each. Hockey has no series in the regular season — clubs meet
for one game and move on — so what is left is the total and the pace.
"""
import json, math
import numpy as np
import data as D
import model
from model import FOCUS, rem

st = model.load_state()
fin, fpts = st.focus_in, st.focus_pts
R = json.load(open("results.json"))

NQ = int(fin.sum())
GL = int(rem[FOCUS])
now = D.points(FOCUS)
need = R["ros_needed"]


def cond(vals, mask, default):
    return float(vals[mask].mean()) if mask.any() else float(default)


gained = fpts.astype(np.int32) - now
out = {
    "cut_target": R["cut_target"],
    "ros_needed_pts": need,
    "ros_games": GL,
    "ros_pace": (need / (2 * GL)) if GL else 0.0,       # as a points percentage
    "season_pace": (now / (2 * D.played(FOCUS))) if D.played(FOCUS) else None,
    "gained_if_qualify": cond(gained, fin, 2 * GL),
    "gained_all": float(gained.mean()),
    "n_qualifying": NQ,
}
json.dump(out, open("path.json", "w"), indent=1)
print(f"to reach {R['cut_target']} points: {need} of the {2 * GL} available "
      f"({out['ros_pace']:.3f} pace) · qualifying seasons take "
      f"{out['gained_if_qualify']:.1f}, all seasons {out['gained_all']:.1f}")
