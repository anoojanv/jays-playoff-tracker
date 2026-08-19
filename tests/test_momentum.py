"""
The momentum rating.

It is deliberately not "last 10 record": every game is scored against the probability
the model itself assigns it, so the rating answers "are they playing above or below
their own level" rather than "are they above .500". These cases pin the two properties
that make it worth showing at all — opponent adjustment and recency weighting — because
both are invisible in the final number and easy to break silently.

Run:  python tests/test_momentum.py
"""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
os.chdir(SRC)                    # model.py loads build/data.json relative to src/

import model                     # noqa: E402


def rate(results, opp="Angels", home=True):
    model.D.RECENT = [{"date": f"2026-08-{i + 1:02d}", "opp": opp, "home": home, "won": w}
                      for i, w in enumerate(results)]
    return model.momentum()


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("no games to measure yields no rating, not a zero")
def _():
    # a zero would render as "Steady", which is a claim; absence is the honest output
    assert rate([]) is None


@case("splitting with a weak club is underperformance, not neutral")
def _():
    weak = rate([True, False] * 5, opp="Angels")
    assert weak["index"] < -5, weak
    assert weak["label"] in ("Cold", "Ice cold"), weak


@case("the same 5-5 against the best club is playing to level")
def _():
    strong = rate([True, False] * 5, opp="Rays")
    assert abs(strong["index"]) <= 5, strong
    assert strong["label"] == "Steady", strong


@case("opponent quality moves the rating for an identical record")
def _():
    assert rate([True, False] * 5, opp="Rays")["index"] > \
           rate([True, False] * 5, opp="Angels")["index"]


@case("recency is weighted: finishing hot beats starting hot")
def _():
    late = rate([False] * 5 + [True] * 5, opp="Royals")
    early = rate([True] * 5 + [False] * 5, opp="Royals")
    assert late["index"] > early["index"], (late, early)


@case("winning everything is positive, losing everything negative")
def _():
    assert rate([True] * 10)["index"] > 0
    assert rate([False] * 10)["index"] < 0


@case("home and road are not scored the same")
def _():
    # the same 5-5 is worth more on the road, where the model expected less
    assert rate([True, False] * 5, opp="Rays", home=False)["index"] > \
           rate([True, False] * 5, opp="Rays", home=True)["index"]


@case("the last-10 summary matches the games handed in")
def _():
    m = rate([True] * 3 + [False] * 2 + [True] * 4 + [False], opp="Royals")
    assert (m["l10_w"], m["l10_l"]) == (7, 3), m
    assert 0 < m["l10_expected_w"] < 10, m


@case("only the last `window` games count")
def _():
    long_run = rate([False] * 60 + [True] * 10, opp="Royals")
    assert long_run["window"] == 25, long_run
    assert long_run["index"] > 0, long_run     # the ancient losses must not dominate


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
        print(f"MOMENTUM TEST FAILED ({len(fails)} of {len(CASES)})")
        return 1
    print(f"MOMENTUM TEST PASSED — all {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
