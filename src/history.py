"""
A short history of the headline numbers, carried inside the published page itself.

The page is already its own state file — check_changed.py reads the fingerprint out of
the live page to decide whether to rebuild — so this uses the same trick rather than
introducing a database. Each build reads the previous page's history, appends the
current point, and emits the result.

Why not simply compare against the last publish: the site rebuilds every time a game
finishes, up to about twenty times a day, so a "since last publish" delta would mostly
be noise from a single game. A day-over-day figure needs a point from roughly 24 hours
ago, which means keeping a little history rather than a single previous value.

Encoding is deliberately compact and regex-friendly, since it lives in a meta tag:

    t:odds:momentum,t:odds:momentum,...

  t         epoch seconds
  odds      playoff odds in tenths of a percent (663 = 66.3%)
  momentum  the momentum index, or empty when there was none to measure
"""
import re

TAG = "page-history"
MIN_GAP_S = 30 * 60          # collapse rebuilds closer together than this
MAX_AGE_S = 12 * 24 * 3600   # a fortnight is plenty for a 24-hour comparison
MAX_POINTS = 250             # hard cap, so the page cannot grow without bound


def parse(text):
    """Pull the history out of a published page (or a bare encoded string)."""
    if not text:
        return []
    m = re.search(r'<meta name="%s" content="([^"]*)"' % TAG, text)
    blob = m.group(1) if m else text
    out = []
    for chunk in blob.split(","):
        parts = chunk.strip().split(":")
        if len(parts) != 3 or not parts[0].strip():
            continue
        try:
            t = int(parts[0])
            odds = int(parts[1])
        except ValueError:
            continue
        try:
            mom = int(parts[2])
        except ValueError:
            mom = None
        out.append((t, odds, mom))
    out.sort(key=lambda p: p[0])
    return out


def encode(points):
    return ",".join(f"{t}:{o}:{'' if m is None else m}" for t, o, m in points)


def append(points, now, odds, momentum):
    """Add the current reading, collapsing rebuilds that land close together.

    Two builds minutes apart describe the same state of the world, so the newer one
    replaces the older rather than accumulating. That also makes a rebuild of unchanged
    data idempotent instead of inflating the page a little each time.
    """
    pt = (int(now), int(round(odds * 1000)), None if momentum is None else int(momentum))
    kept = [p for p in points if p[0] < pt[0]]
    if kept and pt[0] - kept[-1][0] < MIN_GAP_S:
        kept[-1] = pt
    else:
        kept.append(pt)
    return prune(kept, pt[0])


def prune(points, now):
    points = [p for p in points if now - p[0] <= MAX_AGE_S]
    return points[-MAX_POINTS:]


def lookback(points, now, hours=24, tolerance=0.5):
    """The reading closest to `hours` ago, or None if history does not reach back.

    `tolerance` is a fraction of `hours`: at the default, a 24-hour comparison accepts
    a point between 12 and 36 hours old. Without a window the page would happily label
    a three-hour-old number "since yesterday" on the day the history began.
    """
    if not points:
        return None
    target = now - hours * 3600
    lo, hi = now - hours * 3600 * (1 + tolerance), now - hours * 3600 * (1 - tolerance)
    usable = [p for p in points if lo <= p[0] <= hi]
    if not usable:
        return None
    return min(usable, key=lambda p: abs(p[0] - target))


def delta(points, now, odds, momentum, hours=24):
    """Change in odds and momentum against roughly `hours` ago.

    Returns None when there is nothing far enough back to compare against, so a new
    page shows no delta rather than a fabricated zero.
    """
    prev = lookback(points, now, hours)
    if prev is None:
        return None
    t, prev_odds, prev_mom = prev
    d_mom = None
    if momentum is not None and prev_mom is not None:
        d_mom = int(momentum) - prev_mom
    return {
        "odds": odds - prev_odds / 1000.0,
        "momentum": d_mom,
        "age_hours": (now - t) / 3600.0,
        "prev_odds": prev_odds / 1000.0,
    }
