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
import datetime
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


# ---------------------------------------------------------------- drawing it
MIN_POINTS = 4
MIN_SPAN_S = 18 * 3600


def sparkline(points, C, w=660, h=150):
    """The odds over time, as an SVG, plus a sentence about what it shows.

    Returns ("", "") when the history is too short or too narrow to mean anything — a
    brand-new page has one reading, and two points hours apart is not a trend. Drawing
    something there would be inventing a story out of a single build.
    """
    pts = [(t, o / 1000.0) for t, o, _m in points]
    if len(pts) < MIN_POINTS or (pts[-1][0] - pts[0][0]) < MIN_SPAN_S:
        return "", ""

    l, r, top, bot = 34, 12, 14, 22
    t0, t1 = pts[0][0], pts[-1][0]
    span = (t1 - t0) or 1
    x = lambda t: l + (t - t0) / span * (w - l - r)
    y = lambda v: top + (1 - v) * (h - top - bot)

    line = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in pts)
    area = f"{x(t0):.1f},{y(0):.1f} " + line + f" {x(t1):.1f},{y(0):.1f}"

    grid = ""
    for g in (0, .25, .5, .75, 1.0):
        gy = y(g)
        grid += (f'<line x1="{l}" x2="{w-r}" y1="{gy:.1f}" y2="{gy:.1f}" '
                 f'stroke="{C["grid"]}" stroke-width="1"/>'
                 f'<text x="{l-7}" y="{gy+3.5:.1f}" text-anchor="end" font-size="9" '
                 f'fill="{C["mute"]}" style="font-variant-numeric:tabular-nums">'
                 f'{int(g*100)}%</text>')

    days, seen = "", set()
    for t, _v in pts:
        d = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date()
        if d in seen or d.day % 3:
            continue
        seen.add(d)
        days += (f'<text x="{x(t):.1f}" y="{h-6}" text-anchor="middle" font-size="9" '
                 f'fill="{C["mute"]}">{d.strftime("%b %-d")}</text>')

    hi = max(pts, key=lambda p: p[1])
    lo = min(pts, key=lambda p: p[1])
    marks = ""
    for pt, lab, dy in ((hi, "high", -9), (lo, "low", 15)):
        marks += (f'<circle cx="{x(pt[0]):.1f}" cy="{y(pt[1]):.1f}" r="3" '
                  f'fill="{C["mute"]}"/>'
                  f'<text x="{x(pt[0]):.1f}" y="{y(pt[1])+dy:.1f}" text-anchor="middle" '
                  f'font-size="9.5" font-weight="700" fill="{C["ink2"]}" stroke="#fff" '
                  f'stroke-width="3" paint-order="stroke">{pt[1]*100:.0f}% {lab}</text>')
    last = pts[-1]
    marks += (f'<circle cx="{x(last[0]):.1f}" cy="{y(last[1]):.1f}" r="4.5" '
              f'fill="{C["red"]}" stroke="#fff" stroke-width="2"/>')

    days_span = span / 86400
    svg = (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
           f'aria-label="Playoff odds over the last {days_span:.0f} days">'
           f'{grid}<polygon points="{area}" fill="{C["blue"]}" opacity="0.12"/>'
           f'<polyline points="{line}" fill="none" stroke="{C["blue"]}" stroke-width="2" '
           f'stroke-linejoin="round" stroke-linecap="round"/>{marks}{days}</svg>')
    note = (f"{len(pts)} rebuilds over {days_span:.0f} days, a "
            f"<b>{(hi[1]-lo[1])*100:.0f}-point</b> range between the high and the low. "
            f"Every point is a published build; the page carries its own history in a meta "
            f"tag, so this needs no database and no request.")
    return svg, note
