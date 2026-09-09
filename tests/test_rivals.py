"""
The rivals the page talks about are read off the standings, not typed into the source.

In September 2026 the live page was still calling the Rangers, Tigers, Guardians and
Twins "the cluster" — a list written in August — while the Tigers were six back with no
chance and the club actually holding the last spot was not in it. These cases pin down
what the derived list must do instead.

Run:  python tests/test_rivals.py
"""
import json, os, shutil, sys, importlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
FIXTURE = os.path.join(HERE, "fixture_data.json")

_build = os.path.join(ROOT, "build")
_data = os.path.join(_build, "data.json")
os.makedirs(_build, exist_ok=True)
sys.path.insert(0, SRC)
os.chdir(SRC)

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def load(edit=None):
    """Import model against the fixture, optionally with the AL standings doctored."""
    data = json.load(open(FIXTURE))
    if edit:
        edit(data["AL"])
    json.dump(data, open(_data, "w"))
    for m in ("data", "model"):
        sys.modules.pop(m, None)
    return importlib.import_module("model")


@case("the cluster is the clubs within range of Toronto, leaders excluded")
def _():
    model = load()
    al = json.load(open(FIXTURE))["AL"]
    pct = lambda t: al[t][0] / (al[t][0] + al[t][1])
    leaders = {max(m, key=pct) for m in model.D.DIVISIONS.values()}
    for t in model.CLUSTER:
        assert t != model.JAYS
        assert t not in leaders, t
        assert abs(model.games_back(t)) <= model.CLUSTER_GB, (t, model.games_back(t))
    # and nothing in range was left out
    for t in al:
        if t != model.JAYS and t not in leaders and abs(model.games_back(t)) <= model.CLUSTER_GB:
            assert t in model.CLUSTER, t


@case("a club that falls out of the race falls out of the cluster")
def _():
    def bury(al):
        al["Tigers"] = [40, 83, 400, 600]           # 20-odd games back
    model = load(bury)
    assert "Tigers" not in model.CLUSTER, model.CLUSTER


@case("a club that climbs into the race is picked up")
def _():
    def surge(al):
        # from nine back to six back of Toronto's 67-56, still behind the White Sox
        # for the Central lead, so it is a chaser rather than a leader
        al["Royals"] = [61, 62, 530, 540]
    model = load(surge)
    assert "Royals" in model.CLUSTER, model.CLUSTER


@case("there is always a race to describe, even with nobody close")
def _():
    def runaway(al):
        al["Blue Jays"] = [100, 23, 700, 400]
    model = load(runaway)
    assert len(model.CLUSTER) >= 2, model.CLUSTER


@case("every other AL club is a candidate for scoreboard watching")
def _():
    model = load()
    assert model.JAYS not in model.RIVALS
    assert len(model.RIVALS) == 14, model.RIVALS


def main():
    saved = open(_data).read() if os.path.exists(_data) else None
    fails = []
    try:
        for name, fn in CASES:
            try:
                fn()
                print(f"  OK    {name}")
            except AssertionError as e:
                print(f"  FAIL  {name}\n        {e}")
                fails.append(name)
    finally:
        if saved is not None:
            open(_data, "w").write(saved)
        else:
            shutil.copyfile(FIXTURE, _data)
    print("\n" + "=" * 58)
    if fails:
        print(f"RIVALS TEST FAILED ({len(fails)} of {len(CASES)})")
        return 1
    print(f"RIVALS TEST PASSED — all {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
