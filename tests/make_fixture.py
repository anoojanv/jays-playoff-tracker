"""
Regenerate tests/fixture_data.json — the frozen world the self-tests run against.

The fixture is a `build/data.json` in the exact shape fetch_data.py writes, but it is
synthetic and deterministic rather than a snapshot of a real day. That matters: a real
snapshot rots (the schedule empties, the records stop matching the standings) and cannot
be regenerated without network access, whereas this can be rebuilt from nothing at any
time and always reconciles.

Construction guarantees the invariant the whole pipeline is built on: the schedule is
generated first, then each club's games-played is set to 162 minus what it has left, so
all 15 AL clubs reconcile to exactly 162 by construction.

  python tests/make_fixture.py        # rewrite tests/fixture_data.json
"""
import json, os, sys, datetime, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "fixture_data.json")

spec = importlib.util.spec_from_file_location(
    "fd", os.path.join(ROOT, "src", "fetch_data.py"))
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)

SEASON = 2026
AS_OF = "2026-08-14"          # the last day on which games finished
FIRST = datetime.date(2026, 8, 15)
SEASON_END = datetime.date(2026, 10, 4)

AL_TEAMS = [t for members in fd.DIVISIONS.values() for t in members]
NL_TEAMS = ["Braves", "Phillies", "Marlins", "Nationals", "Mets",
            "Brewers", "Cubs", "Cardinals", "Reds", "Pirates",
            "Dodgers", "Padres", "D-backs", "Giants", "Rockies"]

N_SERIES = 13                 # per club
SERIES_LEN = 3


def schedule():
    """13 three-game series per AL club, via the circle method on 16 slots.

    Slot 15 is a stand-in for "an interleague opponent", so exactly one AL club per
    round plays an NL club instead of sitting out. Every AL club therefore plays every
    round, which is what makes the per-club game count uniform.
    """
    slots = list(range(15)) + [None]           # None == the interleague slot
    dates, d = [], FIRST
    while len(dates) < N_SERIES * SERIES_LEN:
        dates.append(d)
        # an off day between series keeps the calendar realistic and lands the last
        # game on the season-end date
        if len(dates) % SERIES_LEN == 0:
            d += datetime.timedelta(days=2)
        else:
            d += datetime.timedelta(days=1)
    assert dates[-1] <= SEASON_END, f"schedule runs past the season ({dates[-1]})"

    games = []
    rot = slots[1:]
    for r in range(N_SERIES):
        order = [slots[0]] + rot
        pairs = [(order[i], order[len(order) - 1 - i]) for i in range(len(order) // 2)]
        for pi, (x, y) in enumerate(pairs):
            if x is None or y is None:
                al = fd_name(x if y is None else y)
                nl = NL_TEAMS[(r * 3 + pi) % len(NL_TEAMS)]
                # the interleague club alternates home and road by round
                home, away = (al, nl) if r % 2 == 0 else (nl, al)
            else:
                a, b = fd_name(x), fd_name(y)
                home, away = (a, b) if (r + pi) % 2 == 0 else (b, a)
            for k in range(SERIES_LEN):
                games.append([dates[r * SERIES_LEN + k].isoformat(), away, home])
        rot = [rot[-1]] + rot[:-1]             # rotate all but the fixed slot
    games.sort()
    return games


def fd_name(slot):
    return AL_TEAMS[slot]


def runs(gp, win_pct, pythag_offset):
    """Pick runs scored/allowed so Pythagenpat lands `pythag_offset` off the real W-L.

    A club with a positive offset has underperformed its run differential (the model
    likes it more than its record does) and vice versa, so the fixture exercises both
    sides of the page's "won more games than the run differential supports" logic.
    """
    p = min(0.750, max(0.250, win_pct + pythag_offset))
    rpg = 8.8
    total = rpg * gp
    x = rpg ** 0.287
    ratio = (p / (1 - p)) ** (1 / x)
    rs = total * ratio / (1 + ratio)
    return int(round(rs)), int(round(total - rs))


def records(teams, games, seed_pcts, offsets):
    """games-played is forced to 162 - (games remaining), so the fixture reconciles."""
    rem = {t: 0 for t in teams}
    for _, a, h in games:
        if a in rem: rem[a] += 1
        if h in rem: rem[h] += 1
    out = {}
    for i, t in enumerate(teams):
        gp = 162 - rem[t]
        w = int(round(gp * seed_pcts[i]))
        rs, ra = runs(gp, w / gp, offsets[i])
        out[t] = [w, gp - w, rs, ra]
    return out


def main():
    games = schedule()

    # a plausible AL spread, deliberately tight in the middle so the wild-card race is
    # live and the conditional/leverage code paths all have something to chew on
    pcts = [.618, .585, .553, .545, .512, .504, .496, .488, .480, .472,
            .463, .447, .431, .415, .390]
    # the Jays overperform their run differential, which is the case the page calls out
    offs = [-.004, +.006, -.002, -.028, +.010, -.006, +.004, +.012, -.008, +.002,
            +.006, -.004, +.008, -.002, +.004]
    al = records(AL_TEAMS, games, pcts, offs)

    # NL clubs only need a record: the model uses them for interleague opponent talent
    # and for the fingerprint, and no 162 check applies to them
    nl = {}
    for i, t in enumerate(NL_TEAMS):
        gp = 121 + (i % 4)
        w = int(round(gp * (.600 - i * .014)))
        rs, ra = runs(gp, w / gp, (-1) ** i * .006)
        nl[t] = [w, gp - w, rs, ra]

    as_dicts = lambda src: {k: {"w": v[0], "l": v[1], "rs": v[2], "ra": v[3]}
                            for k, v in src.items()}
    data = {
        "season": SEASON,
        "as_of": AS_OF,
        "generated": "2026-08-15T02:07:00+00:00",   # fixed: the fixture must be stable
        "AL": al,
        "NL": nl,
        "DIVISIONS": fd.DIVISIONS,
        "GAMES": games,
        "BREF": None,                               # never depend on a live scrape
        "SYNTHETIC": [],
        "fingerprint": fd.fingerprint(as_dicts(al), as_dicts(nl)),
    }

    rem = {t: 0 for t in al}
    for _, a, h in games:
        if a in rem: rem[a] += 1
        if h in rem: rem[h] += 1
    bad = {t: al[t][0] + al[t][1] + rem[t] for t in al
           if al[t][0] + al[t][1] + rem[t] != 162}
    if bad:
        sys.exit(f"fixture does not reconcile to 162: {bad}")

    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print(f"wrote {OUT}")
    print(f"  {len(games)} remaining games, {len(al)} AL / {len(nl)} NL clubs")
    print(f"  every AL club at 162 · Blue Jays "
          f"{al['Blue Jays'][0]}-{al['Blue Jays'][1]}, {rem['Blue Jays']} to play")
    print(f"  fingerprint {data['fingerprint']}")


if __name__ == "__main__":
    main()
