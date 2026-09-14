"""
Seeding the AL field, and who Toronto actually plays.

The simulation always built the full playoff field and threw the seeding away, so the
page could say "39% to reach the playoffs" and nothing at all about what reaching them
looks like. Getting the format wrong would be worse than saying nothing, so the rules are
pinned here:

  * three division winners take seeds 1-3 BY RECORD — a 100-win wild card still seeds
    behind an 85-win division winner, which is the part people get wrong
  * the three wild cards take 4-6
  * seeds 1 and 2 sit out the Wild Card round; 3 hosts 6, 4 hosts 5

Run:  python tests/test_bracket.py
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
model.NSIM = 12_000
ST = model.simulate()
SEEDS = model.seeds_of(ST)
B = model.bracket(ST)
NS = SEEDS.shape[1]
CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("every season seeds exactly six distinct clubs")
def _():
    assert SEEDS.shape == (6, NS), SEEDS.shape
    for c in range(0, NS, 337):                      # a spread of seasons
        col = SEEDS[:, c]
        assert len(set(col.tolist())) == 6, col


@case("seeds 1-3 are the division winners, 4-6 the wild cards")
def _():
    dw, wc = ST.div_winner, ST.wc
    cols = np.arange(NS)
    for k in range(3):
        assert dw[SEEDS[k], cols].all(), f"seed {k+1} is not a division winner"
    for k in range(3, 6):
        assert wc[SEEDS[k], cols].all(), f"seed {k+1} is not a wild card"


@case("a division winner outranks a better-record wild card")
def _():
    """The rule people get wrong. Seed 3 can have a worse record than seed 4."""
    cols = np.arange(NS)
    s3 = ST.wins[SEEDS[2], cols]
    s4 = ST.wins[SEEDS[3], cols]
    assert (s3 < s4).any(), "no season had a wild card out-winning the 3 seed"
    # and it is still seeded third, which is what the assertion above already proved


@case("within each group, the better record seeds higher")
def _():
    cols = np.arange(NS)
    for a, b in ((0, 1), (1, 2), (3, 4), (4, 5)):
        hi = ST.score[SEEDS[a], cols]
        lo = ST.score[SEEDS[b], cols]
        assert (hi >= lo).all(), f"seed {a+1} ranked below seed {b+1}"


@case("Toronto's seed is the slot Toronto actually occupies")
def _():
    j = model.idx[JAYS]
    in_field = (SEEDS == j).any(axis=0)
    assert (in_field == ST.jays_in).all(), "seeded field disagrees with the odds"


@case("the Wild Card pairings are 3-6 and 4-5, and 1-2 sit it out")
def _():
    assert model.WC_OPPONENT == {3: 6, 6: 3, 4: 5, 5: 4}, model.WC_OPPONENT
    assert model.BYE_SEEDS == (1, 2)
    for s, o in model.WC_OPPONENT.items():
        assert model.WC_OPPONENT[o] == s, "pairing is not symmetric"
        assert s + o == 9, (s, o)


@case("the seed distribution is a distribution, and the bye agrees with it")
def _():
    tot = sum(B["jays_seed"].values())
    assert abs(tot - 1.0) < 1e-9, tot
    bye = sum(p for k, p in B["jays_seed"].items() if k in model.BYE_SEEDS)
    assert abs(bye - B["p_bye"]) < 1e-9, (bye, B["p_bye"])
    host = sum(p for k, p in B["jays_seed"].items() if k in (3, 4))
    assert abs(host - B["p_host"]) < 1e-9, (host, B["p_host"])


@case("the opponent is never Toronto, and a bye means no opponent")
def _():
    tot = sum(o["p"] for o in B["jays_opponent"])
    assert tot <= 1.0 + 1e-9, tot
    for o in B["jays_opponent"]:
        assert o["team"] != JAYS, "Toronto cannot play itself"
        assert o["team"] is None or o["team"] in model.AL_TEAMS, o
    bye = sum(o["p"] for o in B["jays_opponent"] if o["team"] is None)
    assert abs(bye - B["p_bye"]) < 0.02, (bye, B["p_bye"])


@case("Toronto is pinned to its likeliest seed and appears nowhere else")
def _():
    best = B["jays_best_seed"]
    assert B["slots"][best][0]["team"] == JAYS, B["slots"][best][:2]
    for k, rows in B["slots"].items():
        if k == best:
            continue
        assert all(r["team"] != JAYS for r in rows), (k, rows)


@case("an eliminated club gets no bracket instead of a crash")
def _():
    """Every September somebody is out, and that is exactly when the build must keep
    publishing rather than divide by a field of zero qualifying seasons."""
    class Dead:
        jays_in = np.zeros(NS, dtype=bool)
    assert model.bracket(Dead()) is None


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
        print(f"BRACKET TEST FAILED ({len(fails)} of {len(CASES)})")
        return 1
    print(f"BRACKET TEST PASSED — all {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
