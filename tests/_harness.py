"""
Shared plumbing for the model tests: load the model against the fixture (optionally
doctored), and a tiny case runner so every file reports the same way.
"""
import json, os, sys, importlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
FIXTURE = os.path.join(HERE, "fixture_data.json")
BUILD = os.path.join(ROOT, "build")
DATA = os.path.join(BUILD, "data.json")

os.makedirs(BUILD, exist_ok=True)
sys.path.insert(0, SRC)
os.chdir(SRC)

_saved = open(DATA).read() if os.path.exists(DATA) else None


def fixture():
    return json.load(open(FIXTURE))


def load(edit=None):
    """Import model against the fixture, after edit(data) has doctored it if given."""
    data = fixture()
    if edit:
        edit(data)
    json.dump(data, open(DATA, "w"))
    for m in ("data", "model"):
        sys.modules.pop(m, None)
    return importlib.import_module("model")


def pts(rec):
    return 2 * rec["w"] + rec["otl"]


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def run(title):
    fails = 0
    try:
        for name, fn in CASES:
            try:
                fn()
                print(f"  ok    {name}")
            except Exception as e:                 # noqa: BLE001 — report every case
                fails += 1
                print(f"  FAIL  {name}\n        {type(e).__name__}: {e}")
    finally:
        # leave build/data.json as it was found
        if _saved is not None:
            open(DATA, "w").write(_saved)
    print("\n" + "=" * 58)
    if fails:
        print(f"{title} FAILED — {fails} of {len(CASES)} cases")
        return 1
    print(f"{title} PASSED — all {len(CASES)} cases")
    return 0
