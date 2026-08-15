"""
Blue Jays 2026 playoff-chase Monte Carlo.

Model
-----
Team talent  : Pythagenpat expected win% (exponent = RPG**0.287) blended 80/20 with
               actual win%, then regressed toward .500 with a 68-game prior. This is
               the standard rest-of-season talent estimator -- run differential is a
               better predictor of future wins than W-L is.
Game model   : log5 matchup probability + home-field advantage (league HFA ~ .535,
               applied as an odds multiplier).
Field        : 3 AL division winners + 3 wild cards, ties broken at random (unbiased
               in expectation; real MLB uses H2H -> intradivision -> last 20).
Derived      : every conditional (odds given a series result, odds given a rival's
               finish, per-game leverage) is computed by conditioning on the SAME
               set of simulated seasons, so all numbers are mutually consistent.
"""
import json, collections, itertools
import numpy as np
import data as D
import collections

RNG = np.random.default_rng(20260814)
NSIM = 120_000
JAYS = "Blue Jays"
HFA_ODDS = 1.15          # ~.535 home win% at even talent
REG_PRIOR = 68.0         # games of .500 regression
PYTH_WEIGHT = 0.80

# ---------------------------------------------------------------- talent
def pythagenpat(rs, ra, g):
    rpg = (rs + ra) / g
    x = rpg ** 0.287
    return rs**x / (rs**x + ra**x)

TEAMS = {**D.AL, **D.NL}
talent = {}
for name, (w, l, rs, ra) in TEAMS.items():
    g = w + l
    p = pythagenpat(rs, ra, g)
    blend = PYTH_WEIGHT * p + (1 - PYTH_WEIGHT) * (w / g)
    talent[name] = (blend * g + 0.500 * REG_PRIOR) / (g + REG_PRIOR)

# ---------------------------------------------------------------- schedule
AL_TEAMS = list(D.AL)
games = list(D.GAMES)          # already deduped and validated by fetch_data.py
games.sort(key=lambda g: (g[0], g[1], g[2]))

# sanity: every AL team must reach 162
played = {t: sum(D.AL[t][:2]) for t in AL_TEAMS}
rem = collections.Counter()
for _, a, h in games:
    if a in D.AL: rem[a] += 1
    if h in D.AL: rem[h] += 1
problems = {t: played[t] + rem[t] for t in AL_TEAMS if played[t] + rem[t] != 162}
if problems:
    raise SystemExit(f"schedule does not reconcile to 162: {problems}")

# ---------------------------------------------------------------- simulate
def log5(a, b):
    return (a - a * b) / (a + b - 2 * a * b)

idx = {t: i for i, t in enumerate(AL_TEAMS)}
NG = len(games)
p_home = np.empty(NG)
for i, (_, a, h) in enumerate(games):
    p = log5(talent[h], talent[a])
    o = p / (1 - p) * HFA_ODDS
    p_home[i] = o / (1 + o)

draws = RNG.random((NG, NSIM))
home_wins = draws < p_home[:, None]          # (NG, NSIM) bool

wins = np.zeros((15, NSIM), dtype=np.int16)
for t in AL_TEAMS:
    wins[idx[t]] = D.AL[t][0]
for i, (_, a, h) in enumerate(games):
    hw = home_wins[i]
    if h in D.AL: wins[idx[h]] += hw
    if a in D.AL: wins[idx[a]] += ~hw

# ---------------------------------------------------------------- playoff field
tie = RNG.random((15, NSIM))
score = wins.astype(np.float64) + tie * 0.5      # random tiebreak

div_of = {}
for dname, members in D.DIVISIONS.items():
    for m in members: div_of[m] = dname

div_winner = np.zeros((15, NSIM), dtype=bool)
for dname, members in D.DIVISIONS.items():
    rows = [idx[m] for m in members]
    sub = score[rows]
    best = np.argmax(sub, axis=0)
    div_winner[np.array(rows)[best], np.arange(NSIM)] = True

wc_score = np.where(div_winner, -1e9, score)
order = np.argsort(-wc_score, axis=0)
wc = np.zeros((15, NSIM), dtype=bool)
for k in range(3):
    wc[order[k], np.arange(NSIM)] = True

playoff = div_winner | wc
J = idx[JAYS]
jays_in = playoff[J]
jays_wins = wins[J]

# ---------------------------------------------------------------- outputs
out = {}
out["as_of"] = D.AS_OF
out["nsim"] = NSIM
out["record"] = {"w": D.AL[JAYS][0], "l": D.AL[JAYS][1],
                 "rs": D.AL[JAYS][2], "ra": D.AL[JAYS][3]}
out["games_left"] = int(rem[JAYS])
out["talent"] = {t: round(talent[t], 4) for t in AL_TEAMS}
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
curve = {}
for w in range(75, 98):
    m = jays_wins == w
    if m.sum() >= 150:
        curve[w] = [float(jays_in[m].mean()), int(m.sum())]
out["win_curve"] = curve
# threshold: smallest win total that is >=50% / >=90% to qualify
out["wins_50"] = min((w for w, (p, n) in curve.items() if p >= .50), default=None)
out["wins_90"] = min((w for w, (p, n) in curve.items() if p >= .90), default=None)
out["wins_10"] = min((w for w, (p, n) in curve.items() if p >= .10), default=None)

# ---------------------------------------------------------------- series analysis
jays_game_ix = [i for i, (_, a, h) in enumerate(games) if JAYS in (a, h)]
jays_won = np.empty((len(jays_game_ix), NSIM), dtype=bool)
for k, i in enumerate(jays_game_ix):
    _, a, h = games[i]
    jays_won[k] = home_wins[i] if h == JAYS else ~home_wins[i]

# group consecutive games into series by opponent
series = []
cur = None
for k, i in enumerate(jays_game_ix):
    date, a, h = games[i]
    opp = a if h == JAYS else h
    home = (h == JAYS)
    if cur and cur["opp"] == opp and cur["home"] == home:
        cur["ix"].append(k); cur["end"] = date
    else:
        if cur: series.append(cur)
        cur = {"opp": opp, "home": home, "ix": [k], "start": date, "end": date}
series.append(cur)

out["series"] = []
base = jays_in.mean()
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
        "is_rival": s["opp"] in ("Rangers", "Tigers", "Guardians", "Twins", "Astros",
                                 "Mariners", "Orioles", "Red Sox", "Yankees"),
    })

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
for t in ["Rangers", "Tigers", "Guardians", "Twins", "Astros", "Mariners", "Red Sox", "Yankees"]:
    tw = wins[idx[t]]
    lo, hi = np.percentile(tw, 25), np.percentile(tw, 75)
    a = jays_in[tw <= lo].mean()
    b = jays_in[tw >= hi].mean()
    dep[t] = {"if_rival_cold": float(a), "if_rival_hot": float(b),
              "swing": float(a - b), "cold_w": float(lo), "hot_w": float(hi)}
out["dependency"] = dep

# how many of the 5-team cluster do the Jays need to pass?
cluster = ["Rangers", "Tigers", "Guardians", "Twins"]
passed = np.zeros(NSIM, dtype=np.int8)
for t in cluster:
    passed += (score[J] > score[idx[t]])
out["pass_dist"] = {int(k): float((passed == k).mean()) for k in range(len(cluster) + 1)}
out["pass_given_in"] = float(passed[jays_in].mean())

# elimination / magic number vs the current WC3 holder (best non-playoff cutline)
cut = np.sort(wc_score, axis=0)[-3]              # 3rd wild card score threshold
out["cut_wins"] = {
    "mean": float(np.mean(np.floor(cut))),
    "p50": float(np.percentile(np.floor(cut), 50)),
    "p90": float(np.percentile(np.floor(cut), 90)),
}
need = np.ceil(cut) - D.AL[JAYS][0]
out["elimination_number"] = int(rem[JAYS] + 1 - (np.ceil(np.median(cut)) - D.AL[JAYS][0]))

# streak requirement: P(in | Jays go X-Y over next 12 games)
next12 = jays_won[:12].sum(axis=0)
out["next12"] = {int(w): [float(jays_in[next12 == w].mean()), float((next12 == w).mean())]
                 for w in range(13) if (next12 == w).sum() >= 100}

with open("results.json", "w") as f:
    json.dump(out, f, indent=1)

print(f"games modelled: {NG}   sims: {NSIM}")
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
