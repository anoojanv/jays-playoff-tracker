"""
The 162-game reconciliation, in both directions.

The schedule and the standings come from two different MLB endpoints that do not update
in lockstep, so a club can briefly reconcile to 161 or 163:

  161  a postponement not yet rescheduled          -> SYNTHETIC_GAMES adds it back
  163  a played game still listed as scheduled     -> drop_phantoms(), or IGNORE_GAMES

The 163 case took the nightly build down on 2026-08-16 (Twins 124 + 39 = 163) and had no
remedy at all: SYNTHETIC_GAMES only adds games. drop_phantoms() resolves the unambiguous
version of it and nothing else — the point of these cases is as much what it declines to
touch as what it fixes.

Run:  python tests/test_reconcile.py
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location("fd", os.path.join(ROOT, "src", "fetch_data.py"))
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)

AS_OF = "2026-08-20"
FUTURE, PAST = "2026-09-01", "2026-08-19"


def world(games, played):
    """An AL of four clubs with the given games-played, plus a schedule."""
    al = {t: {"gp": gp, "w": gp // 2, "l": gp - gp // 2, "rs": 0, "ra": 0}
          for t, gp in played.items()}
    return [list(g) for g in games], al


def counts(games, al):
    rem = fd.remaining(games, al)
    return {t: al[t]["gp"] + rem[t] for t in al}


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("a played game still listed as scheduled is dropped")
def _():
    # A and B both sit at 163: they played each other yesterday, the standings counted
    # it, the schedule has not caught up.
    games, al = world([(PAST, "A", "B"), (FUTURE, "A", "B"), (FUTURE, "C", "D")],
                      {"A": 161, "B": 161, "C": 161, "D": 161})
    dropped = fd.drop_phantoms(games, al, AS_OF)
    assert dropped == [(PAST, "A", "B")], dropped
    assert set(counts(games, al).values()) == {162}, counts(games, al)


@case("a future game is never dropped, however wrong the count")
def _():
    # Same over-count, but the only candidate is in the future — that is a real fixture,
    # so this must refuse and let the caller fail loudly instead.
    games, al = world([(FUTURE, "A", "B"), (FUTURE, "C", "D")],
                      {"A": 162, "B": 162, "C": 161, "D": 161})
    dropped = fd.drop_phantoms(games, al, AS_OF)
    assert dropped == [], dropped
    assert counts(games, al)["A"] == 163


@case("a one-sided mismatch is left alone")
def _():
    # Only A is over. Dropping the past game would fix A and break B, so the mismatch is
    # something other than a stale listing and must not be touched.
    games, al = world([(PAST, "A", "B"), (FUTURE, "C", "D")],
                      {"A": 162, "B": 160, "C": 161, "D": 161})
    dropped = fd.drop_phantoms(games, al, AS_OF)
    assert dropped == [], dropped


@case("an interleague phantom drops on the AL club alone")
def _():
    # The opponent is not in the AL, so there is no second club to corroborate; the AL
    # club being over is the whole signal.
    games, al = world([(PAST, "A", "Mets"), (FUTURE, "C", "D")],
                      {"A": 162, "C": 161, "D": 161})
    dropped = fd.drop_phantoms(games, al, AS_OF)
    assert dropped == [(PAST, "A", "Mets")], dropped
    assert counts(games, al)["A"] == 162


@case("a doubleheader's worth of phantoms both go")
def _():
    # A and B are at 164: three games listed, two of them already played. One drop is
    # not enough, so this also checks the loop keeps going rather than stopping early.
    games, al = world([(PAST, "A", "B"), (PAST, "A", "B"),
                       (FUTURE, "A", "B"), (FUTURE, "C", "D")],
                      {"A": 161, "B": 161, "C": 161, "D": 161})
    assert counts(games, al)["A"] == 164, counts(games, al)
    dropped = fd.drop_phantoms(games, al, AS_OF)
    assert len(dropped) == 2, dropped
    assert set(counts(games, al).values()) == {162}, counts(games, al)


@case("a club short of 162 is not this function's problem")
def _():
    games, al = world([(FUTURE, "A", "B"), (FUTURE, "C", "D")],
                      {"A": 160, "B": 160, "C": 161, "D": 161})
    dropped = fd.drop_phantoms(games, al, AS_OF)
    assert dropped == [], dropped
    assert counts(games, al)["A"] == 161      # left for SYNTHETIC_GAMES / the 162 check


@case("nothing to do on a clean schedule")
def _():
    games, al = world([(FUTURE, "A", "B"), (FUTURE, "C", "D")],
                      {"A": 161, "B": 161, "C": 161, "D": 161})
    assert fd.drop_phantoms(games, al, AS_OF) == []
    assert set(counts(games, al).values()) == {162}


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
        print(f"RECONCILE TEST FAILED ({len(fails)} of {len(CASES)})")
        return 1
    print(f"RECONCILE TEST PASSED — all {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
