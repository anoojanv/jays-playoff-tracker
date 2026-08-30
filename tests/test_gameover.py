"""
A game in "Game Over" state must not break the 162-game reconciliation.

This is the failure that took the nightly build red on 2026-08-30. MLB's schedule feed
moves a finished game through TWO terminal states: "O" (Game Over — the game is
complete) and only later "F" (Final — the official scorer has signed off). The standings
endpoint counts the game as soon as it is over, so between those two states the two
feeds disagree by exactly one game per club.

drop_phantoms() exists to resolve that disagreement, but it will only drop a game dated
on or before as_of, and as_of was derived from "F" games alone. So a game that was over
but not yet final sat one day in the future as far as as_of was concerned, drop_phantoms
refused to touch it, both clubs reconciled to 163, and the build died with an error whose
suggested fix (add it to IGNORE_GAMES) would have needed a human at 4pm on a Sunday and
been wrong again an hour later.

Both directions of the race are tested, because the tempting fix — filtering "O" out of
the remaining-games list the way "F" is — breaks the other one:

  * standings HAVE counted the game -> the club is at 163, so the game must be dropped
  * standings have NOT counted it yet -> the club is at 162, so it must be left alone

Run:  python tests/test_gameover.py
"""
import json, os, sys, shutil, tempfile, importlib.util, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")

spec = importlib.util.spec_from_file_location("fd", os.path.join(SRC, "fetch_data.py"))
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)

_fixture = os.path.join(HERE, "fixture_data.json")
if not os.path.exists(_fixture):
    sys.exit(f"FATAL: fixture missing: {_fixture}\n"
             "  Regenerate it with: python tests/make_fixture.py")
BASE = json.load(open(_fixture))
AL, NL, GAMES = BASE["AL"], BASE["NL"], [tuple(g) for g in BASE["GAMES"]]

FULL = {v: k for k, v in fd.SHORT.items() if k != "Oakland Athletics"}   # short -> full

# The game left sitting in "Game Over": the first day of the fixture's schedule, and --
# not that the code cares -- the same matchup that actually broke production.
OVER_DATE = min(g[0] for g in GAMES)
OVER_GAME = next(g for g in sorted(GAMES)
                 if g[0] == OVER_DATE and g[1] in AL and g[2] in AL)

# A day of genuine finals before it, so as_of has something to fall back to and the
# "O" date is strictly later than any "F" date -- which is what made the bug possible.
PRIOR = "2026-08-14"
FINALS = [(PRIOR, FULL["Yankees"], FULL["Blue Jays"])]


def standings_payload(league, counted):
    """counted=True means the standings already include the Game Over game."""
    src = AL if league == "103" else NL
    recs = []
    for name, (w, l, rs, ra) in src.items():
        gp = w + l
        if counted and league == "103" and name in (OVER_GAME[1], OVER_GAME[2]):
            gp += 1                      # the game is over and the standings know it
            w += 1 if name == OVER_GAME[2] else 0
            l += 1 if name == OVER_GAME[1] else 0
        recs.append({
            "team": {"id": 0, "name": name, "link": "/api/v1/teams/0"},
            "gamesPlayed": gp, "wins": w, "losses": l,
            "runsScored": rs, "runsAllowed": ra, "runDifferential": rs - ra,
            "streak": {"streakCode": "W1"},
        })
    return {"records": [{"teamRecords": recs}]}


def schedule_payload(team_id, start):
    me = fd.AL_IDS[int(team_id)]
    by_date = {}
    for date, away, home in GAMES:
        if me not in (away, home) or date < start:
            continue
        over = (date, away, home) == OVER_GAME
        by_date.setdefault(date, []).append({
            "status": ({"codedGameState": "O", "detailedState": "Game Over"} if over
                       else {"codedGameState": "S", "detailedState": "Scheduled"}),
            "teams": {"away": {"team": {"name": FULL[away]}},
                      "home": {"team": {"name": FULL[home]}}},
        })
    for date, away, home in FINALS:
        if me not in (fd.canon(away), fd.canon(home)) or date < start:
            continue
        by_date.setdefault(date, []).append({
            "status": {"codedGameState": "F", "detailedState": "Final"},
            "teams": {"away": {"team": {"name": away}}, "home": {"team": {"name": home}}},
        })
    return {"dates": [{"date": d, "games": g} for d, g in sorted(by_date.items())]}


def run(counted):
    """Drive the real fetch_data.main() over a stubbed feed; return its data.json."""
    def fake_get(url, tries=4):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "/standings" in url:
            return standings_payload(q["leagueId"][0], counted)
        if "/schedule" in url:
            return schedule_payload(q["teamId"][0], q["startDate"][0])
        raise AssertionError(f"unexpected URL: {url}")

    fd.get = fake_get
    fd._try_get = lambda url, timeout=20: None      # injuries + recent form: best-effort
    fd.bref_odds = lambda: None
    fd.published_history = lambda: ""               # never reach for the live page
    os.environ["AS_OF_OVERRIDE"] = OVER_DATE

    tmp = tempfile.mkdtemp(prefix="jays-gameover-")
    fd.OUT = os.path.join(tmp, "data.json")
    try:
        fd.main()
        return json.load(open(fd.OUT))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def reconcile(got):
    """Every AL club's played + remaining, so the caller can assert on 162."""
    rem = {t: 0 for t in got["AL"]}
    for _, a, h in got["GAMES"]:
        if a in rem: rem[a] += 1
        if h in rem: rem[h] += 1
    return {t: v[0] + v[1] + rem[t] for t, v in got["AL"].items()}


def main():
    fails = []
    over_list = list(OVER_GAME)

    # ---- the standings have counted it: the stale fixture must be dropped ----
    print(f"--- Game Over on {OVER_DATE}: {OVER_GAME[1]} at {OVER_GAME[2]}")
    print("--- case 1: the standings already count it")
    try:
        got = run(counted=True)
    except SystemExit as e:
        got = None
        fails.append(f"build died instead of dropping the phantom: {e}")
    if got:
        bad = {t: n for t, n in reconcile(got).items() if n != 162}
        if bad:
            fails.append(f"clubs did not reconcile to 162: {bad}")
        if over_list in got["GAMES"]:
            fails.append("the Game Over game is still listed as remaining")
        if over_list not in got["REMOVED"]:
            fails.append("the dropped game was not disclosed in REMOVED")
        if got["as_of"] != OVER_DATE:
            fails.append(f"as_of should advance to the Game Over date {OVER_DATE}, "
                         f"got {got['as_of']}")

    # ---- the standings have NOT caught up: it is still a game to play ----
    print("\n--- case 2: the standings have not counted it yet")
    try:
        got = run(counted=False)
    except SystemExit as e:
        got = None
        fails.append(f"build died on a game that is merely over: {e}")
    if got:
        bad = {t: n for t, n in reconcile(got).items() if n != 162}
        if bad:
            fails.append(f"clubs did not reconcile to 162: {bad}")
        if over_list not in got["GAMES"]:
            fails.append("a game the standings have not counted was dropped anyway — "
                         "that is the club one game short, tomorrow")
        if got["REMOVED"]:
            fails.append(f"nothing should have been dropped: {got['REMOVED']}")

    print("\n" + "=" * 62)
    if fails:
        print("GAME OVER TEST FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("GAME OVER TEST PASSED")
    print("  a game that is over and counted is dropped, and disclosed in REMOVED")
    print("  a game that is over but not yet counted is left as still to play")
    print("  all 15 AL clubs reconcile to 162 either way")
    return 0


if __name__ == "__main__":
    sys.exit(main())
