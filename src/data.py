"""Loads build/data.json (written by fetch_data.py) and exposes it to the pipeline."""
import json, os

_P = os.path.join(os.path.dirname(__file__), "..", "build", "data.json")
with open(_P) as f:
    _D = json.load(f)

SEASON    = _D["season"]
AS_OF     = _D["as_of"]
GENERATED = _D["generated"]
AL        = {k: tuple(v) for k, v in _D["AL"].items()}
NL        = {k: tuple(v) for k, v in _D["NL"].items()}
DIVISIONS = _D["DIVISIONS"]
GAMES     = [tuple(g) for g in _D["GAMES"]]
BREF      = _D.get("BREF")
FINGERPRINT = _D.get("fingerprint", "")
