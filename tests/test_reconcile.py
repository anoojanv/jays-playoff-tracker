"""
Standings are summed from the schedule, so they reconcile by construction — these cases
pin down that the model still refuses a world where they don't, and stops cleanly once
there is nothing left to play.

Run:  python tests/test_reconcile.py
"""
import sys
from _harness import case, run, load, fixture, pts


@case("the fixture reconciles: games played plus games left is 84 for every club")
def _():
    model = load()
    for t in model.TEAMS:
        assert model.D.played(t) + model.rem[t] == 84, t


@case("a club one game short is refused, and the message names it")
def _():
    def edit(d):
        d["TEAMS"]["BOS"]["w"] -= 1
    try:
        load(edit)
    except SystemExit as e:
        assert "does not reconcile" in str(e) and "BOS" in str(e), e
    else:
        raise AssertionError("a club at 83 games was accepted")


@case("a game dropped from the schedule is refused for both clubs in it")
def _():
    dropped = {}

    def edit(d):
        g = d["GAMES"].pop(0)
        dropped["g"] = g
    try:
        load(edit)
    except SystemExit as e:
        _, a, h = dropped["g"]
        assert a in str(e) and h in str(e), e
    else:
        raise AssertionError("a missing game was accepted")


@case("no games left for Toronto is a clean stop, not a crash")
def _():
    def edit(d):
        tor = d["TEAMS"]["TOR"]
        left = [g for g in d["GAMES"] if "TOR" in g[1:]]
        d["GAMES"] = [g for g in d["GAMES"] if "TOR" not in g[1:]]
        tor["w"] += len(left)
        # every opponent loses that game
        for _, a, h in left:
            opp = h if a == "TOR" else a
            d["TEAMS"][opp]["l"] += 1
    try:
        load(edit)
    except SystemExit as e:
        assert "SEASON COMPLETE" in str(e), e
    else:
        raise AssertionError("an empty schedule simulated anyway")


@case("points are two a win plus one an overtime loss")
def _():
    model = load()
    d = fixture()
    for t, rec in d["TEAMS"].items():
        assert model.D.points(t) == pts(rec), t


if __name__ == "__main__":
    sys.exit(run("RECONCILE TEST"))
