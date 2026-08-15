"""Model-sensitivity ensemble: how much does the Jays' number depend on modelling choices?"""
import json, collections
import numpy as np
import data as D

JAYS = "Blue Jays"
NSIM = 60_000
TEAMS = {**D.AL, **D.NL}
AL_TEAMS = list(D.AL)
idx = {t: i for i, t in enumerate(AL_TEAMS)}


def pythagenpat(rs, ra, g):
    rpg = (rs + ra) / g
    x = rpg ** 0.287
    return rs**x / (rs**x + ra**x)


games = sorted(D.GAMES)



def build_talent(pyth_w, prior, recency=0.0):
    t = {}
    for name, (w, l, rs, ra) in TEAMS.items():
        g = w + l
        p = pythagenpat(rs, ra, g)
        blend = pyth_w * p + (1 - pyth_w) * (w / g)
        val = (blend * g + 0.500 * prior) / (g + prior)
        if recency:
            # nudge toward raw W-L, itself heavily regressed (stand-in for recent form)
            raw = (w / g * 20 + 0.500 * 50) / 70
            val = (1 - recency) * val + recency * raw
        t[name] = val
    return t


def log5(a, b):
    return (a - a * b) / (a + b - 2 * a * b)


def run(talent, hfa, seed):
    rng = np.random.default_rng(seed)
    NG = len(games)
    ph = np.empty(NG)
    for i, (_, a, h) in enumerate(games):
        p = log5(talent[h], talent[a])
        o = p / (1 - p) * hfa
        ph[i] = o / (1 + o)
    hw = rng.random((NG, NSIM)) < ph[:, None]
    wins = np.zeros((15, NSIM), dtype=np.int16)
    for t in AL_TEAMS:
        wins[idx[t]] = D.AL[t][0]
    for i, (_, a, h) in enumerate(games):
        if h in D.AL: wins[idx[h]] += hw[i]
        if a in D.AL: wins[idx[a]] += ~hw[i]
    score = wins + rng.random((15, NSIM)) * 0.5
    dw = np.zeros((15, NSIM), dtype=bool)
    for _, mem in D.DIVISIONS.items():
        rows = np.array([idx[m] for m in mem])
        dw[rows[np.argmax(score[rows], axis=0)], np.arange(NSIM)] = True
    wcs = np.where(dw, -1e9, score)
    order = np.argsort(-wcs, axis=0)
    wc = np.zeros((15, NSIM), dtype=bool)
    for k in range(3):
        wc[order[k], np.arange(NSIM)] = True
    po = dw | wc
    return float(po[idx[JAYS]].mean()), float(wins[idx[JAYS]].mean())


SCENARIOS = [
    ("Run-differential purist (100% Pythag)",      build_talent(1.00, 68),        1.15),
    ("Pythag-leaning (80/20) - primary model",     build_talent(0.80, 68),        1.15),
    ("Balanced (50/50)",                           build_talent(0.50, 68),        1.15),
    ("Record-leaning (20/80)",                     build_talent(0.20, 68),        1.15),
    ("W-L purist (0% Pythag)",                     build_talent(0.00, 68),        1.15),
    ("Primary + heavy regression (K=110)",         build_talent(0.80, 110),       1.15),
    ("Primary + light regression (K=35)",          build_talent(0.80, 35),        1.15),
    ("Primary + recent-form credit (25%)",          build_talent(0.80, 68, 0.25),  1.15),
    ("Primary + no home-field edge",               build_talent(0.80, 68),        1.00),
    ("Primary + strong home-field (.550)",         build_talent(0.80, 68),        1.22),
]

res = []
for i, (label, tal, hfa) in enumerate(SCENARIOS):
    odds, pw = run(tal, hfa, 900 + i)
    res.append({"label": label, "odds": odds, "proj_w": pw,
                "jays_talent": round(tal[JAYS], 4)})
    print(f"{odds*100:5.1f}%   proj {pw:5.1f}W   talent {tal[JAYS]:.4f}   {label}")

vals = [r["odds"] for r in res]
print(f"\nrange {min(vals)*100:.1f}% - {max(vals)*100:.1f}%   median {np.median(vals)*100:.1f}%")
json.dump({"scenarios": res,
           "lo": min(vals), "hi": max(vals), "median": float(np.median(vals))},
          open("ensemble.json", "w"), indent=1)
