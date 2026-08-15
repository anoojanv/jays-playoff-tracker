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
                   idx, rem, series, jays_game_ix, pythagenpat)

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
        "is_rival": s["opp"] in RIVALS + ["Orioles"],
    })

# how many of the Jays' remaining games are against the wild-card cluster
out["cluster_games"] = int(sum(len(s["ix"]) for s in series if s["opp"] in CLUSTER))

# per-game leverage: P(in | win) - P(in | loss)
lev = []
for k, i in enumerate(jays_game_ix):
    date, a, h = games[i]
    opp = a if h == JAYS else h
    w = jays_won[k]
    lev.append({
        "date": date, "opp": opp, "home": (h == JAYS),
        "leverage": float(jays_in[w].mean() - jays_in[~w].mean()),
    })
out["leverage"] = lev

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
out["pass_given_in"] = float(passed[jays_in].mean())

# elimination / magic number vs the current WC3 holder (best non-playoff cutline)
cut = np.sort(wc_score, axis=0)[-3]              # 3rd wild card score threshold
out["cut_wins"] = {
    "mean": float(np.mean(np.floor(cut))),
    "p50": float(np.percentile(np.floor(cut), 50)),
    "p90": float(np.percentile(np.floor(cut), 90)),
}
# standard magic-number form, clamped to the games that actually remain
_elim = int(rem[JAYS] + 1 - (np.ceil(np.median(cut)) - D.AL[JAYS][0]))
out["elimination_number"] = max(0, min(int(rem[JAYS]) + 1, _elim))

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
print("\nrival odds:")
for t, v in sorted(out["rivals"].items(), key=lambda x: -x[1]["playoff"]):
    print(f"  {t:<10} {v['w']}-{v['l']} rd{v['rd']:+4d}  proj {v['proj_w']:.1f}  {v['playoff']*100:5.1f}%")
print("\ntop leverage games:")
for g in sorted(lev, key=lambda x: -x["leverage"])[:8]:
    print(f"  {g['date']} vs {g['opp']:<10} {'H' if g['home'] else 'A'}  {g['leverage']*100:.2f} pts")
print("\nseries swing:")
for s in sorted(out["series"], key=lambda x: -(x["swing"] or 0)):
    print(f"  {s['start']} {'vs' if s['home'] else '@ '} {s['opp']:<10} exp {s['exp_wins']:.2f}/{s['n']}  swing {s['swing']*100:.1f} pts")
