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
import collections, json, math, os
import numpy as np
import data as D

SEED = 20260814
NSIM = 120_000
JAYS = "Blue Jays"
HFA_ODDS = 1.15          # ~.535 home win% at even talent
REG_PRIOR = 68.0         # games of .500 regression
PYTH_WEIGHT = 0.80

# How close a club has to be to Toronto, in games, to count as part of the race.
CLUSTER_GB = 6.0

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim_state.npz")


# ---------------------------------------------------------------- talent
def pythagenpat(rs, ra, g):
    rpg = (rs + ra) / g
    x = rpg ** 0.287
    return rs**x / (rs**x + ra**x)


def log5(a, b):
    return (a - a * b) / (a + b - 2 * a * b)


TEAMS = {**D.AL, **D.NL}


# ---------------------------------------------------------------- who the race is against
def _winpct(t):
    w, l = D.AL[t][:2]
    return w / (w + l) if w + l else 0.0


def games_back(t):
    """Games ahead of Toronto (positive) or behind (negative), from the standings."""
    w, l = D.AL[t][:2]
    jw, jl = D.AL[JAYS][:2]
    return ((w - jw) + (jl - l)) / 2


def contenders(max_gb=CLUSTER_GB):
    """The clubs Toronto is actually racing, read off the standings on every build.

    This used to be a list typed into the source in August: the same four clubs were
    still being called "the cluster" in September when two of them were six games back
    with no chance, and the club actually holding the last spot was not among them.

    A club is in the cluster when it is not leading a division (leaders occupy the
    automatic berths, so Toronto does not have to pass them) and sits within `max_gb`
    games of Toronto in either direction. Two clubs is the floor: with fewer than that
    within range, the nearest two are used so the page always has a race to describe.
    """
    leaders = {max(m, key=_winpct) for m in D.DIVISIONS.values()}
    others = [t for t in D.AL if t != JAYS and t not in leaders]
    near = [t for t in others if abs(games_back(t)) <= max_gb]
    if len(near) < 2:
        near = sorted(others, key=lambda t: abs(games_back(t)))[:2]
    return sorted(near, key=_winpct, reverse=True)


CLUSTER = contenders()
# every other AL club: the page keeps whichever six actually move Toronto's odds most
RIVALS = [t for t in D.AL if t != JAYS]

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


NEUTRAL = 0.500          # a league-average club, for measuring schedules


def matchup(self_talent, opp_talent, at_home):
    """P(win) for a club of `self_talent` against `opp_talent`: log5 plus home edge.

    The same maths p_home uses to build the simulation, exposed so that anything
    describing the schedule is guaranteed to agree with what is actually simulated.
    """
    p = log5(self_talent, opp_talent)
    if at_home:
        o = p / (1 - p) * HFA_ODDS
        return o / (1 + o)
    o = (1 - p) / p * HFA_ODDS              # the opponent gets the edge on the road
    return 1 / (1 + o)


def p_win(opp, at_home):
    """The model's own probability that Toronto wins that game."""
    return matchup(talent[JAYS], talent[opp], at_home)


def strength_of_schedule():
    """How hard each AL club's remaining games are, independent of how good it is.

    The value is what an identical league-average club would win against that exact
    run of opponents, home and road included. Holding talent constant is the whole
    point: it isolates the schedule, so two clubs can be compared directly without
    their own quality leaking into the number.

    This is descriptive only. The simulation already prices every remaining game
    against its specific opponent, so strength of schedule is in the odds by
    construction — this exists to make visible something the odds already know.
    """
    out = {}
    for t in AL_TEAMS:
        exp, n = 0.0, 0
        for _, a, h in games:
            if h == t:
                exp += matchup(NEUTRAL, talent[a], True); n += 1
            elif a == t:
                exp += matchup(NEUTRAL, talent[h], False); n += 1
        out[t] = (exp / n) if n else None
    return out


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


def around_the_league(st, live_lo=0.05, live_hi=0.98):
    """Every remaining game Toronto is NOT playing, scored against Toronto's own odds.

    For each game: P(Toronto in | home wins) - P(Toronto in | away wins), read off the
    same simulated seasons as everything else, so it cannot disagree with the headline
    number. `root` is the club a Blue Jays fan should want to win, and `leverage` is the
    size of the gap.

    This is the half of scoreboard watching the page never had. Ranking clubs by how much
    their FINISH matters is unactionable the moment two of them play each other: "root
    against Cleveland" and "root against Chicago" are contradictory advice for a
    Cleveland-Chicago game. Scoring the game resolves it, and it prices in the whole
    structure of the field — including a division race, where the loser drops into the
    wild-card pool Toronto is fighting over, so beating a rival can help them.
    """
    jays_in = st.jays_in
    nsim = int(jays_in.shape[0])
    po = {t: float(st.playoff[idx[t]].mean()) for t in AL_TEAMS}
    out = []
    for i, (date, a, h) in enumerate(games):
        if JAYS in (a, h) or (a not in D.AL and h not in D.AL):
            continue
        w = st.home_wins[i]
        nw = int(w.sum())
        if nw == 0 or nw == nsim:        # degenerate once the race is decided
            continue
        p1 = float(jays_in[w].mean())
        p2 = float(jays_in[~w].mean())
        lv = p1 - p2
        # Monte Carlo error on that difference. Most games in a league are worth almost
        # nothing to Toronto, and below a couple of standard errors the SIGN is noise —
        # so the page would be telling people to root for a team on the strength of a
        # coin flip in the random number generator. Anything that does not clear the bar
        # is reported as a toss-up instead of getting a recommendation it cannot support.
        n1, n2 = nw, nsim - nw
        se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
        out.append({
            "date": date, "away": a, "home": h,
            "root": h if lv > 0 else a,
            "leverage": abs(lv),
            "sure": bool(abs(lv) > 2 * se),
            # Both clubs still genuinely in the race, so one of them has to lose and the
            # game is worth less than either club's dependency bar implies. Keyed on live
            # playoff odds rather than on CLUSTER, which excludes division leaders — and
            # a division race between two live clubs is the sharpest case of this.
            "h2h": bool(live_lo < po.get(a, 0.0) < live_hi
                        and live_lo < po.get(h, 0.0) < live_hi),
        })
    out.sort(key=lambda g: (g["date"], -g["leverage"]))
    return out


# MLB's current format: the three division winners take seeds 1-3 by record, the three
# wild cards take 4-6 — a 100-win wild card still seeds behind an 85-win division winner.
# Seeds 1 and 2 sit out the Wild Card round; 3 hosts 6 and 4 hosts 5, best of three, and
# the winners meet the byes in the Division Series (1 plays the 4/5 winner, 2 plays 3/6).
WC_OPPONENT = {3: 6, 6: 3, 4: 5, 5: 4}
BYE_SEEDS = (1, 2)


def seeds_of(st):
    """Team index occupying each AL seed, as a (6, NSIM) array: row k is seed k+1."""
    neg = -np.inf
    dw = np.argsort(-np.where(st.div_winner, st.score, neg), axis=0)[:3]
    wc = np.argsort(-np.where(st.wc, st.score, neg), axis=0)[:3]
    return np.vstack([dw, wc])


# Home-field patterns, as MLB plays them. True = the higher seed hosts.
#   Wild Card  best of 3: the higher seed hosts every game
#   Division   best of 5: 2-2-1
#   Championship best of 7: 2-3-2
FORMATS = {
    "wc":   [True, True, True],
    "alds": [True, True, False, False, True],
    "alcs": [True, True, False, False, False, True, True],
}


def _matchup_vec(tal_a, tal_b, a_home):
    """log5 plus home edge, elementwise — the same maths matchup() uses one at a time."""
    p = (tal_a - tal_a * tal_b) / (tal_a + tal_b - 2 * tal_a * tal_b)
    if a_home:
        o = p / (1 - p) * HFA_ODDS
        return o / (1 + o)
    o = (1 - p) / p * HFA_ODDS
    return 1 / (1 + o)


def play_series(rng, tal_a, tal_b, pattern):
    """Does A win the series? One draw per game in the pattern, majority takes it.

    Playing all G games rather than stopping at the clinch gives the identical winner —
    whoever reaches the needed wins first necessarily holds the majority of G — and it
    vectorises over every simulated season at once instead of looping.
    """
    a_wins = np.zeros(len(tal_a), dtype=np.int16)
    for a_home in pattern:
        a_wins += rng.random(len(tal_a)) < _matchup_vec(tal_a, tal_b, a_home)
    return a_wins > len(pattern) // 2


def postseason(st, seeds, rng):
    """Play October out: Wild Card, Division Series, Championship Series.

    Returns the club that comes out of each node of the bracket. The regular-season
    simulation always stopped at the field; everything past this point is new, and it uses
    the same log5-plus-home-edge matchup the schedule is simulated with, so a series is
    priced the same way a game in August is.
    """
    tal = np.array([talent[t] for t in AL_TEAMS])
    cols = np.arange(seeds.shape[1])
    s1, s2, s3, s4, s5, s6 = (seeds[k] for k in range(6))

    # Wild Card round: 3 hosts 6, 4 hosts 5
    w36 = np.where(play_series(rng, tal[s3], tal[s6], FORMATS["wc"]), s3, s6)
    w45 = np.where(play_series(rng, tal[s4], tal[s5], FORMATS["wc"]), s4, s5)

    # Division Series: the 1 seed takes the 4/5 winner, the 2 seed takes the 3/6 winner
    d1 = np.where(play_series(rng, tal[s1], tal[w45], FORMATS["alds"]), s1, w45)
    d2 = np.where(play_series(rng, tal[s2], tal[w36], FORMATS["alds"]), s2, w36)

    # Championship Series: the better seed hosts, and d1 always outranks d2
    champ = np.where(play_series(rng, tal[d1], tal[d2], FORMATS["alcs"]), d1, d2)
    return {"w36": w36, "w45": w45, "d1": d1, "d2": d2, "champ": champ}


def bracket(st, per_slot=4):
    """Where Toronto lands and who they play, GIVEN that they qualify.

    Everything here is conditional on making the field — the page says so plainly,
    because 39% of the time none of it happens. Read off the same simulated seasons as
    the headline number, so the bracket cannot tell a different story from the odds.

    Returns None when nothing qualifies (a club already eliminated), which is the case
    that used to kill the build every September.
    """
    jays_in = st.jays_in
    n_in = int(jays_in.sum())
    if not n_in:
        return None

    seeds = seeds_of(st)
    J = idx[JAYS]
    nsim = seeds.shape[1]

    # Toronto's own seed, 1-6
    is_j = seeds == J
    j_seed = np.argmax(is_j, axis=0) + 1

    # who they meet in the Wild Card round; a bye means they meet nobody yet
    opp_row = np.array([-1, -1, 5, 4, 3, 2])          # seed 1..6 -> opponent's row
    row = opp_row[j_seed - 1]
    opp = np.where(row >= 0, seeds[np.clip(row, 0, 5), np.arange(nsim)], -1)

    m = jays_in
    seed_dist = {k: float((j_seed[m] == k).mean()) for k in range(1, 7)
                 if (j_seed[m] == k).any()}
    j_best_seed = max(seed_dist, key=seed_dist.get)

    # Toronto's Wild Card opponent, and whether they host it
    opp_m = opp[m]
    opps = []
    for t_i, c in sorted(collections.Counter(opp_m.tolist()).items(),
                         key=lambda kv: -kv[1]):
        opps.append({"team": None if t_i < 0 else AL_TEAMS[t_i], "p": c / n_in})

    # Who fills each seed. Toronto is pinned to its own likeliest seed and the other
    # five slots show the likeliest club that is NOT Toronto, so the bracket reads as one
    # coherent picture rather than six independent modal answers that may not fit together.
    slots = {}
    for k in range(1, 7):
        occ = seeds[k - 1][m]
        counts = collections.Counter(occ.tolist())
        ranked = [{"team": AL_TEAMS[t_i], "p": c / n_in}
                  for t_i, c in sorted(counts.items(), key=lambda kv: -kv[1])]
        if k == j_best_seed:
            pinned = [r for r in ranked if r["team"] == JAYS] or [{"team": JAYS, "p": 0.0}]
            rest = [r for r in ranked if r["team"] != JAYS]
            ranked = pinned + rest
        else:
            ranked = [r for r in ranked if r["team"] != JAYS]
        slots[k] = ranked[:per_slot]

    # ---- the rest of October
    rng = np.random.default_rng(SEED + 7)
    ps = postseason(st, seeds, rng)

    def dist(arr):
        c = collections.Counter(arr[m].tolist())
        return [{"team": AL_TEAMS[t_i], "p": n / n_in}
                for t_i, n in sorted(c.items(), key=lambda kv: -kv[1])][:per_slot]

    rounds = {k: dist(v) for k, v in ps.items()}

    # Toronto's own road, each step conditional on qualifying
    bye = j_seed <= 2
    reach_alds = bye | (ps["w36"] == J) | (ps["w45"] == J)
    reach_alcs = (ps["d1"] == J) | (ps["d2"] == J)
    pennant = ps["champ"] == J

    return {
        "p_qualify": float(jays_in.mean()),
        "n_qualifying": n_in,
        "jays_seed": seed_dist,
        "jays_best_seed": j_best_seed,
        "jays_opponent": opps[:per_slot],
        "p_bye": float((j_seed[m] <= 2).mean()),
        # the higher seed hosts the whole Wild Card round
        "p_host": float(((j_seed[m] >= 3) & (j_seed[m] <= 4)).mean()),
        "slots": slots,
        "rounds": rounds,
        "road": {
            "alds": float(reach_alds[m].mean()),
            "alcs": float(reach_alcs[m].mean()),
            "pennant": float(pennant[m].mean()),
        },
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

    # home_wins travels with the rest: it is what makes a game NOT involving Toronto
    # scoreable against Toronto's odds, which is the whole of the spoiler analysis.
    return State(wins=wins, score=score, wc_score=wc_score, div_winner=div_winner,
                 wc=wc, playoff=playoff, jays_in=playoff[J], jays_wins=wins[J],
                 jays_won=jays_won, home_wins=home_wins)


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
