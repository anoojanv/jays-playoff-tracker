"""
The momentum rating: how Toronto is playing against how the model expected, weighted
toward recent games. Zero is "playing to their own level", which is not the same as
.500 — an underdog splitting its games is running hot.

Run:  python tests/test_momentum.py
"""
import sys
from _harness import case, run, load


def with_recent(games):
    def edit(d):
        d["RECENT"] = games
    return load(edit)


def game(i, opp, won, home=True, ot=False):
    return {"date": f"2027-01-{i + 1:02d}", "opp": opp, "home": home, "won": won, "ot": ot}


@case("nothing to measure: no rating before three games")
def _():
    m = with_recent([game(0, "BOS", True), game(1, "MTL", False)])
    assert m.momentum() is None


@case("winning every game as the underdog reads hot")
def _():
    m = load()
    strong = sorted(m.TEAMS, key=lambda t: -m.talent[t])[:5]
    m = with_recent([game(i, strong[i % 5], True, home=False) for i in range(12)])
    r = m.momentum()
    assert r["index"] >= 15 and r["tone"] == "hot", r


@case("losing every game as the favourite reads cold")
def _():
    m = load()
    weak = sorted(m.TEAMS, key=lambda t: m.talent[t])[:5]
    m = with_recent([game(i, weak[i % 5], False) for i in range(12)])
    r = m.momentum()
    assert r["index"] <= -15 and r["tone"] == "icy", r


@case("recent games count more than old ones")
def _():
    m = load()
    opp = sorted(m.TEAMS, key=lambda t: abs(m.talent[t] - m.talent["TOR"]))[1]
    late_wins = [game(i, opp, i >= 10) for i in range(20)]
    early_wins = [game(i, opp, i < 10) for i in range(20)]
    a = with_recent(late_wins).momentum()["index"]
    b = with_recent(early_wins).momentum()["index"]
    assert a > 0 > b, (a, b)


@case("last ten splits wins, regulation losses and overtime losses")
def _():
    games = ([game(i, "MTL", True) for i in range(5)]
             + [game(5 + i, "MTL", False, ot=True) for i in range(2)]
             + [game(7 + i, "MTL", False) for i in range(3)])
    r = with_recent(games).momentum()
    assert (r["l10_w"], r["l10_l"], r["l10_otl"]) == (5, 3, 2), r


@case("the fixture's own recent form produces a rating")
def _():
    r = load().momentum()
    assert r is not None and r["games"] >= 10 and -100 <= r["index"] <= 100


if __name__ == "__main__":
    sys.exit(run("MOMENTUM TEST"))
