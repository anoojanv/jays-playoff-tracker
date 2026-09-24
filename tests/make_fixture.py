"""
Regenerate tests/fixture_data.json — the frozen world the self-tests run against.

The fixture is a `build/data.json` in the exact shape fetch_data.py writes, but it is
synthetic and deterministic rather than a snapshot of a real day. That matters: a real
snapshot rots (the schedule empties, the records stop matching the standings) and cannot
be regenerated without network access, whereas this can be rebuilt from nothing at any
time and always reconciles.

It is built the way the live data is: a full 84-game schedule for all 32 clubs first,
then the first PLAYED rounds are played out with a seeded coin, and every record is
summed from those games by fetch_data.build_records itself. So every club reconciles to
84 by construction, and the fixture exercises the same code path real standings take.

  python tests/make_fixture.py        # rewrite tests/fixture_data.json
"""
import json, os, re, sys, random, datetime, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "fixture_data.json")

os.environ.setdefault("TEAM", "TOR")
os.environ.setdefault("SEASON", "20262027")
spec = importlib.util.spec_from_file_location(
    "fd", os.path.join(ROOT, "src", "fetch_data.py"))
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)

SEASON_GAMES = 84
FIRST = datetime.date(2026, 10, 7)
PLAYED = 50                   # rounds already played; each club plays once per round
SEED = 84

# abbrev: (city, name, conference, division, last season's points share)
CLUBS = {
    "BOS": ("Boston", "Bruins", "Eastern", "Atlantic", .560),
    "BUF": ("Buffalo", "Sabres", "Eastern", "Atlantic", .600),
    "DET": ("Detroit", "Red Wings", "Eastern", "Atlantic", .530),
    "FLA": ("Florida", "Panthers", "Eastern", "Atlantic", .545),
    "MTL": ("Montréal", "Canadiens", "Eastern", "Atlantic", .575),
    "OTT": ("Ottawa", "Senators", "Eastern", "Atlantic", .580),
    "TBL": ("Tampa Bay", "Lightning", "Eastern", "Atlantic", .625),
    "TOR": ("Toronto", "Maple Leafs", "Eastern", "Atlantic", .555),
    "CAR": ("Carolina", "Hurricanes", "Eastern", "Metropolitan", .640),
    "CBJ": ("Columbus", "Blue Jackets", "Eastern", "Metropolitan", .540),
    "NJD": ("New Jersey", "Devils", "Eastern", "Metropolitan", .525),
    "NYI": ("New York", "Islanders", "Eastern", "Metropolitan", .545),
    "NYR": ("New York", "Rangers", "Eastern", "Metropolitan", .500),
    "PHI": ("Philadelphia", "Flyers", "Eastern", "Metropolitan", .550),
    "PIT": ("Pittsburgh", "Penguins", "Eastern", "Metropolitan", .565),
    "WSH": ("Washington", "Capitals", "Eastern", "Metropolitan", .570),
    "CHI": ("Chicago", "Blackhawks", "Western", "Central", .430),
    "COL": ("Colorado", "Avalanche", "Western", "Central", .670),
    "DAL": ("Dallas", "Stars", "Western", "Central", .630),
    "MIN": ("Minnesota", "Wild", "Western", "Central", .600),
    "NSH": ("Nashville", "Predators", "Western", "Central", .520),
    "STL": ("St. Louis", "Blues", "Western", "Central", .510),
    "UTA": ("Utah", "Mammoth", "Western", "Central", .560),
    "WPG": ("Winnipeg", "Jets", "Western", "Central", .540),
    "ANA": ("Anaheim", "Ducks", "Western", "Pacific", .570),
    "CGY": ("Calgary", "Flames", "Western", "Pacific", .470),
    "EDM": ("Edmonton", "Oilers", "Western", "Pacific", .590),
    "LAK": ("Los Angeles", "Kings", "Western", "Pacific", .540),
    "SEA": ("Seattle", "Kraken", "Western", "Pacific", .520),
    "SJS": ("San Jose", "Sharks", "Western", "Pacific", .500),
    "VAN": ("Vancouver", "Canucks", "Western", "Pacific", .450),
    "VGK": ("Vegas", "Golden Knights", "Western", "Pacific", .600),
}
LEAGUE = {"p_ot": 0.2485, "home_win": 0.5221}


def schedule():
    """84 rounds of the circle method on 32 clubs, one round every other day.

    Every club plays exactly once per round, so every club plays exactly 84 games. Home
    ice alternates with the round, so no club is lopsided home or away.
    """
    teams = sorted(CLUBS)
    fixed, rot = teams[0], teams[1:]
    games = []
    for r in range(SEASON_GAMES):
        order = [fixed] + rot
        date = (FIRST + datetime.timedelta(days=2 * r)).isoformat()
        for i in range(len(order) // 2):
            x, y = order[i], order[len(order) - 1 - i]
            home, away = (x, y) if (r + i) % 2 == 0 else (y, x)
            games.append({"round": r, "date": date, "away": away, "home": home})
        rot = [rot[-1]] + rot[:-1]
    return games


def prior():
    """Last season's final records, from the points shares above."""
    out = {}
    for t, (_, _, _, _, share) in CLUBS.items():
        pts = round(share * 164)
        otl = 8 + (sum(map(ord, t)) % 5)
        w = (pts - otl) // 2
        l = 82 - w - otl
        gd = round((share - .55) * 300)
        out[t] = {"w": w, "l": l, "otl": otl, "gf": 250 + max(gd, 0),
                  "ga": 250 + max(-gd, 0), "gp": 82}
    return out


def play(games):
    """Play the first PLAYED rounds with a seeded coin weighted by last season."""
    rng = random.Random(SEED)
    share = {t: v[4] for t, v in CLUBS.items()}
    gid = 2026020000
    out = []
    for g in games:
        gid += 1
        rec = {"id": gid, "date": g["date"], "utc": g["date"] + "T23:00:00Z",
               "away": g["away"], "home": g["home"], "as": None, "hs": None,
               "period": None, "state": "FUT"}
        if g["round"] < PLAYED:
            a, h = share[g["away"]], share[g["home"]]
            p_home = h * (1 - a) / (h * (1 - a) + a * (1 - h)) + 0.02
            home_won = rng.random() < p_home
            ot = rng.random() < LEAGUE["p_ot"]
            win = 3 + int(rng.random() * 3) if not ot else 3
            lose = win - 1 if ot else int(rng.random() * win)
            rec.update(state="OFF", period=("OT" if rng.random() < .6 else "SO") if ot else "REG",
                       hs=win if home_won else lose, **{"as": lose if home_won else win})
        out.append(rec)
    return out


def main():
    played = play(schedule())
    teams = {t: {"name": v[1], "city": v[0], "conf": v[2], "div": v[3]}
             for t, v in sorted(CLUBS.items())}
    for t, r in fd.build_records(played, teams).items():
        teams[t].update(r)

    divisions = {}
    for t, v in sorted(CLUBS.items()):
        divisions.setdefault(v[3], []).append(t)
    conferences = {"Eastern": ["Atlantic", "Metropolitan"],
                   "Western": ["Central", "Pacific"]}

    remaining = sorted([g["date"], g["away"], g["home"]] for g in played
                       if g["state"] not in fd.FINAL_STATES)
    left = {t: 0 for t in teams}
    for _, a, h in remaining:
        left[a] += 1; left[h] += 1
    bad = {t: v for t, v in teams.items()
           if v["w"] + v["l"] + v["otl"] + left[t] != SEASON_GAMES}
    if bad:
        sys.exit(f"fixture does not reconcile to {SEASON_GAMES}: {bad}")

    as_of = max(g["date"] for g in played if g["state"] in fd.FINAL_STATES)
    times = {f'{g["date"]}|{g["away"]}|{g["home"]}': {"utc": g["utc"], "state": "FUT"}
             for g in played if "TOR" in (g["away"], g["home"]) and g["state"] == "FUT"}
    rows = [{"teamAbbrev": {"default": t}, "wins": v["w"], "losses": v["l"],
             "otLosses": v["otl"], "goalFor": v["gf"], "goalAgainst": v["ga"]}
            for t, v in teams.items()]

    data = {
        "season": "20262027", "season_games": SEASON_GAMES, "focus": "TOR",
        "tracker_id": "nhl-TOR-20262027", "preseason": False, "as_of": as_of,
        "generated": "2027-01-15T07:13:00+00:00",   # fixed: the fixture must be stable
        "TEAMS": teams, "PRIOR": prior(), "LEAGUE": LEAGUE,
        "DIVISIONS": divisions, "CONFERENCES": conferences,
        "GAMES": remaining, "TIMES": times,
        "RECENT": fd.recent_form(played, "TOR"),
        # empty: a fixture build starts its own history, so nothing to freeze
        "HISTORY": "",
        "fingerprint": fd.fingerprint(rows),
    }

    # indent=1 puts every scalar on its own line, which turns a 32-club table and a
    # 544-game schedule into thousands of lines and makes any real change unreviewable.
    # Collapse the leaf arrays and the small records onto one line each.
    txt = json.dumps(data, indent=1, ensure_ascii=False)
    txt = re.sub(r"\[\s+([^\[\]{}]+?)\s+\]",
                 lambda m: "[" + " ".join(m.group(1).split()) + "]", txt)
    txt = re.sub(r"\{\s+([^\[\]{}]+?)\s+\}",
                 lambda m: "{" + " ".join(m.group(1).split()) + "}", txt)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    tor = teams["TOR"]
    print(f"wrote {OUT}")
    print(f"  {len(remaining)} remaining games, {len(teams)} clubs, all at {SEASON_GAMES}")
    print(f"  Maple Leafs {tor['w']}-{tor['l']}-{tor['otl']} "
          f"({2 * tor['w'] + tor['otl']} pts), {left['TOR']} to play, through {as_of}")
    print(f"  fingerprint {data['fingerprint']}")


if __name__ == "__main__":
    main()
