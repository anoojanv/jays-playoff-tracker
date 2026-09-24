"""
Pull everything the model needs from the NHL's public API and write build/data.json.

Standings are computed FROM the schedule rather than fetched separately. The baseball
version of this tracker read standings and schedule from two endpoints that updated at
different moments, and spent hundreds of lines reconciling them — a club could land a game
either side of the season length and the build would fail on it. Here every club's record
is summed from its own completed games, so games played plus games left equals the season
length by construction, and the only thing left to check is that the schedule itself is
whole.

The season length is read off the schedule, not assumed: the NHL moved from 82 games to 84
for 2026-27, and a constant would have been wrong the day it shipped.

Runs on a GitHub Actions runner. Standard library only, so check_changed.py can import it
without installing anything.
"""
import datetime, hashlib, json, os, re, sys, time, urllib.error, urllib.request

FOCUS = os.environ.get("TEAM", "TOR")
SEASON = os.environ.get("SEASON", "20262027")
API = "https://api-web.nhle.com/v1"
SITE_URL = os.environ.get("SITE_URL", "https://jays-playoff-tracker.netlify.app").rstrip("/")
OUT = os.path.join(os.path.dirname(__file__), "..", "build", "data.json")

# Game states, as the NHL feed spells them. A game is only counted once it is OFF or
# FINAL; one still in progress is a game still to play, exactly as the standings treat it.
FINAL_STATES = {"OFF", "FINAL"}

# What each build carries forward from the page it replaces is keyed on this, so readings
# from a different team or season — the Blue Jays page this replaced, say — are never
# drawn as if they were this one's.
TRACKER_ID = f"nhl-{FOCUS}-{SEASON}"

# If last season's standings are unreachable the model falls back to these. Both were
# measured from 2025-26: 24.8% of games went past regulation, home teams won 52.2%.
DEFAULT_LEAGUE = {"p_ot": 0.248, "home_win": 0.522}


def get(url, tries=4):
    """Fetch JSON, retrying transient failures. Fatal: the build cannot proceed without it."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "leafs-tracker/1.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception as e:                                  # transient API blips
            last = e
            time.sleep(2 * (i + 1))
    raise SystemExit(f"FATAL: could not fetch {url}\n  {last}")


def _try_get(url, timeout=20):
    """Single-attempt fetch that never raises. get() exits the build; this must not."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "leafs-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  note: optional fetch failed ({url.split('?')[0]}): {e}")
        return None


# ---------------------------------------------------------------- standings
def standings_now():
    """The standings the NHL is currently serving, and which season they belong to.

    Between seasons this returns LAST season's final table, not an empty one — which is
    why it is used here for alignment and change detection only, never for records.
    """
    rows = get(f"{API}/standings/now").get("standings", [])
    season = str(rows[0].get("seasonId")) if rows else ""
    return season, rows


def standings_on(date):
    return get(f"{API}/standings/{date}").get("standings", [])


def fingerprint(rows):
    """Stable hash of every club's record, plus which tracker this is.

    check_changed.py compares this against the one embedded in the live page. The tracker
    id is folded in so that a page for a different sport, team or season can never be
    mistaken for this one even by chance.
    """
    parts = [TRACKER_ID]
    for t in sorted(rows, key=lambda r: r["teamAbbrev"]["default"]):
        parts.append(f'{t["teamAbbrev"]["default"]}:{t["wins"]}-{t["losses"]}-'
                     f'{t["otLosses"]}-{t["goalFor"]}-{t["goalAgainst"]}')
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def previous_season(season):
    """20262027 -> 20252026."""
    a = int(str(season)[:4])
    return f"{a - 1}{a}"


def season_end(season):
    """The last day of a season's standings, from the league's own calendar."""
    for s in get(f"{API}/standings-season").get("seasons", []):
        if str(s.get("id")) == str(season):
            return s.get("standingsEnd")
    return None


def alignment(rows):
    """Clubs, conferences and divisions, from whichever standings the league is serving."""
    teams, divisions, conferences = {}, {}, {}
    for t in rows:
        ab = t["teamAbbrev"]["default"]
        conf, div = t["conferenceName"], t["divisionName"]
        teams[ab] = {
            "name": (t.get("teamCommonName") or {}).get("default", ab),
            "city": (t.get("placeName") or {}).get("default", ""),
            "conf": conf, "div": div,
        }
        divisions.setdefault(div, []).append(ab)
        conferences.setdefault(conf, [])
        if div not in conferences[conf]:
            conferences[conf].append(div)
    for d in divisions:
        divisions[d].sort()
    for c in conferences:
        conferences[c].sort()
    return teams, divisions, conferences


def prior_records(rows):
    """Last season's final record for each club — the model's starting point before any
    game this season has been played, and a fading weight after."""
    out = {}
    for t in rows:
        out[t["teamAbbrev"]["default"]] = {
            "w": t["wins"], "l": t["losses"], "otl": t["otLosses"],
            "gf": t["goalFor"], "ga": t["goalAgainst"], "gp": t["gamesPlayed"],
        }
    return out


def league_rates(rows):
    """How often games go past regulation and how often the home side wins, measured.

    Every game that goes past regulation produces exactly one overtime loss, so the share
    of games that did is total OT losses over total games.
    """
    if not rows:
        return dict(DEFAULT_LEAGUE)
    gp = sum(t["gamesPlayed"] for t in rows)
    hg = sum(t.get("homeGamesPlayed", 0) for t in rows)
    if not gp or not hg:
        return dict(DEFAULT_LEAGUE)
    return {
        "p_ot": round(sum(t["otLosses"] for t in rows) / (gp / 2), 4),
        "home_win": round(sum(t.get("homeWins", 0) for t in rows) / hg, 4),
    }


# ---------------------------------------------------------------- schedule
def club_schedule(team, season):
    """One club's regular season, every game, finished or not."""
    games = get(f"{API}/club-schedule-season/{team}/{season}").get("games", [])
    return [g for g in games if g.get("gameType") == 2]


def parse_game(g):
    away, home = g["awayTeam"], g["homeTeam"]
    return {
        "id": g["id"], "date": g["gameDate"], "utc": g.get("startTimeUTC"),
        "state": g.get("gameState"),
        "away": away["abbrev"], "home": home["abbrev"],
        "as": away.get("score"), "hs": home.get("score"),
        "period": (g.get("gameOutcome") or {}).get("lastPeriodType"),
    }


def build_records(games, teams):
    """Sum every club's record from its completed games.

    W includes overtime and shootout wins. OTL is a loss past regulation, worth a point.
    RW — regulation wins — is the NHL's first tiebreaker after points, so it is kept.
    """
    rec = {t: {"w": 0, "l": 0, "otl": 0, "gf": 0, "ga": 0, "rw": 0} for t in teams}
    for g in games:
        if g["state"] not in FINAL_STATES or g["as"] is None or g["hs"] is None:
            continue
        a, h = g["away"], g["home"]
        if a not in rec or h not in rec:
            continue
        home_won = g["hs"] > g["as"]
        winner, loser = (h, a) if home_won else (a, h)
        past_reg = g["period"] in ("OT", "SO")
        rec[winner]["w"] += 1
        rec[loser]["otl" if past_reg else "l"] += 1
        if not past_reg:
            rec[winner]["rw"] += 1
        rec[h]["gf"] += g["hs"]; rec[h]["ga"] += g["as"]
        rec[a]["gf"] += g["as"]; rec[a]["ga"] += g["hs"]
    return rec


def recent_form(games, team, limit=25):
    """The focus club's completed games, oldest first, for the momentum rating."""
    out = []
    for g in sorted(games, key=lambda x: (x["date"], x["id"])):
        if g["state"] not in FINAL_STATES or team not in (g["away"], g["home"]):
            continue
        at_home = g["home"] == team
        mine, theirs = (g["hs"], g["as"]) if at_home else (g["as"], g["hs"])
        if mine is None or theirs is None:
            continue
        out.append({"date": g["date"], "opp": g["away"] if at_home else g["home"],
                    "home": at_home, "won": mine > theirs,
                    "ot": g["period"] in ("OT", "SO")})
    return out[-limit:]


def published_history():
    """The history carried by the page currently live — but only if it is THIS tracker's.

    The page is its own state file: each build reads the live page's readings and appends
    today's. When this tracker replaced a Blue Jays one on the same address, the live page
    was carrying weeks of Jays playoff odds, and without the tracker-id check the first
    Leafs build would have drawn them as the Leafs' history. A page with no tracker-id, or
    a different one, contributes nothing and the history starts fresh.
    """
    try:
        req = urllib.request.Request(
            SITE_URL + "/?h=" + str(int(time.time())),
            headers={"User-Agent": "leafs-tracker/1.0", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=20) as r:
            page = r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"  note: could not read the live page for history ({e})")
        return ""
    tid = re.search(r'<meta name="tracker-id" content="([^"]*)"', page)
    if not tid or tid.group(1) != TRACKER_ID:
        print(f"  history: live page is a different tracker "
              f"({tid.group(1) if tid else 'none'}) — starting fresh")
        return ""
    m = re.search(r'<meta name="page-history" content="([^"]*)"', page)
    if not m or not m.group(1):
        return ""
    print(f"  history: {m.group(1).count(',') + 1} previous readings carried forward")
    return m.group(1)


def main():
    today = datetime.date.fromisoformat(os.environ["AS_OF_OVERRIDE"]) \
        if os.environ.get("AS_OF_OVERRIDE") \
        else datetime.datetime.now(datetime.timezone.utc).date()
    print(f"fetching NHL {SEASON} for {FOCUS} (UTC today {today})")

    now_season, now_rows = standings_now()
    teams, divisions, conferences = alignment(now_rows)
    if FOCUS not in teams:
        raise SystemExit(f"FATAL: {FOCUS} is not in the league's standings")
    print(f"  alignment: {len(teams)} clubs, {len(divisions)} divisions "
          f"(from {now_season} standings)")

    # last season, as the prior
    prior_id = previous_season(SEASON)
    prior_end = season_end(prior_id)
    prior_rows = standings_on(prior_end) if prior_end else []
    if prior_rows and str(prior_rows[0].get("seasonId")) != prior_id:
        prior_rows = []
    prior = prior_records(prior_rows)
    league = league_rates(prior_rows)
    print(f"  prior: {prior_id} final standings, {len(prior)} clubs · "
          f"{league['p_ot']*100:.1f}% of games past regulation, "
          f"home side won {league['home_win']*100:.1f}%")

    # every club's schedule; each game appears in both clubs' feeds, deduped by id
    by_id = {}
    per_team = {}
    for ab in sorted(teams):
        sched = club_schedule(ab, SEASON)
        per_team[ab] = len(sched)
        for g in sched:
            by_id[g["id"]] = parse_game(g)
    games = list(by_id.values())

    lengths = set(per_team.values())
    if len(lengths) != 1:
        raise SystemExit(f"FATAL: clubs have different season lengths: {per_team}")
    season_games = lengths.pop()
    if len(games) != season_games * len(teams) // 2:
        raise SystemExit(f"FATAL: {len(games)} unique games, expected "
                         f"{season_games * len(teams) // 2}")

    records = build_records(games, teams)
    for ab, info in teams.items():
        info.update(records[ab])

    remaining = sorted([g["date"], g["away"], g["home"]] for g in games
                       if g["state"] not in FINAL_STATES)
    left = {t: 0 for t in teams}
    for _, a, h in remaining:
        left[a] += 1; left[h] += 1
    bad = {t: (teams[t]["w"] + teams[t]["l"] + teams[t]["otl"], left[t])
           for t in teams
           if teams[t]["w"] + teams[t]["l"] + teams[t]["otl"] + left[t] != season_games}
    if bad:
        raise SystemExit(f"FATAL: schedule does not reconcile to {season_games}: {bad}")
    print(f"  reconciled: all {len(teams)} clubs at {season_games} games · "
          f"{len(remaining)} left to play")

    finals = [g["date"] for g in games if g["state"] in FINAL_STATES]
    preseason = not finals
    as_of = max(finals) if finals else (today - datetime.timedelta(days=1)).isoformat()

    # first pitch — first puck drop — and state for the focus club's games still to come
    times = {}
    for g in games:
        if FOCUS in (g["away"], g["home"]) and g["state"] not in FINAL_STATES:
            times[f'{g["date"]}|{g["away"]}|{g["home"]}'] = {"utc": g["utc"],
                                                             "state": g["state"]}

    data = {
        "season": SEASON, "season_games": season_games, "focus": FOCUS,
        "tracker_id": TRACKER_ID, "preseason": preseason, "as_of": as_of,
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"),
        "TEAMS": teams, "PRIOR": prior, "LEAGUE": league,
        "DIVISIONS": divisions, "CONFERENCES": conferences,
        "GAMES": remaining, "TIMES": times,
        "RECENT": recent_form(games, FOCUS),
        "HISTORY": published_history(),
        "fingerprint": fingerprint(now_rows),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
    t = teams[FOCUS]
    print(f"  {t['city']} {t['name']} {t['w']}-{t['l']}-{t['otl']}, "
          f"{2 * t['w'] + t['otl']} pts, as of {as_of}"
          + ("  (preseason — no games played yet)" if preseason else ""))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
