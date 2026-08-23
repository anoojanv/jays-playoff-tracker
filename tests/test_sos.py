"""
Strength of schedule.

The number is what a league-average club would win against a team's remaining
opponents. Two properties make it worth showing, and neither is visible in the output:

  * it is independent of the club's own quality, so two teams can be compared directly
  * it uses the same matchup maths the simulation uses, so it describes the odds rather
    than telling a different story from them

Run:  python tests/test_sos.py
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

import model  # noqa: E402

JAYS = model.JAYS
CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("every AL club gets a value, and they are plausible win rates")
def _():
    sos = model.strength_of_schedule()
    assert set(sos) == set(model.AL_TEAMS), sorted(sos)
    for t, v in sos.items():
        assert 0.30 < v < 0.70, (t, v)


@case("a club's own quality does not move its own number")
def _():
    # The point of holding talent at .500 is that a club's rating cannot flatter itself.
    before = model.strength_of_schedule()
    original = model.talent[JAYS]
    try:
        model.talent[JAYS] = 0.900          # make Toronto enormously good
        after = model.strength_of_schedule()
    finally:
        model.talent[JAYS] = original
    assert abs(after[JAYS] - before[JAYS]) < 1e-12, (before[JAYS], after[JAYS])


@case("but it does move the number for everyone who has to play them")
def _():
    before = model.strength_of_schedule()
    opponents = {a if h == JAYS else h
                 for _, a, h in model.games if JAYS in (a, h)} & set(model.AL_TEAMS)
    assert opponents, "fixture should have AL clubs facing Toronto"
    original = model.talent[JAYS]
    try:
        model.talent[JAYS] = 0.900
        after = model.strength_of_schedule()
    finally:
        model.talent[JAYS] = original
    for t in opponents:
        assert after[t] < before[t], f"{t} should face a harder road, {before[t]} -> {after[t]}"


@case("a tougher opponent lowers the expected win rate")
def _():
    strong = model.matchup(model.NEUTRAL, 0.600, True)
    weak = model.matchup(model.NEUTRAL, 0.400, True)
    assert strong < weak, (strong, weak)


@case("home field is worth something, and the same game is not scored twice")
def _():
    home = model.matchup(model.NEUTRAL, 0.500, True)
    away = model.matchup(model.NEUTRAL, 0.500, False)
    assert home > 0.5 > away, (home, away)
    assert abs((home + away) - 1.0) < 1e-9, "even-talent home and road must be complements"


@case("it agrees with the probabilities actually simulated")
def _():
    # p_home drives the Monte Carlo; SOS must be built from the same function, or the
    # column would quietly describe a different model from the one producing the odds.
    for i, (_, a, h) in enumerate(model.games[:40]):
        assert abs(model.matchup(model.talent[h], model.talent[a], True)
                   - model.p_home[i]) < 1e-12, (i, a, h)


@case("the hardest and easiest schedules are meaningfully apart")
def _():
    sos = model.strength_of_schedule()
    spread = max(sos.values()) - min(sos.values())
    assert spread > 0.005, f"spread of {spread:.4f} is too small to be worth showing"


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
        print(f"SOS TEST FAILED ({len(fails)} of {len(CASES)})")
        return 1
    print(f"SOS TEST PASSED — all {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
