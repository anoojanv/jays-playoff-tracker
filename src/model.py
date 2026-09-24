"""
The simulation — talent, schedule, and the Monte Carlo over the rest of the NHL season.

Everything above `simulate()` is deterministic, so importing this module is cheap. The
random part runs once, in sim.py, which saves the arrays the downstream scripts need via
save_state(); they call load_state() instead of resimulating.

Model
-----
Talent     : the probability of beating an average club. Goals-based Pythagorean win%
             (exponent 2.1) blended 70/30 with actual win%, pooled across last season
             and this one, then regressed toward .500. Last season counts as PRIOR_WEIGHT
             games, so it carries a preseason projection on its own and fades as real
             games arrive — by midseason this season outweighs it two to one.
Games      : log5 matchup plus home ice, as an odds multiplier measured from last
             season (home sides won 52.2%, well under hockey folklore). Whether a game
             goes past regulation is drawn separately at the measured rate (24.8%), which
             decides whether the loser takes a point.
Standings  : points, then regulation wins, then a coin — the NHL's first two tiebreakers.
Field      : per conference, the top three in each division plus the next two best as
             wild cards. The better division winner meets the second wild card.
Postseason : every round best of seven, 2-2-1-1-1, home ice to the better regular
             season, through the Stanley Cup Final.
"""
import collections, json, math, os
import numpy as np
import data as D

SEED = 20260929
NSIM = 40_000
FOCUS = D.FOCUS
SEASON_GAMES = D.SEASON_GAMES

PYTH_EXP = 2.1          # goals-based Pythagorean exponent for hockey
PYTH_WEIGHT = 0.70      # goal differential against raw win%
PRIOR_WEIGHT = 40.0     # games last season is worth in the pooled estimate
REG_PRIOR = 40.0        # games of .500 regression on top

P_OT = float(D.LEAGUE["p_ot"])
HOME_WIN = float(D.LEAGUE["home_win"])
HFA_ODDS = HOME_WIN / (1 - HOME_WIN)

# How close a club has to be, in projected points, to count as part of Toronto's race.
CLUSTER_PTS = 10.0

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim_state.npz")

TEAMS = sorted(D.TEAMS)
idx = {t: i for i, t in enumerate(TEAMS)}
NT = len(TEAMS)
CONF = {t: D.TEAMS[t]["conf"] for t in TEAMS}
DIV = {t: D.TEAMS[t]["div"] for t in TEAMS}
FOCUS_CONF = CONF[FOCUS]
FOCUS_DIV = DIV[FOCUS]
CONF_TEAMS = {c: sorted(t for t in TEAMS if CONF[t] == c) for c in D.CONFERENCES}
DIV_ABBR = {d: d[0] for d in D.DIVISIONS}          # Atlantic -> A, Metropolitan -> M ...


# ---------------------------------------------------------------- talent
def pyth(gf, ga, x=PYTH_EXP):
    if gf <= 0 and ga <= 0:
        return None
    return gf ** x / (gf ** x + ga ** x)


def observed(rec, pyth_weight=PYTH_WEIGHT):
    """(estimated win%, games) from one season's record, or (None, 0) with no games."""
    gp = rec.get("gp", rec["w"] + rec["l"] + rec["otl"])
    if not gp:
        return None, 0
    p = pyth(rec["gf"], rec["ga"])
    wp = rec["w"] / gp
    return (wp if p is None else pyth_weight * p + (1 - pyth_weight) * wp), gp


def build_talent(pyth_weight=PYTH_WEIGHT, prior_weight=PRIOR_WEIGHT, reg_prior=REG_PRIOR):
    out = {}
    for t in TEAMS:
        num = den = 0.0
        pr = D.PRIOR.get(t)
        if pr:
            o, _ = observed(pr, pyth_weight)
            if o is not None and prior_weight > 0:
                num += o * prior_weight
                den += prior_weight
        o, n = observed(D.TEAMS[t], pyth_weight)
        if o is not None:
            num += o * n
            den += n
        pooled = num / den if den else 0.5
        out[t] = (pooled * den + 0.5 * reg_prior) / (den + reg_prior)
    return out


talent = build_talent()


def log5(a, b):
    return (a - a * b) / (a + b - 2 * a * b)


def matchup(self_talent, opp_talent, at_home, hfa=HFA_ODDS):
    """P(win) for a club of `self_talent` against `opp_talent`, overtime included."""
    p = log5(self_talent, opp_talent)
    if at_home:
        o = p / (1 - p) * hfa
        return o / (1 + o)
    o = (1 - p) / p * hfa
    return 1 / (1 + o)


def exp_points(p_win, p_ot=P_OT):
    """Expected standings points from one game: two for a win, one for a loss past
    regulation. With the two drawn independently, P(loser point) = P(OT) * P(loss)."""
    return 2 * p_win + p_ot * (1 - p_win)


# ---------------------------------------------------------------- schedule
games = sorted(D.GAMES)
NG = len(games)
g_home = np.array([idx[h] for _, _, h in games], dtype=np.int16)
g_away = np.array([idx[a] for _, a, _ in games], dtype=np.int16)

rem = collections.Counter()
for _, _a, _h in games:
    rem[_a] += 1
    rem[_h] += 1
problems = {t: D.played(t) + rem[t] for t in TEAMS
            if D.played(t) + rem[t] != SEASON_GAMES}
if problems:
    raise SystemExit(f"schedule does not reconcile to {SEASON_GAMES}: {problems}")

if not rem[FOCUS]:
    raise SystemExit(
        f"SEASON COMPLETE: no games remain for {FOCUS}, so there is nothing left\n"
        "to simulate. Disable the workflow in the Actions tab, or bump SEASON for next\n"
        "year. (This is a clean stop, not a failure.)")


def home_probs(tal=None, hfa=HFA_ODDS):
    tal = tal or talent
    return np.array([matchup(tal[h], tal[a], True, hfa) for _, a, h in games])


p_home = home_probs()
focus_game_ix = [i for i, (_, a, h) in enumerate(games) if FOCUS in (a, h)]


def p_win(opp, at_home, tal=None):
    tal = tal or talent
    return matchup(tal[FOCUS], tal[opp], at_home)


def projected_points(tal=None):
    """Current points plus the expected points from every game left. Analytic, so it is
    available before any simulation runs and in the preseason, when everyone has zero."""
    tal = tal or talent
    out = {t: float(D.points(t)) for t in TEAMS}
    for _, a, h in games:
        ph = matchup(tal[h], tal[a], True)
        out[h] += exp_points(ph)
        out[a] += exp_points(1 - ph)
    return out


PROJ = projected_points()


def contenders(band=CLUSTER_PTS):
    """The clubs Toronto is actually racing, read off projected points on every build.

    Projected rather than current points, so the list means something in October, when
    everyone has the same handful and a points gap is noise. Only the focus conference:
    a Western club's record cannot move Toronto's odds of qualifying. Two is the floor, so
    the page always has a race to describe.
    """
    me = PROJ[FOCUS]
    others = [t for t in CONF_TEAMS[FOCUS_CONF] if t != FOCUS]
    near = [t for t in others if abs(PROJ[t] - me) <= band]
    if len(near) < 2:
        near = sorted(others, key=lambda t: abs(PROJ[t] - me))[:2]
    return sorted(near, key=lambda t: -PROJ[t])


CLUSTER = contenders()
# every other club in the conference; the page keeps whichever move Toronto's odds most
RIVALS = [t for t in CONF_TEAMS[FOCUS_CONF] if t != FOCUS]


def strength_of_schedule(tal=None):
    """What an average club would win against each team's remaining opponents, home and
    road included. Descriptive only: the simulation already prices every game."""
    tal = tal or talent
    exp, n = collections.Counter(), collections.Counter()
    for _, a, h in games:
        exp[h] += matchup(0.5, tal[a], True); n[h] += 1
        exp[a] += matchup(0.5, tal[h], False); n[a] += 1
    return {t: (exp[t] / n[t]) if n[t] else None for t in TEAMS}


def momentum(decay=0.90, window=25):
    """How Toronto is playing against how the model expected, recency-weighted.

    Zero means playing exactly to their own level, which is not the same as .500. None in
    the preseason and the first week, when there is nothing to measure.
    """
    recent = [g for g in D.RECENT if g.get("opp") in talent]
    if len(recent) < 3:
        return None
    num = den = 0.0
    for i, g in enumerate(reversed(recent[-window:])):
        w = decay ** i
        num += w * ((1.0 if g["won"] else 0.0) - p_win(g["opp"], g["home"]))
        den += w
    ix = int(round((num / den if den else 0.0) * 100))
    last10 = recent[-10:]
    w10 = sum(1 for g in last10 if g["won"])
    otl10 = sum(1 for g in last10 if not g["won"] and g.get("ot"))
    exp10 = sum(p_win(g["opp"], g["home"]) for g in last10)
    if ix >= 15:   label, tone = "Red hot", "hot"
    elif ix >= 6:  label, tone = "Hot", "warm"
    elif ix > -6:  label, tone = "Steady", "flat"
    elif ix > -15: label, tone = "Cold", "cool"
    else:          label, tone = "Ice cold", "icy"
    return {"index": ix, "label": label, "tone": tone, "games": len(recent),
            "window": min(window, len(recent)), "l10_w": w10,
            "l10_l": len(last10) - w10 - otl10, "l10_otl": otl10,
            "l10_expected_w": round(exp10, 1),
            "half_life": round(-0.6931 / math.log(decay), 1)}


# ---------------------------------------------------------------- simulation
class State:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def simulate(nsim=None, seed=SEED, tal=None, hfa=HFA_ODDS, p_ot=P_OT):
    """Run the Monte Carlo. Deterministic given the seed, the size and the schedule.

    Two draws per game: who wins, and whether it went past regulation. The winner takes
    two points; the loser takes one only if it went past regulation. A regulation win is
    tracked for the tiebreak.
    """
    nsim = nsim or NSIM
    rng = np.random.default_rng(seed)
    ph = p_home if (tal is None and hfa == HFA_ODDS) else home_probs(tal, hfa)

    home_wins = np.empty((NG, nsim), dtype=bool)
    ot = np.empty((NG, nsim), dtype=bool)
    for s in range(0, NG, 64):
        e = min(s + 64, NG)
        home_wins[s:e] = rng.random((e - s, nsim)) < ph[s:e, None]
        ot[s:e] = rng.random((e - s, nsim)) < p_ot

    pts = np.empty((NT, nsim), dtype=np.int16)
    rw = np.empty((NT, nsim), dtype=np.int16)
    for t in TEAMS:
        pts[idx[t]] = D.points(t)
        rw[idx[t]] = D.TEAMS[t]["rw"]
    for i in range(NG):
        h, a = g_home[i], g_away[i]
        hw, o = home_wins[i], ot[i]
        lw = ~hw
        pts[h] += (hw.astype(np.int16) << 1) + (lw & o)
        pts[a] += (lw.astype(np.int16) << 1) + (hw & o)
        rw[h] += hw & ~o
        rw[a] += lw & ~o

    # points, then regulation wins, then a coin. rw never reaches 1000, so it can only
    # separate clubs level on points; the coin can only separate clubs level on both.
    score = pts + rw * 1e-3 + rng.random((NT, nsim)) * 1e-5
    cols = np.arange(nsim)

    div_rank = np.zeros((NT, nsim), dtype=np.int8)
    for d, members in D.DIVISIONS.items():
        rows = np.array([idx[m] for m in members])
        order = np.argsort(-score[rows], axis=0)
        for k in range(len(rows)):
            div_rank[rows[order[k]], cols] = k + 1

    wc_rank = np.zeros((NT, nsim), dtype=np.int8)
    for c in D.CONFERENCES:
        rows = np.array([idx[t] for t in CONF_TEAMS[c]])
        s = np.where(div_rank[rows] <= 3, -np.inf, score[rows])
        order = np.argsort(-s, axis=0)
        for k in range(2):
            wc_rank[rows[order[k]], cols] = k + 1

    playoff = (div_rank <= 3) | (wc_rank > 0)
    J = idx[FOCUS]

    focus_won = np.empty((len(focus_game_ix), nsim), dtype=bool)
    focus_ot = np.empty((len(focus_game_ix), nsim), dtype=bool)
    for k, i in enumerate(focus_game_ix):
        _, a, h = games[i]
        focus_won[k] = home_wins[i] if h == FOCUS else ~home_wins[i]
        focus_ot[k] = ot[i]

    return State(pts=pts, rw=rw, score=score, div_rank=div_rank, wc_rank=wc_rank,
                 playoff=playoff, focus_in=playoff[J], focus_pts=pts[J],
                 focus_won=focus_won, focus_ot=focus_ot,
                 home_wins=home_wins, ot=ot, nsim=nsim)


# ---------------------------------------------------------------- around the league
def around_the_league(st, live_lo=0.05, live_hi=0.98):
    """Every remaining game Toronto is NOT playing, scored against Toronto's odds.

    P(in | home wins) - P(in | away wins), read off the same simulated seasons. Only
    games touching the focus conference are scored — a Western game cannot move the
    Eastern field. Anything inside twice its own Monte Carlo error is a toss-up: below
    that, which way the difference points is the random number generator, not hockey.
    """
    fin = st.focus_in
    nsim = int(fin.shape[0])
    po = {t: float(st.playoff[idx[t]].mean()) for t in TEAMS}
    out = []
    for i, (date, a, h) in enumerate(games):
        if FOCUS in (a, h) or (CONF[a] != FOCUS_CONF and CONF[h] != FOCUS_CONF):
            continue
        w = st.home_wins[i]
        nw = int(w.sum())
        if nw == 0 or nw == nsim:
            continue
        p1, p2 = float(fin[w].mean()), float(fin[~w].mean())
        lv = p1 - p2
        se = math.sqrt(p1 * (1 - p1) / nw + p2 * (1 - p2) / (nsim - nw))
        out.append({
            "date": date, "away": a, "home": h,
            "root": h if lv > 0 else a, "leverage": abs(lv),
            "sure": bool(abs(lv) > 2 * se),
            "h2h": bool(live_lo < po[a] < live_hi and live_lo < po[h] < live_hi),
        })
    out.sort(key=lambda g: (g["date"], -g["leverage"]))
    return out


# ---------------------------------------------------------------- the bracket
# 2-2-1-1-1: True = the club with home ice hosts that game
SERIES = [True, True, False, False, True, False, True]


def _matchup_vec(tal_a, tal_b, a_home):
    p = (tal_a - tal_a * tal_b) / (tal_a + tal_b - 2 * tal_a * tal_b)
    if a_home:
        o = p / (1 - p) * HFA_ODDS
        return o / (1 + o)
    o = (1 - p) / p * HFA_ODDS
    return 1 / (1 + o)


def play_series(rng, tal_a, tal_b, pattern=SERIES):
    """Does A win? One draw per game, majority takes it.

    Playing all seven rather than stopping at the fourth win gives the identical winner —
    whoever gets there first necessarily holds the majority of seven — and lets a whole
    round resolve as one vectorised pass over every simulated season.
    """
    a_wins = np.zeros(len(tal_a), dtype=np.int16)
    for a_home in pattern:
        a_wins += rng.random(len(tal_a)) < _matchup_vec(tal_a, tal_b, a_home)
    return a_wins > len(pattern) // 2


def seats_of(st, conf):
    """A conference's eight first-round seats, structurally, as an (8, nsim) array.

    Order: [D1 winner, the wild card it draws, D1 2nd, D1 3rd,
            D2 winner, the wild card it draws, D2 2nd, D2 3rd]
    with D1 and D2 the conference's divisions in alphabetical order. The better division
    winner draws the SECOND wild card, so which wild card sits in seat 1 versus seat 5
    changes season to season.
    """
    nsim = st.score.shape[1]
    cols = np.arange(nsim)
    d1, d2 = D.CONFERENCES[conf]

    def div_seat(div, rank):
        rows = np.array([idx[t] for t in D.DIVISIONS[div]])
        return rows[np.argmax(st.div_rank[rows] == rank, axis=0)]

    crows = np.array([idx[t] for t in CONF_TEAMS[conf]])
    wc1 = crows[np.argmax(st.wc_rank[crows] == 1, axis=0)]
    wc2 = crows[np.argmax(st.wc_rank[crows] == 2, axis=0)]
    w1, w2 = div_seat(d1, 1), div_seat(d2, 1)
    w1_top = st.score[w1, cols] > st.score[w2, cols]
    return np.vstack([
        w1, np.where(w1_top, wc2, wc1), div_seat(d1, 2), div_seat(d1, 3),
        w2, np.where(w1_top, wc1, wc2), div_seat(d2, 2), div_seat(d2, 3),
    ])


def postseason(st, rng):
    """Play the whole playoffs out, both conferences and the Final.

    Returns every node of the bracket as an (nsim,) array of team indices. Home ice in
    every series goes to the better regular season, as the NHL awards it.
    """
    tal = np.array([talent[t] for t in TEAMS])
    cols = np.arange(st.score.shape[1])

    def play(a, b):
        a_hosts = st.score[a, cols] >= st.score[b, cols]
        hi = np.where(a_hosts, a, b)
        lo = np.where(a_hosts, b, a)
        return np.where(play_series(rng, tal[hi], tal[lo]), hi, lo)

    out = {}
    for c in sorted(D.CONFERENCES):
        p = "E" if c == "Eastern" else "W"
        s = seats_of(st, c)
        for k in range(8):
            out[f"{p}{k + 1}"] = s[k]
        r1 = [play(s[0], s[1]), play(s[2], s[3]), play(s[4], s[5]), play(s[6], s[7])]
        for k, v in enumerate(r1):
            out[f"{p}r1{'abcd'[k]}"] = v
        r2 = [play(r1[0], r1[1]), play(r1[2], r1[3])]
        out[f"{p}r2a"], out[f"{p}r2b"] = r2
        out[f"{p}cf"] = play(r2[0], r2[1])
    out["cup"] = play(out["Ecf"], out["Wcf"])
    return out


def focus_label(div_rank, wc_rank):
    """'3rd in the Atlantic' or 'the second wild card', from a club's final placing."""
    if wc_rank == 1:
        return "first wild card"
    if wc_rank == 2:
        return "second wild card"
    return f"{_ordinal(int(div_rank))} in the {FOCUS_DIV}"


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# which two nodes feed each later node, per conference prefix
FEEDERS = {}
for _p in ("E", "W"):
    FEEDERS.update({f"{_p}r1a": (f"{_p}1", f"{_p}2"), f"{_p}r1b": (f"{_p}3", f"{_p}4"),
                    f"{_p}r1c": (f"{_p}5", f"{_p}6"), f"{_p}r1d": (f"{_p}7", f"{_p}8"),
                    f"{_p}r2a": (f"{_p}r1a", f"{_p}r1b"), f"{_p}r2b": (f"{_p}r1c", f"{_p}r1d"),
                    f"{_p}cf": (f"{_p}r2a", f"{_p}r2b")})
FEEDERS["cup"] = ("Ecf", "Wcf")


def coherent_picks(counts, pins):
    """One club per slot, so the bracket reads as a single picture.

    Picking each slot's likeliest club on its own lets one strong club fill three seats
    at once — early in a season nearly every seat is a coin flip among the same few. So:
    pinned seats first, then the remaining seats greedily, likeliest (seat, club) pair
    first, each club used once; then every later slot takes whichever of its two feeder
    clubs wins that series more often. app.js does the same with the live counts.
    """
    picks = dict(pins)
    used = set(pins.values())
    seats = [k for k in counts if k[1:].isdigit() and k not in picks]
    cand = sorted(((n, k, t) for k in seats for t, n in counts[k].items()),
                  key=lambda x: (-x[0], x[1], x[2]))
    for n, k, t in cand:
        if k not in picks and t not in used:
            picks[k] = t
            used.add(t)
    for k in FEEDERS:                       # insertion order runs round by round
        if k not in counts:
            continue
        a, b = (picks.get(f) for f in FEEDERS[k])
        opts = [t for t in (a, b) if t is not None]
        picks[k] = max(opts, key=lambda t: counts[k].get(t, 0)) if opts else None
    return picks


def bracket(st, per_slot=4):
    """Where Toronto lands and how far it goes, GIVEN that it qualifies.

    Every number is conditional on making the field, and the page says so. Read off the
    same simulated seasons as the headline, so the bracket cannot disagree with the odds.
    Returns None when nothing qualifies.
    """
    fin = st.focus_in
    n_in = int(fin.sum())
    if not n_in:
        return None
    J = idx[FOCUS]
    m = fin
    rng = np.random.default_rng(SEED + 7)
    ps = postseason(st, rng)

    p = "E" if FOCUS_CONF == "Eastern" else "W"
    seats = np.vstack([ps[f"{p}{k}"] for k in range(1, 9)])
    j_seat = np.argmax(seats == J, axis=0) + 1                    # 1..8
    seat_dist = collections.Counter(j_seat[m].tolist())
    best_seat = max(seat_dist, key=seat_dist.get)

    # Toronto's first-round opponent: the other seat in its pair
    partner = {1: 2, 2: 1, 3: 4, 4: 3, 5: 6, 6: 5, 7: 8, 8: 7}
    nsim = seats.shape[1]
    opp = seats[np.array([partner[s] for s in j_seat]) - 1, np.arange(nsim)]
    opps = [{"team": TEAMS[t], "p": c / n_in}
            for t, c in sorted(collections.Counter(opp[m].tolist()).items(),
                               key=lambda kv: -kv[1])][:per_slot]
    cols = np.arange(nsim)
    hosts_r1 = st.score[J, cols] > st.score[opp, cols]

    labels = collections.Counter(
        focus_label(st.div_rank[J, i], st.wc_rank[J, i]) for i in np.flatnonzero(m))

    # The headline has to describe the seat the bracket actually pins Toronto to, and the
    # opponent it meets THERE. The likeliest placing ("second wild card") and the likeliest
    # seat can disagree, because a wild card lands in either half of the bracket depending
    # on which division winner is better — so the headline is read off the seat.
    in_best = m & (j_seat == best_seat)
    seat_opp = collections.Counter(opp[in_best].tolist())
    best_opp = TEAMS[max(seat_opp, key=seat_opp.get)] if seat_opp else None
    d1, d2 = D.CONFERENCES[FOCUS_CONF]
    div_of_seat = d1 if best_seat <= 4 else d2
    role = {1: f"winning the {div_of_seat}", 2: "a wild card",
            3: f"2nd in the {div_of_seat}", 4: f"3rd in the {div_of_seat}"}[
        (best_seat - 1) % 4 + 1]
    best_label = role

    counts = {key: collections.Counter(arr[m].tolist()) for key, arr in ps.items()}
    pins = {f"{p}{best_seat}": J}
    if best_opp is not None:
        pins[f"{p}{partner[best_seat]}"] = idx[best_opp]
    picks = coherent_picks(counts, pins)

    nodes = {}
    for key, c in counts.items():
        rows = [{"team": TEAMS[t], "p": n / n_in}
                for t, n in sorted(c.items(), key=lambda kv: -kv[1])]
        pick = TEAMS[picks[key]] if picks.get(key) is not None else None
        if pick is not None:
            mine = [r for r in rows if r["team"] == pick] or [{"team": pick, "p": 0.0}]
            rows = mine + [r for r in rows if r["team"] != pick]
        nodes[key] = rows[:per_slot]

    return {
        "p_qualify": float(fin.mean()), "n_qualifying": n_in,
        "focus_conf": p, "best_seat": int(best_seat),
        "seat_dist": {int(k): v / n_in for k, v in seat_dist.items()},
        "best_label": best_label,
        "best_seat_p": float(in_best.sum() / n_in),
        "best_seat_opponent": best_opp,
        "best_seat_hosts": float(hosts_r1[in_best].mean()) if in_best.any() else 0.0,
        "labels": {k: v / n_in for k, v in labels.most_common()},
        "opponent": opps, "p_home_r1": float(hosts_r1[m].mean()),
        "nodes": nodes,
        "road": {
            "r1": float(((ps[f"{p}r1a"] == J) | (ps[f"{p}r1b"] == J)
                         | (ps[f"{p}r1c"] == J) | (ps[f"{p}r1d"] == J))[m].mean()),
            "r2": float(((ps[f"{p}r2a"] == J) | (ps[f"{p}r2b"] == J))[m].mean()),
            "cf": float((ps[f"{p}cf"] == J)[m].mean()),
            "cup": float((ps["cup"] == J)[m].mean()),
        },
        "divisions": list(D.CONFERENCES[FOCUS_CONF]),
        "other_divisions": list(D.CONFERENCES[
            [c for c in D.CONFERENCES if c != FOCUS_CONF][0]]),
    }


# ---------------------------------------------------------------- state cache
def _key():
    return f"{D.FINGERPRINT}|{SEED}|{NSIM}|{NG}|{len(focus_game_ix)}"


def save_state(st):
    """Persist what the downstream scripts need (a few MB, not the full game arrays)."""
    np.savez(STATE, key=np.array(_key()), focus_won=st.focus_won, focus_ot=st.focus_ot,
             focus_in=st.focus_in, focus_pts=st.focus_pts)


def load_state():
    try:
        z = np.load(STATE, allow_pickle=False)
        if str(z["key"]) == _key():
            return State(focus_won=z["focus_won"], focus_ot=z["focus_ot"],
                         focus_in=z["focus_in"], focus_pts=z["focus_pts"])
        print("  note: sim_state.npz is stale — resimulating")
    except FileNotFoundError:
        print("  note: no sim_state.npz — resimulating")
    return simulate()
