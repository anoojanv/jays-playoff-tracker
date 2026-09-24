"""Loads build/data.json (written by fetch_data.py) and exposes it to the pipeline."""
import json, os

_P = os.path.join(os.path.dirname(__file__), "..", "build", "data.json")
with open(_P) as f:
    _D = json.load(f)

SEASON       = _D["season"]
SEASON_GAMES = _D["season_games"]
FOCUS        = _D["focus"]
TRACKER_ID   = _D.get("tracker_id", f"nhl-{FOCUS}-{SEASON}")
PRESEASON    = _D.get("preseason", False)
AS_OF        = _D["as_of"]
GENERATED    = _D["generated"]
# abbrev -> {name, city, conf, div, w, l, otl, gf, ga, rw}
TEAMS        = _D["TEAMS"]
# abbrev -> last season's final {w, l, otl, gf, ga, gp}; may be missing for a new club
PRIOR        = _D.get("PRIOR", {})
# measured from last season: share of games past regulation, and home win rate
LEAGUE       = _D.get("LEAGUE", {"p_ot": 0.248, "home_win": 0.522})
DIVISIONS    = _D["DIVISIONS"]
CONFERENCES  = _D["CONFERENCES"]
GAMES        = [tuple(g) for g in _D["GAMES"]]
# first puck drop (UTC ISO) and game state for the focus club's remaining games
TIMES        = _D.get("TIMES", {})
# the focus club's completed games, oldest first; drives the momentum rating
RECENT       = _D.get("RECENT", [])
# encoded readings carried forward from the published page; see history.py
HISTORY      = _D.get("HISTORY", "")
FINGERPRINT  = _D.get("fingerprint", "")


def points(t):
    r = TEAMS[t]
    return 2 * r["w"] + r["otl"]


def played(t):
    r = TEAMS[t]
    return r["w"] + r["l"] + r["otl"]
