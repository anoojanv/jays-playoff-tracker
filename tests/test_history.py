"""
The day-over-day deltas, and the history the page carries to make them possible.

The page is its own state file: each build reads the previous page's history, appends
today's reading, and republishes. That is the only reason a delta exists without a
database — and it means the awkward cases are about time, not arithmetic:

  * the site rebuilds up to twenty times a day, so a naive "since last publish" delta
    would be a single game's noise rather than a day's movement
  * on the first build, and for a while after, there is nothing 24 hours back. The page
    must show no delta rather than inventing one against whatever is nearest.

Run:  python tests/test_history.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

import history as H  # noqa: E402

HOUR = 3600
NOW = 1_800_000_000
CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("a round trip through the encoding preserves every reading")
def _():
    pts = [(NOW - 2 * HOUR, 663, 25), (NOW - HOUR, 661, None), (NOW, 670, -3)]
    assert H.parse(H.encode(pts)) == pts, H.parse(H.encode(pts))


@case("it reads its own meta tag out of a full page")
def _():
    page = '<html><head><meta name="page-history" content="100:500:7"></head></html>'
    assert H.parse(page) == [(100, 500, 7)]


@case("junk in the tag is skipped, not fatal")
def _():
    assert H.parse("100:500:7,,garbage,:::,200:x:1,300:600:") == [(100, 500, 7), (300, 600, None)]


@case("nothing to compare against yields no delta, not a zero")
def _():
    # a fabricated "no change" on day one would be a claim, not an absence
    assert H.delta([], NOW, 0.663, 25) is None


@case("a point only hours old is not passed off as yesterday")
def _():
    recent = [(NOW - 3 * HOUR, 581, 9)]
    assert H.delta(recent, NOW, 0.663, 25) is None


@case("a point roughly a day back is used, and signed correctly")
def _():
    pts = [(NOW - 24 * HOUR, 581, 9)]
    d = H.delta(pts, NOW, 0.663, 25)
    assert d is not None
    assert abs(d["odds"] - 0.082) < 1e-9, d
    assert d["momentum"] == 16, d
    assert 23.9 < d["age_hours"] < 24.1, d


@case("a fall is negative in both figures")
def _():
    d = H.delta([(NOW - 24 * HOUR, 710, 40)], NOW, 0.663, 25)
    assert d["odds"] < 0 and d["momentum"] < 0, d


@case("the nearest point to 24h wins when several are in range")
def _():
    pts = [(NOW - 30 * HOUR, 500, 1), (NOW - 23 * HOUR, 600, 2), (NOW - 14 * HOUR, 700, 3)]
    d = H.delta(pts, NOW, 0.663, 25)
    assert abs(d["prev_odds"] - 0.600) < 1e-9, d


@case("momentum delta is absent when either side had none")
def _():
    assert H.delta([(NOW - 24 * HOUR, 581, None)], NOW, 0.663, 25)["momentum"] is None
    assert H.delta([(NOW - 24 * HOUR, 581, 9)], NOW, 0.663, None)["momentum"] is None


@case("rebuilds minutes apart collapse instead of accumulating")
def _():
    pts = []
    for i in range(10):
        pts = H.append(pts, NOW + i * 60, 0.663, 25)     # ten rebuilds, ten minutes
    assert len(pts) == 1, pts
    assert pts[0][0] == NOW + 9 * 60, pts               # the newest reading survives


@case("readings a day apart both survive")
def _():
    pts = H.append([], NOW - 24 * HOUR, 0.581, 9)
    pts = H.append(pts, NOW, 0.663, 25)
    assert len(pts) == 2, pts


@case("history cannot grow without bound")
def _():
    pts = []
    for i in range(4000):                                # ~3 months of hourly builds
        pts = H.append(pts, NOW + i * HOUR, 0.5, 0)
    assert len(pts) <= H.MAX_POINTS, len(pts)
    assert len(H.encode(pts)) < 6000, len(H.encode(pts))
    oldest = NOW + 3999 * HOUR - pts[0][0]
    assert oldest <= H.MAX_AGE_S, oldest


@case("odds survive the round trip to a tenth of a point")
def _():
    for odds in (0.0, 0.001, 0.163, 0.6634, 0.999, 1.0):
        pts = H.append([], NOW, odds, 0)
        back = pts[0][1] / 1000.0
        assert abs(back - odds) <= 0.0005, (odds, back)


@case("the bootstrap seed is a well-formed history with momentum on every point")
def _():
    # transcribed by hand from build logs, so a typo is entirely possible and would
    # otherwise show up as a silently missing delta rather than an error
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fd", os.path.join(os.path.dirname(HERE), "src", "fetch_data.py"))
    fd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fd)

    pts = H.parse(fd.HISTORY_SEED)
    assert len(pts) == fd.HISTORY_SEED.count(",") + 1, pts
    assert H.encode(pts) == fd.HISTORY_SEED, H.encode(pts)
    for t, odds, mom in pts:
        # a point with no momentum would silently kill the momentum delta whenever
        # lookback happened to land on it
        assert mom is not None, (t, odds)
        assert 0 <= odds <= 1000, (t, odds)
        assert 1_700_000_000 < t < 2_000_000_000, t
    # spaced far enough apart to survive append()'s collapsing, and in order
    for (a, _, _), (b, _, _) in zip(pts, pts[1:]):
        assert b - a >= H.MIN_GAP_S, (a, b)


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
        print(f"HISTORY TEST FAILED ({len(fails)} of {len(CASES)})")
        return 1
    print(f"HISTORY TEST PASSED — all {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
