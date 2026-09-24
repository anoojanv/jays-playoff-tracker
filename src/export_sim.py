"""Export the model for the in-browser simulator.

The browser re-simulates the focus conference only. Nothing the page lets a reader change
— Toronto's points, a rival running hot or cold — can move a game between two clubs of the
other conference, so those games are left out and each re-run stays fast. The other
conference's champion, needed for the Final, is sampled from the Python run.
"""
import json
import data as D
import model
from model import (FOCUS, TEAMS, idx, CONF, FOCUS_CONF, CONF_TEAMS, games, p_home,
                   talent, SERIES)

st = model.load_state()
R = json.load(open("results.json"))

gH, gA, gP, gJ = [], [], [], []
slot = 0
for i, (date, a, h) in enumerate(games):
    if CONF[a] != FOCUS_CONF and CONF[h] != FOCUS_CONF:
        continue
    gH.append(idx[h]); gA.append(idx[a]); gP.append(round(float(p_home[i]), 5))
    if FOCUS in (a, h):
        gJ.append(slot); slot += 1
    else:
        gJ.append(-1)

conf_idx = [idx[t] for t in CONF_TEAMS[FOCUS_CONF]]
divs = [[idx[t] for t in D.DIVISIONS[d]] for d in D.CONFERENCES[FOCUS_CONF]]

# the other conference's champion, as the Python run found it in the seasons where
# Toronto qualified — the only thing the Final needs from the other side
B = R.get("bracket") or {}
other = "Wcf" if FOCUS_CONF == "Eastern" else "Ecf"
champs = [{"t": idx[r["team"]], "p": r["p"],
           "pts": round(R["teams"][r["team"]]["proj_pts"], 2)}
          for r in (B.get("nodes", {}).get(other) or [])]

out = {
    "teams": TEAMS,
    "names": [D.TEAMS[t]["name"] for t in TEAMS],
    "confIdx": conf_idx, "divs": divs, "divNames": list(D.CONFERENCES[FOCUS_CONF]),
    "basePts": [D.points(t) for t in TEAMS],
    "baseRw": [D.TEAMS[t]["rw"] for t in TEAMS],
    "gH": gH, "gA": gA, "gP": gP, "gJ": gJ,
    "nFocusGames": slot,
    "focusIdx": idx[FOCUS],
    "talent": [round(float(talent[t]), 6) for t in TEAMS],
    "hfa": model.HFA_ODDS, "pOt": model.P_OT, "series": SERIES,
    "otherChamps": champs,
    "baselineOdds": float(st.focus_in.mean()),
}
json.dump(out, open("simdata.json", "w"), separators=(",", ":"))
print(f"browser games {len(gH)} of {len(games)} (focus conference only)  "
      f"focus games {slot}")
print(f"simdata.json {len(json.dumps(out, separators=(',', ':'))) / 1024:.1f} KB  "
      f"· python baseline {out['baselineOdds'] * 100:.2f}%")
