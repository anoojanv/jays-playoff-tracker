"""
Integration test for fetch_data.py with the network mocked out.

Every NHL endpoint the build touches is answered from the same synthetic season the
fixture is made from, in the shapes the real API uses: standings rows keyed by
teamAbbrev, one club-schedule feed per club (so every game arrives twice and must be
deduped by id), OFF for a finished game, LIVE and CRIT for one still being played.

Run:  python src/selftest_fetch.py
"""
import io, json, os, sys, tempfile, datetime, importlib.util, contextlib, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.environ["TEAM"] = "TOR"
os.environ["SEASON"] = "20262027"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fd = _load("fd", os.path.join(HERE, "fetch_data.py"))
mf = _load("mf", os.path.join(ROOT, "tests", "make_fixture.py"))
fd.time.sleep = lambda s: None                      # get() retries must not stall a test


# ---------------------------------------------------------------- the fake league
def world(played=True):
    games = mf.play(mf.schedule()) if played else [
        dict(g, id=2026020001 + i, utc=g["date"] + "T23:00:00Z", state="FUT",
             **{"as": None, "hs": None, "period": None})
        for i, g in enumerate(mf.schedule())]
    return games


def standings_rows(records, season="20262027", home=True):
    rows = []
    for t, (city, name, conf, div, _) in sorted(mf.CLUBS.items()):
        r = records.get(t, {"w": 0, "l": 0, "otl": 0, "gf": 0, "ga": 0})
        gp = r["w"] + r["l"] + r["otl"]
        row = {"teamAbbrev": {"default": t}, "teamCommonName": {"default": name},
               "placeName": {"default": city}, "conferenceName": conf,
               "divisionName": div, "seasonId": int(season), "gamesPlayed": gp,
               "wins": r["w"], "losses": r["l"], "otLosses": r["otl"],
               "goalFor": r["gf"], "goalAgainst": r["ga"]}
        if home:
            row.update(homeGamesPlayed=gp // 2, homeWins=round(gp // 2 * .53))
        rows.append(row)
    return rows


def feed(games):
    """games (the make_fixture shape) -> one NHL club-schedule-season payload per club."""
    out = {t: [] for t in mf.CLUBS}
    for g in games:
        entry = {
            "id": g["id"], "gameType": 2, "gameDate": g["date"],
            "startTimeUTC": g["utc"], "gameState": g["state"],
            "awayTeam": {"abbrev": g["away"], "score": g["as"]},
            "homeTeam": {"abbrev": g["home"], "score": g["hs"]},
            "gameOutcome": {"lastPeriodType": g["period"]} if g["period"] else None,
        }
        out[g["away"]].append(entry)
        out[g["home"]].append(entry)
    # a preseason game in the feed, which the build must ignore
    out["TOR"].insert(0, dict(out["TOR"][0], id=2026010001, gameType=1,
                              gameDate="2026-09-20", gameState="OFF"))
    return out


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def make_urlopen(games, prior_rows, live_page=None, now_rows=None, fail=()):
    feeds = feed(games)
    now_rows = now_rows if now_rows is not None else standings_rows(
        fd.build_records(games, {t: {} for t in mf.CLUBS}))

    def urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        for f in fail:
            if f in url:
                raise OSError(f"simulated outage: {f}")
        if url.startswith(fd.SITE_URL):
            if live_page is None:
                raise OSError("site unreachable")
            return _Resp(live_page.encode())
        path = url.replace(fd.API, "")
        if path == "/standings/now":
            body = {"standings": now_rows}
        elif path == "/standings-season":
            body = {"seasons": [{"id": 20252026, "standingsEnd": "2026-04-16"},
                                {"id": 20262027, "standingsEnd": "2027-04-15"}]}
        elif path.startswith("/standings/"):
            body = {"standings": prior_rows}
        elif path.startswith("/club-schedule-season/"):
            team = path.split("/")[2]
            body = {"games": feeds[team]}
        else:
            raise AssertionError(f"unexpected URL {url}")
        return _Resp(json.dumps(body).encode())
    return urlopen


PRIOR_ROWS = standings_rows({t: dict(v) for t, v in mf.prior().items()}, season="20252026")


def run(urlopen, today="2027-01-15"):
    """Drive fetch_data.main() against the fake league; return the data it wrote."""
    out = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    fd.OUT = out
    os.environ["AS_OF_OVERRIDE"] = today
    real = urllib.request.urlopen
    urllib.request.urlopen = urlopen
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fd.main()
    finally:
        urllib.request.urlopen = real
    data = json.load(open(out))
    os.remove(out)
    return data


# ---------------------------------------------------------------- cases
CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("mid-season: records summed from the schedule match the fixture exactly")
def _():
    fx = json.load(open(os.path.join(ROOT, "tests", "fixture_data.json")))
    d = run(make_urlopen(world(), PRIOR_ROWS))
    for t, v in fx["TEAMS"].items():
        for k in ("w", "l", "otl", "gf", "ga", "rw"):
            assert d["TEAMS"][t][k] == v[k], (t, k, d["TEAMS"][t][k], v[k])
    assert d["GAMES"] == fx["GAMES"], "remaining schedule differs from the fixture"
    assert d["RECENT"] == fx["RECENT"]
    assert d["season_games"] == 84 and not d["preseason"]
    assert d["as_of"] == fx["as_of"]


@case("every game arrives in both clubs' feeds and is counted once")
def _():
    d = run(make_urlopen(world(), PRIOR_ROWS))
    total = sum(v["w"] + v["l"] + v["otl"] for v in d["TEAMS"].values())
    assert total == 2 * 50 * 16, total           # 50 rounds of 16 games, two sides each
    assert len(d["GAMES"]) == 34 * 16


@case("a game still being played is a game still to play")
def _():
    games = world()
    tor_final = [g for g in games if g["state"] == "OFF" and "TOR" in (g["away"], g["home"])]
    last = tor_final[-1]
    last.update(state="LIVE")
    also = [g for g in games if g["state"] == "OFF" and "TOR" not in (g["away"], g["home"])][-1]
    also.update(state="CRIT")
    d = run(make_urlopen(games, PRIOR_ROWS))
    assert [last["date"], last["away"], last["home"]] in d["GAMES"]
    assert [also["date"], also["away"], also["home"]] in d["GAMES"]
    tor = d["TEAMS"]["TOR"]
    assert tor["w"] + tor["l"] + tor["otl"] == 49
    key = f'{last["date"]}|{last["away"]}|{last["home"]}'
    assert d["TIMES"][key]["state"] == "LIVE", "the page needs to know it is underway"


@case("overtime and shootout losses are OTL, and neither win is a regulation win")
def _():
    games = world()
    g = next(x for x in games if x["state"] == "OFF")
    before = run(make_urlopen(games, PRIOR_ROWS))["TEAMS"]
    home_won = g["hs"] > g["as"]
    winner, loser = (g["home"], g["away"]) if home_won else (g["away"], g["home"])
    was_reg = g["period"] == "REG"
    g["period"] = "SO"
    after = run(make_urlopen(games, PRIOR_ROWS))["TEAMS"]
    if was_reg:
        assert after[loser]["otl"] == before[loser]["otl"] + 1
        assert after[loser]["l"] == before[loser]["l"] - 1
        assert after[winner]["rw"] == before[winner]["rw"] - 1
    assert after[winner]["w"] == before[winner]["w"]


@case("preseason: nothing played, every club level, the whole schedule ahead")
def _():
    d = run(make_urlopen(world(played=False), PRIOR_ROWS,
                         now_rows=PRIOR_ROWS), today="2026-09-24")
    assert d["preseason"] is True
    assert d["as_of"] == "2026-09-23"
    assert all(v["w"] == v["l"] == v["otl"] == 0 for v in d["TEAMS"].values())
    assert len(d["GAMES"]) == 84 * 16
    assert len(d["TIMES"]) == 84
    assert d["PRIOR"]["TBL"]["gp"] == 82


@case("last season's standings become the prior, and set the overtime and home rates")
def _():
    d = run(make_urlopen(world(), PRIOR_ROWS))
    assert set(d["PRIOR"]) == set(mf.CLUBS)
    otl = sum(r["otLosses"] for r in PRIOR_ROWS)
    gp = sum(r["gamesPlayed"] for r in PRIOR_ROWS)
    assert abs(d["LEAGUE"]["p_ot"] - round(otl / (gp / 2), 4)) < 1e-9
    assert 0.5 < d["LEAGUE"]["home_win"] < 0.56


@case("standings from the wrong season are not used as the prior")
def _():
    wrong = [dict(r, seasonId=20242025) for r in PRIOR_ROWS]
    d = run(make_urlopen(world(), wrong))
    assert d["PRIOR"] == {}
    assert d["LEAGUE"] == fd.DEFAULT_LEAGUE


@case("a schedule that does not add up stops the build")
def _():
    games = [g for g in world() if not (g["away"] == "TOR" and g["state"] == "FUT")][:-1]
    try:
        run(make_urlopen(games, PRIOR_ROWS))
    except SystemExit as e:
        assert "season length" in str(e) or "unique games" in str(e) or "reconcile" in str(e), e
    else:
        raise AssertionError("an incomplete schedule was accepted")


@case("history carries forward from this tracker's page, never from another one")
def _():
    mine = ('<meta name="tracker-id" content="nhl-TOR-20262027">'
            '<meta name="page-history" content="abc,def">')
    jays = ('<meta name="tracker-id" content="mlb-TOR-2026">'
            '<meta name="page-history" content="xyz">')
    none = '<meta name="page-history" content="xyz">'
    assert run(make_urlopen(world(), PRIOR_ROWS, live_page=mine))["HISTORY"] == "abc,def"
    assert run(make_urlopen(world(), PRIOR_ROWS, live_page=jays))["HISTORY"] == ""
    assert run(make_urlopen(world(), PRIOR_ROWS, live_page=none))["HISTORY"] == ""
    assert run(make_urlopen(world(), PRIOR_ROWS, live_page=None))["HISTORY"] == ""


@case("the fingerprint moves when any club's record does, and names the tracker")
def _():
    rows = standings_rows(fd.build_records(world(), {t: {} for t in mf.CLUBS}))
    a = fd.fingerprint(rows)
    rows[5] = dict(rows[5], wins=rows[5]["wins"] + 1)
    assert fd.fingerprint(rows) != a
    real = fd.TRACKER_ID
    try:
        fd.TRACKER_ID = "nhl-MTL-20262027"
        b = fd.fingerprint(rows)
    finally:
        fd.TRACKER_ID = real
    assert b != fd.fingerprint(rows), "a different tracker must never share a fingerprint"


@case("the NHL API being down is fatal, not a silently empty page")
def _():
    try:
        run(make_urlopen(world(), PRIOR_ROWS, fail=("/club-schedule-season/",)))
    except SystemExit as e:
        assert "could not fetch" in str(e)
    else:
        raise AssertionError("an unreachable API produced a build")


def main():
    fails = 0
    for name, fn in CASES:
        try:
            fn()
            print(f"  ok    {name}")
        except Exception as e:                     # noqa: BLE001 — report every case
            fails += 1
            print(f"  FAIL  {name}\n        {type(e).__name__}: {e}")
    print("\n" + "=" * 58)
    if fails:
        print(f"FETCH SELFTEST FAILED — {fails} of {len(CASES)} cases")
        return 1
    print(f"FETCH SELFTEST PASSED — all {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
