"""Model sensitivity: how much does Toronto's number depend on modelling choices?

Each specification rebuilds talent or the game model and re-runs the same simulation
(model.simulate), rather than keeping a second copy of it that could quietly drift.
"""
import json
import numpy as np
import model
from model import FOCUS, idx, build_talent

NSIM = 12_000
J = idx[FOCUS]

SPECS = [
    ("Primary model",                              dict(),                                   {}),
    ("Goal-differential purist (100% Pythag)",     dict(pyth_weight=1.0),                    {}),
    ("Record purist (0% Pythag)",                  dict(pyth_weight=0.0),                    {}),
    ("This season only (no prior)",                dict(prior_weight=0.0),                   {}),
    ("Last season counts double",                  dict(prior_weight=80.0),                  {}),
    ("Light regression (20 games)",                dict(reg_prior=20.0),                     {}),
    ("Heavy regression (70 games)",                dict(reg_prior=70.0),                     {}),
    ("No home ice",                                dict(),                                   {"hfa": 1.0}),
    ("More overtime (30%)",                        dict(),                                   {"p_ot": 0.30}),
    ("Less overtime (20%)",                        dict(),                                   {"p_ot": 0.20}),
]

res = []
for i, (label, tkw, skw) in enumerate(SPECS):
    tal = build_talent(**tkw) if tkw else None
    st = model.simulate(nsim=NSIM, seed=900 + i, tal=tal,
                        hfa=skw.get("hfa", model.HFA_ODDS), p_ot=skw.get("p_ot", model.P_OT))
    odds = float(st.focus_in.mean())
    res.append({"label": label, "odds": odds, "proj_pts": float(st.focus_pts.mean()),
                "talent": round((tal or model.talent)[FOCUS], 4),
                "primary": label == "Primary model"})
    print(f"{odds*100:5.1f}%   proj {res[-1]['proj_pts']:5.1f} pts   {label}")

vals = [r["odds"] for r in res]
print(f"\nrange {min(vals)*100:.1f}% - {max(vals)*100:.1f}%   median {np.median(vals)*100:.1f}%")
json.dump({"scenarios": res, "lo": min(vals), "hi": max(vals),
           "median": float(np.median(vals))}, open("ensemble.json", "w"), indent=1)
