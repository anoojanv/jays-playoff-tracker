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

# The MLB API is not consistent about team names: the standings endpoint returns the
# short name ("Rays") while the schedule endpoint returns the full one ("Tampa Bay
# Rays"). canon() accepts either so neither endpoint can break the build.
CANON = set(SHORT.values())


def canon(name):
    if name in CANON:
        return name
    if name in SHORT:
        return SHORT[name]
    raise SystemExit(
        f"FATAL: unrecognised team name from the MLB API: {name!r}\n"
        "  Add it to the SHORT map in src/fetch_data.py (a club was probably renamed)."
    )


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

# The mirror of SYNTHETIC_GAMES, for a club that reconciles to 163 rather than 161: a
# game the feed still lists as scheduled even though it has been played. Add it here as
# ("YYYY-MM-DD", "Away", "Home") to drop it by hand. Anything listed is disclosed in the
# page's methodology footnote, exactly like a synthetic makeup.
IGNORE_GAMES = [
    # ("2026-08-15", "Twins", "Guardians"),
]


def fingerprint(al, nl):
    """Stable hash of every club's record. Any finished game changes it."""
    import hashlib
    parts = []
    for src in (al, nl):
        for name in sorted(src):
            v = src[name]
            w, l, rs, ra = (v["w"], v["l"], v["rs"], v["ra"]) if isinstance(v, dict) else v
            parts.append(f"{name}:{w}-{l}-{rs}-{ra}")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


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
            name = canon(t["team"]["name"])
            out[name] = {
                "w": t["wins"], "l": t["losses"], "gp": t["gamesPlayed"],
                "rs": int(t["runsScored"]), "ra": int(t["runsAllowed"]),
                "streak": t.get("streak", {}).get("streakCode", ""),
            }
    return out


def schedule(team_id, start, final_dates):
    url = (f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}"
           f"&startDate={start}&endDate={SEASON_END}")
    games = []
    for d in get(url).get("dates", []):
        for g in d.get("games", []):
            if g.get("status", {}).get("codedGameState") == "F":
                final_dates.add(d["date"])
            # Keep only games still to be played. F = final, C = cancelled,
            # D = postponed (the makeup shows up separately with its own date).
            # If this filter is ever wrong the 162-game check below fails the build
            # rather than letting a miscounted schedule reach the page.
            if g.get("status", {}).get("codedGameState") in ("F", "C", "D"):
                continue
            games.append((d["date"],
                          canon(g["teams"]["away"]["team"]["name"]),
                          canon(g["teams"]["home"]["team"]["name"])))
    return games


# Return dates MLB has not published but you have read somewhere reliable. Keyed by the
# player's full name exactly as the API spells it; anything here overrides the derived
# timeline and is marked on the page as a reported date rather than an IL minimum.
INJURY_NOTES = {
    # "Bo Bichette": "targeting a rehab assignment the week of Sep 8",
}

# How long each injured list keeps a player out, for the earliest-eligible-return date.
IL_DAYS = {"D7": 7, "D10": 10, "D15": 15, "D60": 60}


def remaining(games, al):
    """Games still to play, per AL club."""
    rem = {t: 0 for t in al}
    for _, a, h in games:
        if a in al: rem[a] += 1
        if h in al: rem[h] += 1
    return rem


def drop_phantoms(games, al, as_of):
    """Remove games that have obviously been played but are still listed as scheduled.

    A club reconciling to 163 rather than 162 means the standings have counted a game
    that the schedule feed has not yet marked final — a routine race between two MLB
    endpoints, and one SYNTHETIC_GAMES cannot fix, since that only adds games.

    A game is only dropped when both of these hold, which is what keeps this from
    guessing:
      * it is dated on or before as_of, i.e. the day of the last confirmed final, so it
        cannot be a genuine future fixture; and
      * every AL club in it is currently over 162. Both clubs played the phantom game,
        so both of their gamesPlayed counts moved — if only one side is over, the
        mismatch is something else and this leaves it alone.

    Anything it cannot explain is left for the caller's 162 check to fail on.
    """
    dropped = []
    while True:
        rem = remaining(games, al)
        over = {t for t in al if al[t]["gp"] + rem[t] > 162}
        if not over:
            break
        cand = next((g for g in sorted(games)
                     if g[0] <= as_of
                     and [x for x in (g[1], g[2]) if x in al]
                     and all(x in over for x in (g[1], g[2]) if x in al)), None)
        if cand is None:
            break                       # nothing defensible left to drop
        games.remove(cand)
        dropped.append(tuple(cand))
        print(f"  note: dropped {cand[1]} at {cand[2]} on {cand[0]} — already counted in "
              f"the standings but still listed as scheduled")
    return dropped


def _try_get(url, timeout=20):
    """Single-attempt fetch that never raises. get() exits the build; this must not."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "jays-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  note: optional fetch failed ({url.split('?')[0]}): {e}")
        return None


def injuries(team_id=141):
    """Who is hurt, which IL, and the earliest they can be back.

    Best-effort in the same way as bref_odds(): the roster endpoint is the only thing
    this really needs, the transactions endpoint just sharpens the return date, and any
    failure anywhere drops the section from the page rather than failing the build.
    """
    roster = _try_get(f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
                      f"?rosterType=fullRoster&season={SEASON}")
    if not roster or "roster" not in roster:
        return []

    hurt = []
    for e in roster.get("roster", []):
        st = (e.get("status") or {})
        code = st.get("code", "")
        if not code.startswith("D"):            # A = active, D* = an injured list
            continue
        hurt.append({
            "name": (e.get("person") or {}).get("fullName", "?"),
            "pos": (e.get("position") or {}).get("abbreviation", ""),
            "status": st.get("description", code),
            "il_days": IL_DAYS.get(code),
            "since": None, "eligible": None, "note": None,
        })
    if not hurt:
        return []

    # when each player went on the IL, so "earliest return" is a real date
    start = (datetime.date.fromisoformat(SEASON_END) - datetime.timedelta(days=250))
    tx = _try_get(f"https://statsapi.mlb.com/api/v1/transactions?teamId={team_id}"
                  f"&startDate={start.isoformat()}&endDate={SEASON_END}")
    placed = {}
    for t in (tx or {}).get("transactions", []):
        if "injured list" not in (t.get("description", "") or "").lower():
            continue
        name = (t.get("person") or {}).get("fullName")
        date = t.get("effectiveDate") or t.get("date")
        if name and date:
            placed[name] = max(placed.get(name, ""), date[:10])

    by_name = {h["name"]: h for h in hurt}
    for name, date in placed.items():
        if name in by_name:
            by_name[name]["since"] = date

    for h in hurt:
        if h["since"] and h["il_days"]:
            h["eligible"] = (datetime.date.fromisoformat(h["since"])
                             + datetime.timedelta(days=h["il_days"])).isoformat()
        h["note"] = INJURY_NOTES.get(h["name"])

    hurt.sort(key=lambda h: (h["eligible"] or "9999", h["name"]))
    print(f"  injuries: {len(hurt)} on the IL")
    return hurt


def recent_form(team_id, today, days=45, limit=25):
    """The club's last completed games, most recent last.

    schedule() already sees finished games but keeps only their dates, and it looks two
    days back, which is far too narrow for form. This is a separate, wider, best-effort
    request for one club, so the critical path — the 162-game reconciliation built from
    every club's remaining schedule — is untouched by it.
    """
    me = AL_IDS.get(team_id)
    start = (today - datetime.timedelta(days=days)).isoformat()
    data = _try_get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1"
                    f"&teamId={team_id}&startDate={start}&endDate={today.isoformat()}")
    if not data:
        return []

    out = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            if g.get("status", {}).get("codedGameState") != "F":
                continue
            try:
                away = canon(g["teams"]["away"]["team"]["name"])
                home = canon(g["teams"]["home"]["team"]["name"])
            except SystemExit:          # an unknown club here must not fail the build
                continue
            if me not in (away, home):
                continue
            at_home = home == me
            side = "home" if at_home else "away"
            won = g["teams"][side].get("isWinner")
            if won is None:             # older payloads carry only the score
                sa, sh = g["teams"]["away"].get("score"), g["teams"]["home"].get("score")
                if sa is None or sh is None:
                    continue
                won = (sh > sa) if at_home else (sa > sh)
            out.append({"date": d["date"], "opp": away if at_home else home,
                        "home": at_home, "won": bool(won)})

    out.sort(key=lambda x: x["date"])
    out = out[-limit:]
    if out:
        w = sum(1 for x in out if x["won"])
        print(f"  recent form: {len(out)} completed games, {w}-{len(out) - w}")
    return out


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
    # A runner's clock is UTC, so at 10pm Eastern it is already tomorrow. Start the
    # schedule window two days back: anything already final is filtered out below, and
    # this guarantees a game still in progress somewhere is counted as "still to play"
    # — which is what the standings assume too, so the 162 check stays consistent.
    today = datetime.date.fromisoformat(
        os.environ["AS_OF_OVERRIDE"]) if os.environ.get("AS_OF_OVERRIDE") \
        else datetime.datetime.now(datetime.timezone.utc).date()
    start = (today - datetime.timedelta(days=2)).isoformat()
    print(f"fetching {SEASON} data, schedule from {start} to {SEASON_END} (UTC today {today})")

    al = standings(103)
    nl = standings(104)
    print(f"  standings: {len(al)} AL, {len(nl)} NL teams")

    # union every AL club's remaining schedule; an AL-vs-AL game appears in both feeds
    counter, final_dates = {}, set()
    for tid in AL_IDS:
        for g in schedule(tid, start, final_dates):
            counter[g] = counter.get(g, 0) + 1
    games = []
    for (date, away, home), n in counter.items():
        both_al = away in al and home in al
        for _ in range(n // 2 if both_al else n):
            games.append([date, away, home])
    for g in SYNTHETIC_GAMES:
        games.append(list(g))
        print(f"  note: added synthetic makeup game {g[1]} at {g[2]} on {g[0]}")
    ignored = []
    for g in IGNORE_GAMES:
        if list(g) in games:
            games.remove(list(g))
            ignored.append(tuple(g))
            print(f"  note: ignoring {g[1]} at {g[2]} on {g[0]} by hand (IGNORE_GAMES)")
        else:
            print(f"  note: IGNORE_GAMES entry {g} is not in the feed — remove it")
    games.sort()
    print(f"  schedule: {len(games)} remaining games")

    # as-of = the most recent day on which a game actually finished, not today.
    # Computed before the 162 check because drop_phantoms needs it to tell a stale
    # listing from a genuine future fixture.
    as_of = max(final_dates) if final_dates else (today - datetime.timedelta(days=1)).isoformat()

    # a club at 163 is the standings and the schedule disagreeing about a game that has
    # already been played; resolve only what is unambiguous, then check as before
    dropped = drop_phantoms(games, al, as_of)

    # every club must reconcile to exactly 162
    rem = remaining(games, al)
    bad = {t: al[t]["gp"] + rem[t] for t in al if al[t]["gp"] + rem[t] != 162}
    if bad:
        print("FATAL: schedule does not reconcile to 162 games:", file=sys.stderr)
        for t, n in sorted(bad.items()):
            print(f"  {t}: {al[t]['gp']} played + {rem[t]} remaining = {n}", file=sys.stderr)
        short = [t for t, n in bad.items() if n < 162]
        longs = [t for t, n in bad.items() if n > 162]
        if short:
            print("\nA club short of 162 is usually a postponement MLB has not yet\n"
                  "rescheduled. Either re-run later, or add the makeup to SYNTHETIC_GAMES\n"
                  "near the top of this file.", file=sys.stderr)
        if longs:
            print("\nA club past 162 is a game the standings count but the schedule still\n"
                  "lists as scheduled. It usually clears within a poll or two; if it does\n"
                  "not, add the stale fixture to IGNORE_GAMES near the top of this file.",
                  file=sys.stderr)
        raise SystemExit(1)
    print("  reconciled: all 15 AL clubs at 162 games")

    data = {
        "season": SEASON, "as_of": as_of, "generated": datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds"),
        "AL": {k: [v["w"], v["l"], v["rs"], v["ra"]] for k, v in al.items()},
        "NL": {k: [v["w"], v["l"], v["rs"], v["ra"]] for k, v in nl.items()},
        "DIVISIONS": DIVISIONS, "GAMES": games, "BREF": bref_odds(),
        "INJURIES": injuries(),
        "RECENT": recent_form(141, today),
        "SYNTHETIC": [list(g) for g in SYNTHETIC_GAMES],
        "REMOVED": [list(g) for g in ignored + dropped],
        "fingerprint": fingerprint(al, nl),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
    j = data["AL"]["Blue Jays"]
    print(f"  Blue Jays {j[0]}-{j[1]}, run diff {j[2]-j[3]:+d}, as of {data['as_of']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
