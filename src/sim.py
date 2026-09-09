"""
Blue Jays playoff-chase Monte Carlo — runs the model and writes results.json.

The model itself lives in model.py; this file is the part that turns a set of simulated
seasons into the numbers the page shows. It also saves the simulated arrays so analyze.py
and export_sim.py can read the SAME seasons instead of running their own.
"""
import json
import numpy as np
import data as D
import model
from model import (JAYS, NSIM, TEAMS, AL_TEAMS, CLUSTER, RIVALS, talent, games,
                   idx, rem, series, jays_game_ix, pythagenpat, momentum,
                   strength_of_schedule)

st = model.simulate()
model.save_state(st)

wins, score, wc_score = st.wins, st.score, st.wc_score
div_winner, wc, playoff = st.div_winner, st.wc, st.playoff
jays_in, jays_wins, jays_won = st.jays_in, st.jays_wins, st.jays_won
J = idx[JAYS]

# ---------------------------------------------------------------- outputs
out = {}
out["as_of"] = D.AS_OF
out["nsim"] = NSIM
out["record"] = {"w": D.AL[JAYS][0], "l": D.AL[JAYS][1],
                 "rs": D.AL[JAYS][2], "ra": D.AL[JAYS][3]}
out["games_left"] = int(rem[JAYS])
out["talent"] = {t: round(talent[t], 4) for t in AL_TEAMS}
out["cluster"] = CLUSTER
# recent form against what the model expected; None when there is nothing to measure
out["momentum"] = momentum()
# descriptive: what a league-average club would win against each remaining
# schedule. Already priced into the odds game by game; this just exposes it.
_sos = strength_of_schedule()
out["sos"] = {t: (round(v, 4) if v is not None else None) for t, v in _sos.items()}
out["pythag_record"] = {}
for t in AL_TEAMS:
    w, l, rs, ra = D.AL[t]
    pw = pythagenpat(rs, ra, w + l) * (w + l)
    out["pythag_record"][t] = [round(pw, 1), round(w + l - pw, 1)]

out["odds"] = {
    "playoff": float(jays_in.mean()),
    "division": float(div_winner[J].mean()),
    "wildcard": float(wc[J].mean()),
}
out["proj_wins"] = {
    "mean": float(jays_wins.mean()),
    "p10": float(np.percentile(jays_wins, 10)),
    "p50": float(np.percentile(jays_wins, 50)),
    "p90": float(np.percentile(jays_wins, 90)),
}

# rival odds
out["rivals"] = {}
for t in AL_TEAMS:
    out["rivals"][t] = {
        "w": D.AL[t][0], "l": D.AL[t][1], "rd": D.AL[t][2] - D.AL[t][3],
        "playoff": float(playoff[idx[t]].mean()),
        "proj_w": float(wins[idx[t]].mean()),
        "games_left": int(rem[t]),
    }

# win-total -> P(in) curve  (the "how many wins do we need" chart)
# the window follows the simulated distribution rather than a fixed 75-97, which
# silently truncated the curve for a club on pace for 98+
lo_w = int(np.percentile(jays_wins, 0.5))
hi_w = int(np.percentile(jays_wins, 99.5))
curve = {}
for w in range(lo_w, hi_w + 1):
    m = jays_wins == w
    if m.sum() >= 150:
        curve[w] = [float(jays_in[m].mean()), int(m.sum())]
out["win_curve"] = curve
# threshold: smallest win total that is >=50% / >=90% to qualify
out["wins_50"] = min((w for w, (p, n) in curve.items() if p >= .50), default=None)
out["wins_90"] = min((w for w, (p, n) in curve.items() if p >= .90), default=None)
out["wins_10"] = min((w for w, (p, n) in curve.items() if p >= .10), default=None)

# ---------------------------------------------------------------- series analysis
out["series"] = []
for s in series:
    swins = jays_won[s["ix"]].sum(axis=0)
    n = len(s["ix"])
    conds = {}
    for w in range(n + 1):
        m = swins == w
        if m.sum() >= 100:
            conds[w] = [float(jays_in[m].mean()), float(m.mean())]
    sweep_hi = conds.get(n, [None])[0]
    sweep_lo = conds.get(0, [None])[0]
    out["series"].append({
        "opp": s["opp"], "home": s["home"], "start": s["start"], "end": s["end"],
        "n": n,
        "opp_talent": round(talent[s["opp"]], 4),
        "opp_record": f"{TEAMS[s['opp']][0]}-{TEAMS[s['opp']][1]}",
        "exp_wins": float(swins.mean()),
        "cond": conds,
        "swing": (sweep_hi - sweep_lo) if (sweep_hi is not None and sweep_lo is not None) else None,
        "is_rival": s["opp"] in CLUSTER,
    })

# how many of the Jays' remaining games are against the wild-card cluster
out["cluster_games"] = int(sum(len(s["ix"]) for s in series if s["opp"] in CLUSTER))

# per-game leverage: P(in | win) - P(in | loss), plus which series the game belongs to
# so the page can dedupe by series rather than by opponent-and-month
_series_of = {}
for si, s in enumerate(series):
    for k in s["ix"]:
        _series_of[k] = si
lev = []
for k, i in enumerate(jays_game_ix):
    date, a, h = games[i]
    opp = a if h == JAYS else h
    w = jays_won[k]
    p_w = float(jays_in[w].mean()) if w.any() else 0.0
    p_l = float(jays_in[~w].mean()) if (~w).any() else 0.0
    lev.append({
        "date": date, "opp": opp, "home": (h == JAYS), "series": _series_of[k],
        "p_win": p_w, "p_loss": p_l, "leverage": p_w - p_l,
    })
out["leverage"] = lev

# the next game, with first pitch and game state when the feed supplied them
if lev:
    _date, _a, _h = games[jays_game_ix[0]]
    _t = D.TIMES.get(f"{_date}|{_a}|{_h}") or {}
    out["next_game"] = dict(lev[0], utc=_t.get("utc"), state=_t.get("state"),
                            opp_record=f"{TEAMS[lev[0]['opp']][0]}-{TEAMS[lev[0]['opp']][1]}")
else:
    out["next_game"] = None

# ---------------------------------------------------------------- the fan's numbers
# Magic and tragic numbers as fans actually quote them: 163 minus one club's wins minus
# the other's losses, against the specific club on the other side of the line. Read off
# the standings, not the simulation, so they agree with every broadcast.
_pct = {t: model._winpct(t) for t in AL_TEAMS}
_leaders = {max(m, key=lambda t: _pct[t]) for m in D.DIVISIONS.values()}
_own_div = next(d for d, m in D.DIVISIONS.items() if JAYS in m)
_div_order = sorted(D.DIVISIONS[_own_div], key=lambda t: _pct[t], reverse=True)
_wc_order = [t for t in sorted(AL_TEAMS, key=lambda t: _pct[t], reverse=True)
             if t not in _leaders]
JW, JL = D.AL[JAYS][:2]
if JAYS in _leaders:
    _vs = _div_order[1]
    out["line"] = {"mode": "magic", "vs": _vs, "n": max(0, 163 - JW - D.AL[_vs][1]),
                   "what": f"to clinch the {_own_div}"}
elif JAYS in _wc_order[:3]:
    _vs = _wc_order[3]
    out["line"] = {"mode": "magic", "vs": _vs, "n": max(0, 163 - JW - D.AL[_vs][1]),
                   "what": "to finish ahead of the first club out"}
else:
    _vs = _wc_order[2]
    out["line"] = {"mode": "tragic", "vs": _vs, "n": max(0, 163 - D.AL[_vs][0] - JL),
                   "what": "before the last wild card is out of reach"}
_lead = _div_order[0]
out["division"] = {
    "name": _own_div, "leader": _lead, "rank": _div_order.index(JAYS) + 1,
    "gb": max(0.0, model.games_back(_lead)) if _lead != JAYS else 0.0,
    "lead_by": (model.games_back(_div_order[1]) * -1) if _lead == JAYS else 0.0,
    "odds": out["odds"]["division"],
}

# rival-dependency: how much Jays odds move on a rival's finish
dep = {}
for t in RIVALS:
    tw = wins[idx[t]]
    lo, hi = np.percentile(tw, 25), np.percentile(tw, 75)
    a = jays_in[tw <= lo].mean()
    b = jays_in[tw >= hi].mean()
    dep[t] = {"if_rival_cold": float(a), "if_rival_hot": float(b),
              "swing": float(a - b), "cold_w": float(lo), "hot_w": float(hi)}
out["dependency"] = dep

# how many of the cluster do the Jays need to pass?
passed = np.zeros(NSIM, dtype=np.int8)
for t in CLUSTER:
    passed += (score[J] > score[idx[t]])
out["pass_dist"] = {int(k): float((passed == k).mean()) for k in range(len(CLUSTER) + 1)}
# NaN when nothing qualifies; the page reads this straight
out["pass_given_in"] = float(passed[jays_in].mean()) if jays_in.any() else 0.0

# elimination / magic number vs the current WC3 holder (best non-playoff cutline)
cut = np.sort(wc_score, axis=0)[-3]              # 3rd wild card score threshold
out["cut_wins"] = {
    "mean": float(np.mean(np.floor(cut))),
    "p50": float(np.percentile(np.floor(cut), 50)),
    "p90": float(np.percentile(np.floor(cut), 90)),
}
# Elimination number against the median cut line: the number of further Jays losses
# that leaves them short of it. Derived from cut_wins.p50 — the same figure the page
# quotes as "the cut line" — so the two cannot disagree by a win, which they did when
# this used ceil(median(cut)) on the raw tie-broken scores.
_target = int(np.ceil(out["cut_wins"]["p50"]))
_need = max(0, _target - D.AL[JAYS][0])
out["cut_target_w"] = _target
out["elimination_number"] = max(0, min(int(rem[JAYS]) + 1, int(rem[JAYS]) + 1 - _need))

# streak requirement: P(in | Jays go X-Y over the next stretch)
nnext = min(12, len(jays_game_ix))
nextN = jays_won[:nnext].sum(axis=0)
out["next_n"] = nnext
out["next12"] = {int(w): [float(jays_in[nextN == w].mean()), float((nextN == w).mean())]
                 for w in range(nnext + 1) if (nextN == w).sum() >= 100}

with open("results.json", "w") as f:
    json.dump(out, f, indent=1)

print(f"games modelled: {len(games)}   sims: {NSIM}")
print(f"Jays talent {talent[JAYS]:.4f}  proj {out['proj_wins']['mean']:.1f} W")
print(f"PLAYOFF ODDS: {out['odds']['playoff']*100:.1f}%  (WC {out['odds']['wildcard']*100:.1f}%)")
print(f"wins needed: 10% @ {out['wins_10']}  50% @ {out['wins_50']}  90% @ {out['wins_90']}")
print(f"cutline median: {out['cut_wins']['p50']:.0f} wins")
if out["momentum"]:
    _m = out["momentum"]
    print(f"momentum: {_m['index']:+d} ({_m['label']}) — last 10 "
          f"{_m['l10_w']}-{_m['l10_l']} vs {_m['l10_expected_w']} expected")
print("\nrival odds:")
for t, v in sorted(out["rivals"].items(), key=lambda x: -x[1]["playoff"]):
    print(f"  {t:<10} {v['w']}-{v['l']} rd{v['rd']:+4d}  proj {v['proj_w']:.1f}  {v['playoff']*100:5.1f}%")
print("\ntop leverage games:")
for g in sorted(lev, key=lambda x: -x["leverage"])[:8]:
    print(f"  {g['date']} vs {g['opp']:<10} {'H' if g['home'] else 'A'}  {g['leverage']*100:.2f} pts")
print("\nseries swing:")
for s in sorted(out["series"], key=lambda x: -(x["swing"] or 0)):
    print(f"  {s['start']} {'vs' if s['home'] else '@ '} {s['opp']:<10} exp {s['exp_wins']:.2f}/{s['n']}  swing {s['swing']*100:.1f} pts")
