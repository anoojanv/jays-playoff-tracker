"""
Integration test for fetch_data.py with the network mocked out.

Feeds it responses shaped exactly like the real MLB API — including the two quirks that
actually bit us: the standings endpoint returns SHORT team names ("Rays") while the
schedule endpoint returns FULL ones ("Tampa Bay Rays"), and some games are still in
progress when the nightly build runs.

Run:  python src/selftest_fetch.py
"""
import json, os, sys, shutil, tempfile, datetime, importlib.util, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location("fd", os.path.join(HERE, "fetch_data.py"))
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)

# ---- a realistic world: a frozen, committed set of records and a remaining schedule ----
# This used to read build/data.json, which is gitignored — so in a fresh clone (and in
# CI) the fixture was always absent and the whole test exited 0 without running. It now
# reads a committed fixture and treats a missing one as a failure.
_fixture = os.path.join(ROOT, "tests", "fixture_data.json")
if not os.path.exists(_fixture):
    sys.exit(f"FATAL: fixture missing: {_fixture}\n"
             "  Regenerate it with: python tests/make_fixture.py")
BASE = json.load(open(_fixture))
AL, NL, GAMES = BASE["AL"], BASE["NL"], [tuple(g) for g in BASE["GAMES"]]

# games that finished on the most recent day (these must NOT be counted as remaining,
# and they are what as_of should be derived from)
FINALS = [("2026-08-14", "New York Yankees", "Toronto Blue Jays"),
          ("2026-08-14", "Boston Red Sox", "Pittsburgh Pirates"),
          ("2026-08-14", "Chicago White Sox", "Detroit Tigers")]

FULL = {v: k for k, v in fd.SHORT.items() if k != "Oakland Athletics"}   # short -> full


def standings_payload(league):
    src = AL if league == "103" else NL
    recs = []
    for name, (w, l, rs, ra) in src.items():
        recs.append({
            "team": {"id": 0, "name": name, "link": "/api/v1/teams/0"},   # SHORT name
            "gamesPlayed": w + l, "wins": w, "losses": l,
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
        by_date.setdefault(date, []).append({
            "status": {"codedGameState": "S", "detailedState": "Scheduled"},
            "teams": {"away": {"team": {"name": FULL[away]}},
                      "home": {"team": {"name": FULL[home]}}},
        })
    for date, away, home in FINALS:                       # FULL names, already final
        if me not in (fd.canon(away), fd.canon(home)) or date < start:
            continue
        by_date.setdefault(date, []).append({
            "status": {"codedGameState": "F", "detailedState": "Final"},
            "teams": {"away": {"team": {"name": away}}, "home": {"team": {"name": home}}},
        })
    return {"dates": [{"date": d, "games": g} for d, g in sorted(by_date.items())]}


# Realistic shapes for the two optional endpoints behind the injury report. This is the
# only coverage that parsing has — the live API cannot be reached from a test — so the
# payloads mirror the real ones: status codes on the roster, free-text descriptions on
# the transactions feed, and a player who is hurt but has no placement transaction.
ROSTER = {"roster": [
    {"person": {"id": 1, "fullName": "Dalton Reyes"}, "position": {"abbreviation": "SP"},
     "status": {"code": "D15", "description": "15-Day Injured List"}},
    {"person": {"id": 2, "fullName": "Healthy Hank"}, "position": {"abbreviation": "1B"},
     "status": {"code": "A", "description": "Active"}},
    {"person": {"id": 3, "fullName": "Nate Kowalski"}, "position": {"abbreviation": "C"},
     "status": {"code": "D7", "description": "7-Day Injured List"}},
]}
TRANSACTIONS = {"transactions": [
    {"person": {"fullName": "Dalton Reyes"}, "date": "2026-08-06",
     "effectiveDate": "2026-08-06",
     "description": "Toronto Blue Jays placed SP Dalton Reyes on the 15-day injured list."},
    {"person": {"fullName": "Healthy Hank"}, "date": "2026-05-01",
     "description": "Toronto Blue Jays selected the contract of 1B Healthy Hank."},
]}


def fake_try_get(url, timeout=20):
    if "/roster" in url:
        return ROSTER
    if "/transactions" in url:
        return TRANSACTIONS
    raise AssertionError(f"unexpected optional URL: {url}")


def fake_get(url, tries=4):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if "/standings" in url:
        return standings_payload(q["leagueId"][0])
    if "/schedule" in url:
        return schedule_payload(q["teamId"][0], q["startDate"][0])
    raise AssertionError(f"unexpected URL: {url}")


def main():
    fd.get = fake_get
    fd._try_get = fake_try_get
    fd.bref_odds = lambda: None                 # don't hit Baseball-Reference in a test
    # pretend it is 02:07 UTC on Aug 15 — i.e. 10:07pm ET on Aug 14, the real cron moment
    os.environ["AS_OF_OVERRIDE"] = "2026-08-15"

    # write somewhere disposable rather than clobbering the real build/data.json and
    # restoring it afterwards, which lost the file outright if the run died mid-test
    tmp = tempfile.mkdtemp(prefix="jays-selftest-")
    fd.OUT = os.path.join(tmp, "data.json")
    try:
        fd.main()
        got = json.load(open(fd.OUT))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    fails = []
    if got["as_of"] != "2026-08-14":
        fails.append(f"as_of should be the last day games finished (2026-08-14), got {got['as_of']}")
    if len(got["GAMES"]) != len(GAMES):
        fails.append(f"expected {len(GAMES)} remaining games, got {len(got['GAMES'])}")
    for g in got["GAMES"]:
        if g[1] not in got["AL"] and g[1] not in got["NL"]:
            fails.append(f"unresolved away team name: {g[1]!r}"); break
        if g[2] not in got["AL"] and g[2] not in got["NL"]:
            fails.append(f"unresolved home team name: {g[2]!r}"); break
    rem = {}
    for _, a, h in got["GAMES"]:
        if a in got["AL"]: rem[a] = rem.get(a, 0) + 1
        if h in got["AL"]: rem[h] = rem.get(h, 0) + 1
    for t, (w, l, _, _) in got["AL"].items():
        if w + l + rem.get(t, 0) != 162:
            fails.append(f"{t}: {w+l} played + {rem.get(t,0)} remaining != 162")
    if set(got["AL"]) != set(AL):
        fails.append("AL team set changed through the round trip")
    if got["AL"]["Blue Jays"][:2] != AL["Blue Jays"][:2]:
        fails.append("Blue Jays record did not survive the round trip")

    inj = {p["name"]: p for p in got.get("INJURIES", [])}
    if "Healthy Hank" in inj:
        fails.append("an active player was reported as injured")
    if set(inj) != {"Dalton Reyes", "Nate Kowalski"}:
        fails.append(f"wrong players on the IL: {sorted(inj)}")
    elif inj["Dalton Reyes"]["eligible"] != "2026-08-21":
        fails.append("15-day IL from Aug 6 should be eligible Aug 21, got "
                     f"{inj['Dalton Reyes']['eligible']!r}")
    elif inj["Nate Kowalski"]["eligible"] is not None:
        fails.append("a player with no placement transaction must have no return date")

    print("\n" + "=" * 62)
    if fails:
        print("SELF-TEST FAILED")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("SELF-TEST PASSED")
    print(f"  as_of {got['as_of']} · {len(got['GAMES'])} remaining games · "
          f"Blue Jays {got['AL']['Blue Jays'][0]}-{got['AL']['Blue Jays'][1]}")
    print("  short-name standings and full-name schedule both resolved")
    print("  all 15 AL clubs reconcile to 162")
    print(f"  injury report: {len(got.get('INJURIES', []))} on the IL, "
          "return dates derived from the transactions feed")


if __name__ == "__main__":
    main()
