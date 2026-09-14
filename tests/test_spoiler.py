"""
Scoring the games Toronto is not playing.

A Blue Jays fan watching a Guardians game wants one thing: which side to root for, and
whether it is worth caring about. The page ranked clubs by how much their *finish*
mattered, which breaks down completely when two of those clubs play each other — the
Guardians and White Sox spent the last fortnight of 2026 fighting for the AL Central
while the page told fans to root against both of them.

The sign convention is the thing worth pinning down: get it backwards and the page tells
a hundred thousand people to cheer for the wrong team.

Run:  python tests/test_spoiler.py
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")

_build = os.path.join(ROOT, "build")
_data = os.path.join(_build, "data.json")
if not os.path.exists(_data):
    os.makedirs(_build, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "fixture_data.json"), _data)

sys.path.insert(0, SRC)
os.chdir(SRC)

import numpy as np  # noqa: E402
import model  # noqa: E402

JAYS = model.JAYS
CASES = []

# A real run is 120,000 seasons; the relationships under test hold at a fraction of that
# and this keeps the suite quick.
model.NSIM = 12_000
ST = model.simulate()
AROUND = model.around_the_league(ST)


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("Toronto's own games are never scored here")
def _():
    for g in AROUND:
        assert JAYS not in (g["away"], g["home"]), g


@case("every game names one side to root for, and a non-negative size")
def _():
    assert AROUND, "the fixture should leave plenty of games to score"
    for g in AROUND:
        assert g["root"] in (g["away"], g["home"]), g
        assert 0.0 <= g["leverage"] < 1.0, g


@case("the side to root for is the side that leaves Toronto better off")
def _():
    """The whole point. Recomputed straight from the simulated seasons."""
    for g in AROUND[:40]:
        i = model.games.index((g["date"], g["away"], g["home"]))
        w = ST.home_wins[i]
        p_home = ST.jays_in[w].mean()
        p_away = ST.jays_in[~w].mean()
        better = g["home"] if p_home > p_away else g["away"]
        assert g["root"] == better, (g, float(p_home), float(p_away))
        assert abs(g["leverage"] - abs(p_home - p_away)) < 1e-9, g


@case("beating up a club Toronto is chasing is what a fan wants")
def _():
    """Across the games the model will actually stand behind, involving one cluster club
    and one club that is not, the fan should be rooting against the cluster club.

    Only `sure` games are checked, and that is the point rather than a convenience: below
    a couple of standard errors the sign of these differences is Monte Carlo noise, which
    is exactly why the page reports those as toss-ups instead of naming a side."""
    agree = total = 0
    for g in AROUND:
        if not g["sure"]:
            continue
        inc = [t for t in (g["away"], g["home"]) if t in model.CLUSTER]
        if len(inc) != 1:
            continue
        total += 1
        agree += g["root"] != inc[0]
    assert total >= 5, f"only {total} such games in the fixture"
    assert agree / total > 0.95, f"rooted against the chaser in only {agree} of {total}"


@case("a toss-up is never dressed up as a recommendation")
def _():
    """The guard that keeps the sign honest: anything the page names a side for has to
    clear twice its own Monte Carlo error."""
    n_toss = 0
    for g in AROUND:
        i = model.games.index((g["date"], g["away"], g["home"]))
        w = ST.home_wins[i]
        p1, p2 = float(ST.jays_in[w].mean()), float(ST.jays_in[~w].mean())
        n1, n2 = int(w.sum()), int(ST.jays_in.shape[0] - w.sum())
        se = (p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2) ** 0.5
        assert g["sure"] == (abs(p1 - p2) > 2 * se), g
        n_toss += not g["sure"]
    assert n_toss, "a whole league of games and not one is too close to call?"


@case("a game between two live clubs is flagged, a dead one is not")
def _():
    po = {t: float(ST.playoff[model.idx[t]].mean()) for t in model.AL_TEAMS}
    for g in AROUND:
        live = [0.05 < po.get(t, 0.0) < 0.98 for t in (g["away"], g["home"])]
        assert g["h2h"] == all(live), (g, po.get(g["away"]), po.get(g["home"]))


@case("clubs with nothing left to play for barely move the number")
def _():
    dead = [g for g in AROUND
            if all(ST.playoff[model.idx[t]].mean() < 0.01
                   for t in (g["away"], g["home"]) if t in model.D.AL)]
    for g in dead:
        assert g["leverage"] < 0.03, g


@case("the games are ordered by date, then by what they are worth")
def _():
    keys = [(g["date"], -g["leverage"]) for g in AROUND]
    assert keys == sorted(keys), "not in date then leverage order"


def main():
    fails = []
    for name, fn in CASES:
        try:
            fn()
            print(f"  OK    {name}")
        except AssertionError as e:
            print(f"  FAIL  {name}\n        {e}")
            fails.append(name)
    print("\n" + "=" * 58)
    if fails:
        print(f"SPOILER TEST FAILED ({len(fails)} of {len(CASES)})")
        return 1
    print(f"SPOILER TEST PASSED — all {len(CASES)} cases, {len(AROUND)} games scored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
