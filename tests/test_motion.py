"""
The data the motion graphics animate, and the model change the backtest led to.

The season machine and the forecast cone draw the simulation's shape directly, so a
histogram that does not sum to its seasons, or a points path that goes backwards, would
put a false picture on the page. These pin down the invariants, the strength-uncertainty
term's meaning, and the committed backtest the report card is drawn from.

Run:  python tests/test_motion.py
"""
import json, os, subprocess, sys
import numpy as np
from _harness import case, run, load, fixture, SRC, ROOT

model = load()
subprocess.run([sys.executable, "sim.py"], cwd=SRC, check=True, capture_output=True)
R = json.load(open(os.path.join(SRC, "results.json")))
M, CONE = R["machine"], R["cone"]
NB = M["hi"] - M["lo"] + 1


@case("every machine histogram accounts for exactly its seasons")
def _():
    for name, st in M["states"].items():
        assert len(st["in"]) == len(st["out"]) == NB, name
        assert sum(st["in"]) + sum(st["out"]) == st["n"], name
        assert abs(st["odds"] - sum(st["in"]) / st["n"]) < 1e-9, name
    assert M["states"]["model"]["n"] == M["nsim"]


@case("tonight's two futures partition the seasons, and winning helps")
def _():
    w, l, a = M["states"]["win"], M["states"]["loss"], M["states"]["model"]
    assert w["n"] + l["n"] == a["n"]
    assert w["odds"] > a["odds"] > l["odds"]
    # the whole is the weighted mix of its two halves
    assert abs(a["odds"] - (w["odds"] * w["n"] + l["odds"] * l["n"]) / a["n"]) < 1e-9


@case("the machine's headline is the page's headline")
def _():
    assert abs(M["states"]["model"]["odds"] - R["odds"]["playoff"]) < 1e-9


@case("cone bands cover every remaining game, ordered and never falling")
def _():
    n = R["games_left"]
    assert len(CONE["dates"]) == n
    q = CONE["q"]
    for k in ("p5", "p25", "p50", "p75", "p95"):
        assert len(q[k]) == n, k
        assert all(b >= a for a, b in zip(q[k], q[k][1:])), f"{k} goes backwards"
    for i in range(n):
        assert q["p5"][i] <= q["p25"][i] <= q["p50"][i] <= q["p75"][i] <= q["p95"][i], i
    assert q["p5"][0] >= CONE["start_pts"] and q["p95"][-1] <= CONE["start_pts"] + 2 * n


@case("every sampled path is a real season: from today's points, 0-2 a game")
def _():
    for p in CONE["paths"]:
        steps = np.diff([CONE["start_pts"]] + p["pts"])
        assert len(p["pts"]) == R["games_left"]
        assert set(steps.tolist()) <= {0, 1, 2}, set(steps.tolist())


@case("the season log ends on the standings")
def _():
    t = fixture()["TEAMS"]["TOR"]
    log = CONE["log"]
    assert len(log) == t["w"] + t["l"] + t["otl"] == CONE["start_gp"]
    assert log[-1]["pts"] == 2 * t["w"] + t["otl"] == CONE["start_pts"]
    assert sum(1 for g in log if g["res"] == "OTL") == t["otl"]


@case("strength uncertainty narrows as games are played")
def _():
    sd = model.talent_sd()
    assert all(v > 0 for v in sd.values())

    def edit(d):                          # the same clubs, twice as many games in
        for r in d["TEAMS"].values():
            for k in ("w", "l", "otl", "gf", "ga", "rw"):
                r[k] *= 2
        d["season_games"] = 2 * d["season_games"] - 34
    later = load(edit).talent_sd()
    assert all(later[t] < sd[t] for t in sd)


@case("with no uncertainty every season plays the same strengths; with it, odds pull in")
def _():
    m = load()
    zero = {t: 0.0 for t in m.TEAMS}
    a = m.simulate(nsim=4000, seed=5, sd=zero)
    assert np.allclose(a.tal_sim, a.tal_sim[:, :1])
    b = m.simulate(nsim=4000, seed=5)
    spread = lambda st: np.mean(np.abs(st.playoff.mean(axis=1) - 0.5))
    assert spread(b) < spread(a), "uncertainty must make the model less sure, not more"


@case("the browser simulator carries the same strength uncertainty as the model")
def _():
    subprocess.run([sys.executable, "export_sim.py"], cwd=SRC, check=True, capture_output=True)
    sim = json.load(open(os.path.join(SRC, "simdata.json")))
    sd = model.talent_sd()
    assert [round(sd[t], 6) for t in sim["teams"]] == sim["sd"]
    src = open(os.path.join(SRC, "app.js")).read()
    for needle in ("D.sd", "HAS_SD", "oddsEff[g] * EN[a] / EN[h]", "pGame(TS[hi], TS[lo]"):
        assert needle in src, needle


@case("the committed backtest is a held-out season, scored honestly")
def _():
    path = os.path.join(ROOT, "data", "backtest_20252026.json")
    b = json.load(open(path))
    assert b["held_out"] and b["fit_season"] != b["season"]
    assert sum(b["truth"].values()) == 16 and len(b["truth"]) == 32
    assert sum(x["n"] for x in b["bins"]) == b["n_predictions"]
    assert abs(b["brier"]["coin"] - 0.25) < 1e-9
    for x in b["bins"]:
        assert x["lo"] <= x["p"] <= x["hi"] and 0 <= x["freq"] <= 1
    # what the report card says, held to the data
    assert b["brier"]["model"] < b["brier"]["standings"] < b["brier"]["coin"]
    assert b["brier"]["model"] < b["brier"]["previous"]


@case("the training season is committed too, so the fit can be re-checked")
def _():
    b = json.load(open(os.path.join(ROOT, "data", "backtest_20242025.json")))
    assert not b["held_out"] and b["season"] == b["fit_season"]


if __name__ == "__main__":
    sys.exit(run("MOTION TEST"))
