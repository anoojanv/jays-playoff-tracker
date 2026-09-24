"""
The NHL's scoring and qualifying rules, checked against the simulated seasons.

A win is two points whether it came in regulation, overtime or a shootout; the loser
takes one only past regulation. Standings run on points, then regulation wins. Three
per division qualify, then two wild cards per conference.

Run:  python tests/test_points.py
"""
import sys
import numpy as np
from _harness import case, run, load

model = load()
st = model.simulate(nsim=4000, seed=7)
N_LEFT = model.NG


@case("every game hands out two points, or three if it went past regulation")
def _():
    base = sum(model.D.points(t) for t in model.TEAMS)
    added = st.pts.sum(axis=0).astype(np.int64) - base
    extra = st.ot.sum(axis=0)
    assert np.array_equal(added, 2 * N_LEFT + extra)


@case("regulation wins only come from games decided in regulation")
def _():
    base = sum(model.D.TEAMS[t]["rw"] for t in model.TEAMS)
    added = st.rw.sum(axis=0).astype(np.int64) - base
    assert np.array_equal(added, N_LEFT - st.ot.sum(axis=0))


@case("games past regulation happen at the measured rate")
def _():
    share = st.ot.mean()
    assert abs(share - model.P_OT) < 0.01, share


@case("eight clubs qualify in each conference: three per division, two wild cards")
def _():
    for conf, divs in model.D.CONFERENCES.items():
        rows = [model.idx[t] for t in model.CONF_TEAMS[conf]]
        assert np.all(st.playoff[rows].sum(axis=0) == 8), conf
        assert np.all((st.wc_rank[rows] == 1).sum(axis=0) == 1)
        assert np.all((st.wc_rank[rows] == 2).sum(axis=0) == 1)
        for d in divs:
            drows = [model.idx[t] for t in model.D.DIVISIONS[d]]
            assert np.all((st.div_rank[drows] <= 3).sum(axis=0) == 3), d
            # a wild card never comes from a club that finished top three
            assert not np.any((st.wc_rank[drows] > 0) & (st.div_rank[drows] <= 3))


@case("the wild cards are the best of the rest, on points then regulation wins")
def _():
    for s in range(200):
        for conf in model.D.CONFERENCES:
            rows = [model.idx[t] for t in model.CONF_TEAMS[conf]]
            rest = [r for r in rows if st.div_rank[r, s] > 3]
            best = sorted(rest, key=lambda r: -st.score[r, s])[:2]
            assert st.wc_rank[best[0], s] == 1 and st.wc_rank[best[1], s] == 2


@case("the tiebreak: level on points, more regulation wins finishes higher")
def _():
    hits = 0
    for s in range(4000):
        for d, members in model.D.DIVISIONS.items():
            rows = [model.idx[t] for t in members]
            for i in rows:
                for j in rows:
                    if i < j and st.pts[i, s] == st.pts[j, s] and st.rw[i, s] != st.rw[j, s]:
                        hi, lo = (i, j) if st.rw[i, s] > st.rw[j, s] else (j, i)
                        assert st.div_rank[hi, s] < st.div_rank[lo, s]
                        hits += 1
    assert hits > 50, f"only {hits} ties seen — the case is not being exercised"


@case("a matchup is one probability seen from both benches")
def _():
    for a, b in [(0.6, 0.45), (0.5, 0.5), (0.3, 0.7)]:
        p = model.matchup(a, b, True)
        q = model.matchup(b, a, False)
        assert abs(p + q - 1) < 1e-12
    assert model.matchup(0.5, 0.5, True) > 0.5 > model.matchup(0.5, 0.5, False)


@case("expected points: two for a win, one for a loss past regulation")
def _():
    assert abs(model.exp_points(1.0) - 2.0) < 1e-12
    assert abs(model.exp_points(0.0) - model.P_OT) < 1e-12
    assert abs(model.exp_points(0.5, 0.25) - (1.0 + 0.125)) < 1e-12


@case("talent sits strictly between 0 and 1, and more regression pulls it toward .500")
def _():
    for t, v in model.talent.items():
        assert 0 < v < 1, (t, v)
    spread = lambda tal: np.std([v - 0.5 for v in tal.values()])
    assert spread(model.build_talent(reg_prior=200)) < spread(model.talent)
    assert spread(model.build_talent(reg_prior=5)) > spread(model.talent)
    # and last season is part of the estimate: dropping it changes the ratings
    no_prior = model.build_talent(prior_weight=0.0)
    assert max(abs(no_prior[t] - model.talent[t]) for t in model.TEAMS) > 0.005


if __name__ == "__main__":
    sys.exit(run("POINTS TEST"))
