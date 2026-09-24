"""
Leafs playoff-chase Monte Carlo — runs the model and writes results.json.

The model itself lives in model.py; this file turns a set of simulated seasons into the
numbers the page shows, and saves the arrays the downstream scripts need so they read the
SAME seasons instead of running their own.
"""
import json, math
import numpy as np
import data as D
import model
from model import (FOCUS, NSIM, TEAMS, idx, CONF, DIV, CONF_TEAMS, FOCUS_CONF, FOCUS_DIV,
                   CLUSTER, RIVALS, talent, games, rem, focus_game_ix, momentum,
                   strength_of_schedule, PROJ, matchup)

st = model.simulate()
model.save_state(st)

J = idx[FOCUS]
fin, fpts = st.focus_in, st.focus_pts
cols = np.arange(st.nsim)

out = {"as_of": D.AS_OF, "nsim": NSIM, "preseason": D.PRESEASON,
       "season_games": D.SEASON_GAMES, "focus": FOCUS,
       "focus_name": D.TEAMS[FOCUS]["name"], "focus_city": D.TEAMS[FOCUS]["city"],
       "focus_conf": FOCUS_CONF, "focus_div": FOCUS_DIV}

T = D.TEAMS[FOCUS]
out["record"] = {"w": T["w"], "l": T["l"], "otl": T["otl"], "pts": D.points(FOCUS),
                 "gp": D.played(FOCUS), "gf": T["gf"], "ga": T["ga"], "rw": T["rw"]}
out["games_left"] = int(rem[FOCUS])
out["talent"] = {t: round(talent[t], 4) for t in TEAMS}
out["cluster"] = CLUSTER
out["momentum"] = momentum()
_sos = strength_of_schedule()
out["sos"] = {t: (round(v, 4) if v is not None else None) for t, v in _sos.items()}
out["league"] = {"p_ot": model.P_OT, "home_win": model.HOME_WIN}

out["odds"] = {
    "playoff": float(fin.mean()),
    "division": float((st.div_rank[J] == 1).mean()),
    "top3": float((st.div_rank[J] <= 3).mean()),
    "wildcard": float((st.wc_rank[J] > 0).mean()),
}
out["proj_pts"] = {"mean": float(fpts.mean()),
                   "p10": float(np.percentile(fpts, 10)),
                   "p50": float(np.percentile(fpts, 50)),
                   "p90": float(np.percentile(fpts, 90))}

# every club, for the race table and the bracket's names
out["teams"] = {}
for t in TEAMS:
    r = D.TEAMS[t]
    out["teams"][t] = {
        "name": r["name"], "city": r["city"], "conf": r["conf"], "div": r["div"],
        "w": r["w"], "l": r["l"], "otl": r["otl"], "pts": D.points(t), "gp": D.played(t),
        "gd": r["gf"] - r["ga"], "rw": r["rw"],
        "playoff": float(st.playoff[idx[t]].mean()),
        "division": float((st.div_rank[idx[t]] == 1).mean()),
        "proj_pts": float(st.pts[idx[t]].mean()),
        "proj_analytic": round(PROJ[t], 1),
        "games_left": int(rem[t]),
    }

# ---------------------------------------------------------------- how many points
# P(in) by final point total. The window follows the simulated distribution.
lo = int(np.percentile(fpts, 0.5))
hi = int(np.percentile(fpts, 99.5))
curve = {}
for p in range(lo, hi + 1):
    m = fpts == p
    if m.sum() >= max(60, st.nsim // 800):
        curve[p] = [float(fin[m].mean()), int(m.sum())]
out["pts_curve"] = curve
out["pts_10"] = min((p for p, (v, n) in curve.items() if v >= .10), default=None)
out["pts_50"] = min((p for p, (v, n) in curve.items() if v >= .50), default=None)
out["pts_90"] = min((p for p, (v, n) in curve.items() if v >= .90), default=None)

# the cut line: the points of the conference's second wild card, season by season
crows = np.array([idx[t] for t in CONF_TEAMS[FOCUS_CONF]])
wc2 = crows[np.argmax(st.wc_rank[crows] == 2, axis=0)]
cut = st.pts[wc2, cols]
out["cut_pts"] = {"mean": float(cut.mean()), "p50": float(np.percentile(cut, 50)),
                  "p10": float(np.percentile(cut, 10)),
                  "p90": float(np.percentile(cut, 90))}
_target = int(math.ceil(out["cut_pts"]["p50"]))
out["cut_target"] = _target
out["ros_needed"] = max(0, min(2 * out["games_left"], _target - D.points(FOCUS)))

# ---------------------------------------------------------------- per-game leverage
lev = []
for k, i in enumerate(focus_game_ix):
    date, a, h = games[i]
    opp = a if h == FOCUS else h
    w = st.focus_won[k]
    p_w = float(fin[w].mean()) if w.any() else 0.0
    p_l = float(fin[~w].mean()) if (~w).any() else 0.0
    lev.append({"date": date, "opp": opp, "home": h == FOCUS, "k": k,
                "p_win": p_w, "p_loss": p_l, "leverage": p_w - p_l,
                "p_game": round(matchup(talent[FOCUS], talent[opp], h == FOCUS), 3)})
out["leverage"] = lev

if lev:
    _d, _a, _h = games[focus_game_ix[0]]
    _t = D.TIMES.get(f"{_d}|{_a}|{_h}") or {}
    _o = lev[0]["opp"]
    out["next_game"] = dict(lev[0], utc=_t.get("utc"), state=_t.get("state"),
                            opp_name=D.TEAMS[_o]["name"],
                            opp_record=f'{D.TEAMS[_o]["w"]}-{D.TEAMS[_o]["l"]}-'
                                       f'{D.TEAMS[_o]["otl"]}')
else:
    out["next_game"] = None

# the next ten games, at every points total Toronto could take from them
nnext = min(10, len(focus_game_ix))
nw = st.focus_won[:nnext]
npts = (nw.astype(np.int16) * 2 + ((~nw) & st.focus_ot[:nnext])).sum(axis=0)
out["next_n"] = nnext
out["next_pts"] = {int(p): [float(fin[npts == p].mean()), float((npts == p).mean())]
                   for p in range(2 * nnext + 1) if (npts == p).sum() >= 100}

# ---------------------------------------------------------------- where the race stands
def _standing_key(t):
    r = out["teams"][t]
    # points, then games in hand, then regulation wins; projection breaks the preseason
    return (-r["pts"], r["gp"], -r["rw"], -PROJ[t])


conf_order = sorted(CONF_TEAMS[FOCUS_CONF], key=_standing_key)
out["race"] = {"conference": FOCUS_CONF, "divisions": list(D.CONFERENCES[FOCUS_CONF])}
_top3 = {}
for d in D.CONFERENCES[FOCUS_CONF]:
    _top3[d] = sorted(D.DIVISIONS[d], key=_standing_key)[:3]
_in_div = {t for v in _top3.values() for t in v}
_wc = [t for t in conf_order if t not in _in_div]
out["race"]["top3"] = _top3
out["race"]["wildcard"] = _wc

# points back of the last playoff position, as things stand
_line_team = _wc[1] if len(_wc) > 1 else None
_first_out = _wc[2] if len(_wc) > 2 else None
_mine = D.points(FOCUS)
if FOCUS in _in_div or FOCUS in _wc[:2]:
    ref = _first_out
    out["line"] = {"in": True, "vs": ref,
                   "gap": (_mine - D.points(ref)) if ref else 0,
                   "gp_diff": (D.played(ref) - D.played(FOCUS)) if ref else 0}
else:
    ref = _line_team
    out["line"] = {"in": False, "vs": ref,
                   "gap": (D.points(ref) - _mine) if ref else 0,
                   "gp_diff": (D.played(ref) - D.played(FOCUS)) if ref else 0}
out["line"]["max_pts"] = _mine + 2 * out["games_left"]

_div = sorted(D.DIVISIONS[FOCUS_DIV], key=_standing_key)
out["division"] = {"name": FOCUS_DIV, "leader": _div[0], "rank": _div.index(FOCUS) + 1,
                   "back": D.points(_div[0]) - _mine if _div[0] != FOCUS else 0,
                   "odds": out["odds"]["division"]}

# ---------------------------------------------------------------- scoreboard watching
around = model.around_the_league(st)
_first = around[0]["date"] if around else None
_soon = [g for g in around if _first and g["date"] <= (
    __import__("datetime").date.fromisoformat(_first)
    + __import__("datetime").timedelta(days=10)).isoformat()]
_top = sorted(around, key=lambda g: -g["leverage"])[:50]
_keep = {(g["date"], g["away"], g["home"]): g for g in _soon + _top}
out["around"] = sorted(_keep.values(), key=lambda g: (g["date"], -g["leverage"]))
out["around_next_date"] = _first

dep = {}
for t in RIVALS:
    tp = st.pts[idx[t]]
    lo_, hi_ = np.percentile(tp, 25), np.percentile(tp, 75)
    a = fin[tp <= lo_].mean()
    b = fin[tp >= hi_].mean()
    dep[t] = {"if_rival_cold": float(a), "if_rival_hot": float(b),
              "swing": float(a - b), "cold_pts": float(lo_), "hot_pts": float(hi_)}
out["dependency"] = dep

passed = np.zeros(st.nsim, dtype=np.int8)
for t in CLUSTER:
    passed += st.score[J] > st.score[idx[t]]
out["pass_given_in"] = float(passed[fin].mean()) if fin.any() else 0.0

out["bracket"] = model.bracket(st)

with open("results.json", "w") as f:
    json.dump(out, f, indent=1)

print(f"games modelled: {len(games)}   sims: {NSIM}   "
      f"P(OT) {model.P_OT:.3f}   home-ice odds {model.HFA_ODDS:.3f}")
print(f"{FOCUS} talent {talent[FOCUS]:.4f}  proj {out['proj_pts']['mean']:.1f} pts")
print(f"PLAYOFF ODDS: {out['odds']['playoff']*100:.1f}%  "
      f"(division {out['odds']['division']*100:.1f}%, "
      f"wild card {out['odds']['wildcard']*100:.1f}%)")
print(f"points needed: 10% @ {out['pts_10']}  50% @ {out['pts_50']}  90% @ {out['pts_90']}"
      f"   · cut line median {out['cut_pts']['p50']:.0f}")
_b = out["bracket"]
if _b:
    print(f"if they get in: {_b['best_label']} ({_b['best_seat_p']*100:.0f}%) vs "
          f"{_b['best_seat_opponent']} · road R1 {_b['road']['r1']*100:.0f}% "
          f"R2 {_b['road']['r2']*100:.0f}% CF {_b['road']['cf']*100:.0f}% "
          f"Cup {_b['road']['cup']*100:.1f}%")
print("\nconference odds:")
for t in sorted(CONF_TEAMS[FOCUS_CONF], key=lambda x: -out["teams"][x]["playoff"]):
    v = out["teams"][t]
    print(f"  {t:<4} {v['w']}-{v['l']}-{v['otl']} {v['pts']:>3}pts  talent {talent[t]:.3f}"
          f"  proj {v['proj_pts']:5.1f}  {v['playoff']*100:5.1f}%")
print("\ntop leverage games:")
for g in sorted(lev, key=lambda x: -x["leverage"])[:6]:
    print(f"  {g['date']} {'vs' if g['home'] else '@ '} {g['opp']:<4} "
          f"{g['leverage']*100:.2f} pts")
