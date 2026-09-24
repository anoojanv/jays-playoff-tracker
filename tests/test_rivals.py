"""
The rivals the page talks about are read off the standings, not typed into the source.

In September 2026 the Blue Jays page this replaced was still calling a list written in
August "the cluster", while the club actually holding the last spot was not in it. These
cases pin down what the derived list must do instead.

Run:  python tests/test_rivals.py
"""
import sys
from _harness import case, run, load


@case("the cluster is the conference clubs projected within range of Toronto")
def _():
    m = load()
    me = m.PROJ["TOR"]
    for t in m.CLUSTER:
        assert m.CONF[t] == "Eastern" and t != "TOR"
        assert abs(m.PROJ[t] - me) <= m.CLUSTER_PTS, t
    for t in m.CONF_TEAMS["Eastern"]:
        if t != "TOR" and abs(m.PROJ[t] - me) <= m.CLUSTER_PTS:
            assert t in m.CLUSTER, f"{t} is in range but missing"


@case("a Western club is never a rival, however close its points")
def _():
    m = load()
    assert not any(m.CONF[t] == "Western" for t in m.CLUSTER + m.RIVALS)


@case("the list follows the standings: a club that surges joins it")
def _():
    m = load()
    far = min(m.CONF_TEAMS["Eastern"], key=lambda t: m.PROJ[t])
    assert far not in m.CLUSTER

    def edit(d):
        # the same games played, now with Toronto's exact record and goals
        mine = d["TEAMS"]["TOR"]
        d["TEAMS"][far].update({k: mine[k] for k in ("w", "l", "otl", "gf", "ga", "rw")})
    m2 = load(edit)
    assert far in m2.CLUSTER, (far, m2.PROJ[far], m2.PROJ["TOR"])


@case("a club running away from everyone still has two rivals to describe")
def _():
    def edit(d):
        r = d["TEAMS"]["TOR"]
        r["w"], r["l"], r["otl"] = r["w"] + r["l"] + r["otl"], 0, 0
        r["gf"] += 100
    m = load(edit)
    assert len(m.CLUSTER) >= 2
    others = sorted((t for t in m.CONF_TEAMS["Eastern"] if t != "TOR"),
                    key=lambda t: abs(m.PROJ[t] - m.PROJ["TOR"]))
    assert set(others[:2]) <= set(m.CLUSTER)


@case("every other Eastern club is a candidate for the scoreboard panel")
def _():
    m = load()
    assert sorted(m.RIVALS) == sorted(t for t in m.CONF_TEAMS["Eastern"] if t != "TOR")
    assert len(m.RIVALS) == 15


if __name__ == "__main__":
    sys.exit(run("RIVALS TEST"))
