"""
The simulation itself — talent, schedule, and the Monte Carlo over the rest of the AL.

This used to live inside sim.py, and analyze.py and export_sim.py got at it with

    exec(open("sim.py").read().split('with open("results.json"')[0])

which re-ran the whole simulation in each process and silently depended on the exact
text of a line in another file. Both are now imports.

Everything above `simulate()` is deterministic — no RNG is touched — so importing this
module is cheap. The random part runs once, in sim.py, which saves the arrays the two
downstream scripts need via save_state(); they call load_state() instead of resimulating.

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
import collections, json, os
import numpy as np
import data as D

SEED = 20260814
NSIM = 120_000
JAYS = "Blue Jays"
HFA_ODDS = 1.15          # ~.535 home win% at even talent
REG_PRIOR = 68.0         # games of .500 regression
PYTH_WEIGHT = 0.80

# Rivals the page tracks as the wild-card cluster. Kept here rather than duplicated in
# sim.py and build_html.py so the prose and the numbers cannot drift apart.
CLUSTER = ["Rangers", "Tigers", "Guardians", "Twins"]
RIVALS = ["Rangers", "Tigers", "Guardians", "Twins", "Astros", "Mariners",
          "Red Sox", "Yankees"]

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim_state.npz")


# ---------------------------------------------------------------- talent
def pythagenpat(rs, ra, g):
    rpg = (rs + ra) / g
    x = rpg ** 0.287
    return rs**x / (rs**x + ra**x)


def log5(a, b):
    return (a - a * b) / (a + b - 2 * a * b)


TEAMS = {**D.AL, **D.NL}
talent = {}
for _name, (_w, _l, _rs, _ra) in TEAMS.items():
    _g = _w + _l
    _p = pythagenpat(_rs, _ra, _g)
    _blend = PYTH_WEIGHT * _p + (1 - PYTH_WEIGHT) * (_w / _g)
    talent[_name] = (_blend * _g + 0.500 * REG_PRIOR) / (_g + REG_PRIOR)

# ---------------------------------------------------------------- schedule
AL_TEAMS = list(D.AL)
idx = {t: i for i, t in enumerate(AL_TEAMS)}
games = list(D.GAMES)          # already deduped and validated by fetch_data.py
games.sort(key=lambda g: (g[0], g[1], g[2]))
NG = len(games)

# sanity: every AL team must reach 162
played = {t: sum(D.AL[t][:2]) for t in AL_TEAMS}
rem = collections.Counter()
for _, _a, _h in games:
    if _a in D.AL: rem[_a] += 1
    if _h in D.AL: rem[_h] += 1
problems = {t: played[t] + rem[t] for t in AL_TEAMS if played[t] + rem[t] != 162}
if problems:
    raise SystemExit(f"schedule does not reconcile to 162: {problems}")

if not rem[JAYS]:
    raise SystemExit(
        "SEASON COMPLETE: no games remain for the Blue Jays, so there is nothing left\n"
        "to simulate. Disable the workflow in the Actions tab, or bump SEASON for next\n"
        "year. (This is a clean stop, not a failure.)")

p_home = np.empty(NG)
for _i, (_, _a, _h) in enumerate(games):
    _p = log5(talent[_h], talent[_a])
    _o = _p / (1 - _p) * HFA_ODDS
    p_home[_i] = _o / (1 + _o)

# ---------------------------------------------------------------- series structure
# deterministic: depends only on the schedule, so downstream scripts get it by import
jays_game_ix = [i for i, (_, a, h) in enumerate(games) if JAYS in (a, h)]

series = []
_cur = None
for _k, _i in enumerate(jays_game_ix):
    _date, _a, _h = games[_i]
    _opp = _a if _h == JAYS else _h
    _home = (_h == JAYS)
    if _cur and _cur["opp"] == _opp and _cur["home"] == _home:
        _cur["ix"].append(_k); _cur["end"] = _date
    else:
        if _cur: series.append(_cur)
        _cur = {"opp": _opp, "home": _home, "ix": [_k], "start": _date, "end": _date}
if _cur:
    series.append(_cur)


def p_win(opp, at_home):
    """The model's own probability that Toronto wins that game — log5 plus home edge."""
    p = log5(talent[JAYS], talent[opp])
    if at_home:
        o = p / (1 - p) * HFA_ODDS
        return o / (1 + o)
    o = (1 - p) / p * HFA_ODDS              # the opponent gets the edge on the road
    return 1 / (1 + o)


def momentum(decay=0.90, window=25):
    """How the Blue Jays are playing relative to how they should be playing.

    Raw "last 10" is a poor form measure: 6-4 against the Rays and Yankees is a much
    better ten games than 6-4 against the Athletics and Angels. Every game here is
    scored against what the model itself expected, using the same matchup probability
    that simulates the rest of the season, so the rating is actual minus expected.
    Zero means playing exactly to their own level, which is not the same as .500.

    Recent games count for more: weights decay by `decay` per game back, a half-life of
    about seven games, so a hot week shows through without a good April propping it up.

    Returns None when there is nothing to measure, and the page omits the badge.
    """
    recent = [g for g in D.RECENT if g.get("opp") in talent]
    if not recent:
        return None

    num = den = 0.0
    for i, g in enumerate(reversed(recent[-window:])):    # i = games ago, 0 = latest
        w = decay ** i
        num += w * ((1.0 if g["won"] else 0.0) - p_win(g["opp"], g["home"]))
        den += w
    idx = int(round((num / den if den else 0.0) * 100))

    last10 = recent[-10:]
    w10 = sum(1 for g in last10 if g["won"])
    exp10 = sum(p_win(g["opp"], g["home"]) for g in last10)

    if idx >= 15:   label, tone = "Red hot", "hot"
    elif idx >= 6:  label, tone = "Hot", "warm"
    elif idx > -6:  label, tone = "Steady", "flat"
    elif idx > -15: label, tone = "Cold", "cool"
    else:           label, tone = "Ice cold", "icy"

    return {
        "index": idx, "label": label, "tone": tone,
        "games": len(recent), "window": min(window, len(recent)),
        "l10_w": w10, "l10_l": len(last10) - w10,
        "l10_expected_w": round(exp10, 1),
        "half_life": round(-0.6931 / __import__("math").log(decay), 1),
    }


class State:
    """The simulated seasons. Attribute names match the originals in sim.py."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def simulate():
    """Run the Monte Carlo. Deterministic given SEED, NSIM and the schedule."""
    rng = np.random.default_rng(SEED)

    # Generated in row-blocks rather than as one (NG, NSIM) float64 array. numpy fills
    # in C order from the bit stream, so block-by-block draws the identical numbers --
    # this changes peak memory, not results.
    home_wins = np.empty((NG, NSIM), dtype=bool)
    for s in range(0, NG, 64):
        e = min(s + 64, NG)
        home_wins[s:e] = rng.random((e - s, NSIM)) < p_home[s:e, None]

    wins = np.zeros((15, NSIM), dtype=np.int16)
    for t in AL_TEAMS:
        wins[idx[t]] = D.AL[t][0]
    for i, (_, a, h) in enumerate(games):
        hw = home_wins[i]
        if h in D.AL: wins[idx[h]] += hw
        if a in D.AL: wins[idx[a]] += ~hw

    # ------------------------------------------------------------ playoff field
    tie = rng.random((15, NSIM))
    score = wins.astype(np.float64) + tie * 0.5      # random tiebreak

    div_winner = np.zeros((15, NSIM), dtype=bool)
    for dname, members in D.DIVISIONS.items():
        rows = [idx[m] for m in members]
        best = np.argmax(score[rows], axis=0)
        div_winner[np.array(rows)[best], np.arange(NSIM)] = True

    wc_score = np.where(div_winner, -1e9, score)
    order = np.argsort(-wc_score, axis=0)
    wc = np.zeros((15, NSIM), dtype=bool)
    for k in range(3):
        wc[order[k], np.arange(NSIM)] = True

    playoff = div_winner | wc
    J = idx[JAYS]

    jays_won = np.empty((len(jays_game_ix), NSIM), dtype=bool)
    for k, i in enumerate(jays_game_ix):
        _, a, h = games[i]
        jays_won[k] = home_wins[i] if h == JAYS else ~home_wins[i]

    return State(wins=wins, score=score, wc_score=wc_score, div_winner=div_winner,
                 wc=wc, playoff=playoff, jays_in=playoff[J], jays_wins=wins[J],
                 jays_won=jays_won)


# ---------------------------------------------------------------- state cache
def _key():
    """Anything that would invalidate the cached arrays."""
    return f"{D.FINGERPRINT}|{SEED}|{NSIM}|{NG}|{len(jays_game_ix)}"


def save_state(st):
    """Persist just what analyze.py and export_sim.py need (a few MB, not the lot)."""
    # uncompressed on purpose: this is a few MB of scratch between two steps of the
    # same build, and deflating a bool array costs more than the bytes are worth
    np.savez(STATE, key=np.array(_key()), jays_won=st.jays_won,
             jays_in=st.jays_in, jays_wins=st.jays_wins)


def load_state():
    """Reuse sim.py's simulated seasons; resimulate if the cache is absent or stale."""
    try:
        z = np.load(STATE, allow_pickle=False)
        if str(z["key"]) == _key():
            return State(jays_won=z["jays_won"], jays_in=z["jays_in"],
                         jays_wins=z["jays_wins"])
        print("  note: sim_state.npz is stale — resimulating")
    except FileNotFoundError:
        print("  note: no sim_state.npz — resimulating")
    return simulate()
