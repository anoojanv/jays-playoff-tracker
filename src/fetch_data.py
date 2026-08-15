"""
Pull everything the model needs straight from the MLB Stats API and write build/data.json.

Runs on a GitHub Actions runner, which has ordinary outbound internet — so unlike the
Cowork sandbox this talks to statsapi.mlb.com directly.

Fails loudly. If the schedule does not reconcile to 162 games for every AL club, the
build stops rather than publishing a quietly wrong page.
"""
import json, os, sys, datetime, urllib.request, urllib.error, time

SEASON = int(os.environ.get("SEASON", "2026"))
SEASON_END = os.environ.get("SEASON_END", f"{SEASON}-10-04")
OUT = os.path.join(os.path.dirname(__file__), "..", "build", "data.json")

AL_IDS = {141: "Blue Jays", 147: "Yankees", 111: "Red Sox", 139: "Rays", 110: "Orioles",
          145: "White Sox", 116: "Tigers", 142: "Twins", 114: "Guardians", 118: "Royals",
          117: "Astros", 140: "Rangers", 136: "Mariners", 133: "Athletics", 108: "Angels"}

SHORT = {
    "Toronto Blue Jays": "Blue Jays", "New York Yankees": "Yankees", "Boston Red Sox": "Red Sox",
    "Tampa Bay Rays": "Rays", "Baltimore Orioles": "Orioles", "Chicago White Sox": "White Sox",
    "Minnesota Twins": "Twins", "Detroit Tigers": "Tigers", "Cleveland Guardians": "Guardians",
    "Kansas City Royals": "Royals", "Houston Astros": "Astros", "Texas Rangers": "Rangers",
    "Seattle Mariners": "Mariners", "Athletics": "Athletics", "Oakland Athletics": "Athletics",
    "Los Angeles Angels": "Angels", "Atlanta Braves": "Braves",
    "Philadelphia Phillies": "Phillies", "Miami Marlins": "Marlins",
    "Washington Nationals": "Nationals", "New York Mets": "Mets",
    "Milwaukee Brewers": "Brewers", "Chicago Cubs": "Cubs", "St. Louis Cardinals": "Cardinals",
    "Cincinnati Reds": "Reds", "Pittsburgh Pirates": "Pirates",
    "Los Angeles Dodgers": "Dodgers", "San Diego Padres": "Padres",
    "Arizona Diamondbacks": "D-backs", "San Francisco Giants": "Giants",
    "Colorado Rockies": "Rockies",
}

DIVISIONS = {
    "AL East":    ["Rays", "Yankees", "Red Sox", "Blue Jays", "Orioles"],
    "AL Central": ["White Sox", "Tigers", "Twins", "Guardians", "Royals"],
    "AL West":    ["Astros", "Rangers", "Mariners", "Athletics", "Angels"],
}

# Escape hatch for a postponement MLB has not yet put back on the calendar, which
# leaves two clubs a game short and fails the 162 check below. Add the makeup here as
# ("YYYY-MM-DD", "Away", "Home") and remove it once the real game appears in the feed.
# Anything listed here is disclosed in the page's methodology footnote.
SYNTHETIC_GAMES = [
    # ("2026-09-23", "Angels", "Rangers"),
]


def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "jays-tracker/1.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception as e:                                  # transient API blips
            last = e
            time.sleep(2 * (i + 1))
    raise SystemExit(f"FATAL: could not fetch {url}\n  {last}")


def standings(league_id):
    url = (f"https://statsapi.mlb.com/api/v1/standings?leagueId={league_id}"
           f"&season={SEASON}&standingsTypes=regularSeason")
    out = {}
    for rec in get(url)["records"]:
        for t in rec["teamRecords"]:
            name = SHORT[t["team"]["name"]]
            out[name] = {
                "w": t["wins"], "l": t["losses"], "gp": t["gamesPlayed"],
                "rs": int(t["runsScored"]), "ra": int(t["runsAllowed"]),
                "streak": t.get("streak", {}).get("streakCode", ""),
            }
    return out


def schedule(team_id, start):
    url = (f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}"
           f"&startDate={start}&endDate={SEASON_END}")
    games = []
    for d in get(url).get("dates", []):
        for g in d.get("games", []):
            # Keep only games still to be played. F = final, C = cancelled,
            # D = postponed (the makeup shows up separately with its own date).
            # If this filter is ever wrong the 162-game check below fails the build
            # rather than letting a miscounted schedule reach the page.
            if g.get("status", {}).get("codedGameState") in ("F", "C", "D"):
                continue
            games.append((d["date"],
                          SHORT[g["teams"]["away"]["team"]["name"]],
                          SHORT[g["teams"]["home"]["team"]["name"]]))
    return games


def bref_odds():
    """Best-effort comparison number. Never fatal — the page hides the pill if absent."""
    try:
        url = f"https://www.baseball-reference.com/leagues/majors/{SEASON}-playoff-odds.shtml"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 jays-tracker"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "ignore")
        import re
        m = re.search(r"standings through (\d{4}-\d{2}-\d{2})", html)
        date = m.group(1) if m else None
        row = re.search(r'data-stat="team_ID"[^>]*>\s*<a[^>]*>TOR</a>.*?'
                        r'data-stat="playoff_odds"[^>]*>([\d.]+)', html, re.S)
        if row:
            return {"odds": float(row.group(1)), "date": date}
    except Exception as e:
        print(f"  note: Baseball-Reference comparison unavailable ({e})")
    return None


def main():
    today = os.environ.get("AS_OF_OVERRIDE") or datetime.date.today().isoformat()
    print(f"fetching {SEASON} data, schedule from {today} to {SEASON_END}")

    al = standings(103)
    nl = standings(104)
    print(f"  standings: {len(al)} AL, {len(nl)} NL teams")

    # union every AL club's remaining schedule; an AL-vs-AL game appears in both feeds
    counter = {}
    for tid in AL_IDS:
        for g in schedule(tid, today):
            counter[g] = counter.get(g, 0) + 1
    games = []
    for (date, away, home), n in counter.items():
        both_al = away in al and home in al
        for _ in range(n // 2 if both_al else n):
            games.append([date, away, home])
    for g in SYNTHETIC_GAMES:
        games.append(list(g))
        print(f"  note: added synthetic makeup game {g[1]} at {g[2]} on {g[0]}")
    games.sort()
    print(f"  schedule: {len(games)} remaining games")

    # every club must reconcile to exactly 162
    rem = {t: 0 for t in al}
    for _, a, h in games:
        if a in al: rem[a] += 1
        if h in al: rem[h] += 1
    bad = {t: al[t]["gp"] + rem[t] for t in al if al[t]["gp"] + rem[t] != 162}
    if bad:
        print("FATAL: schedule does not reconcile to 162 games:", file=sys.stderr)
        for t, n in sorted(bad.items()):
            print(f"  {t}: {al[t]['gp']} played + {rem[t]} remaining = {n}", file=sys.stderr)
        print("\nUsually a postponed game MLB has not yet rescheduled. Either re-run later,\n"
              "or add the makeup to SYNTHETIC_GAMES near the top of this file.",
              file=sys.stderr)
        raise SystemExit(1)
    print("  reconciled: all 15 AL clubs at 162 games")

    # as-of = the date of the last completed games, not today
    as_of = min((datetime.date.fromisoformat(g[0]) for g in games),
                default=datetime.date.fromisoformat(today)) - datetime.timedelta(days=1)

    data = {
        "season": SEASON, "as_of": as_of.isoformat(), "generated": datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds"),
        "AL": {k: [v["w"], v["l"], v["rs"], v["ra"]] for k, v in al.items()},
        "NL": {k: [v["w"], v["l"], v["rs"], v["ra"]] for k, v in nl.items()},
        "DIVISIONS": DIVISIONS, "GAMES": games, "BREF": bref_odds(),
        "SYNTHETIC": [list(g) for g in SYNTHETIC_GAMES],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
    j = data["AL"]["Blue Jays"]
    print(f"  Blue Jays {j[0]}-{j[1]}, run diff {j[2]-j[3]:+d}, as of {data['as_of']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
