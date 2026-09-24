"""
Seeding and drawing the playoff bracket, NHL-style.

Top three in each division, then two wild cards. The better division winner draws the
second wild card. Every series best of seven, home ice to the better regular season. The
page draws the bracket as one picture — one club per seat — and the browser draws it the
same way, so both are checked here.

Run:  python tests/test_bracket.py
"""
import sys, collections
import numpy as np
from _harness import case, run, load

model = load()
st = model.simulate(nsim=6000, seed=3)
rng = np.random.default_rng(5)
ps = model.postseason(st, rng)
bk = model.bracket(st)


@case("seat order: division winners in 1 and 5, second and third behind them")
def _():
    s = model.seats_of(st, "Eastern")
    d1, d2 = model.D.CONFERENCES["Eastern"]
    for k, (div, rank) in {0: (d1, 1), 2: (d1, 2), 3: (d1, 3),
                           4: (d2, 1), 6: (d2, 2), 7: (d2, 3)}.items():
        for c in range(0, st.nsim, 97):
            t = model.TEAMS[s[k, c]]
            assert model.DIV[t] == div and st.div_rank[s[k, c], c] == rank


@case("the better division winner draws the second wild card")
def _():
    s = model.seats_of(st, "Eastern")
    for c in range(st.nsim):
        w1_top = st.score[s[0, c], c] > st.score[s[4, c], c]
        top_opp, other_opp = (s[1, c], s[5, c]) if w1_top else (s[5, c], s[1, c])
        assert st.wc_rank[top_opp, c] == 2 and st.wc_rank[other_opp, c] == 1


@case("the eight seats are exactly the eight qualifiers")
def _():
    for conf in ("Eastern", "Western"):
        s = model.seats_of(st, conf)
        for c in range(0, st.nsim, 53):
            seated = set(s[:, c].tolist())
            assert len(seated) == 8
            q = {model.idx[t] for t in model.CONF_TEAMS[conf] if st.playoff[model.idx[t], c]}
            assert seated == q


@case("every winner comes out of the series that feeds it")
def _():
    for key, (a, b) in model.FEEDERS.items():
        assert np.all((ps[key] == ps[a]) | (ps[key] == ps[b])), key


@case("home ice is worth something, and a better club wins more series")
def _():
    r = np.random.default_rng(1)
    n = 40000
    even = model.play_series(r, np.full(n, .5), np.full(n, .5)).mean()
    assert 0.5 < even < 0.56, even
    better = model.play_series(r, np.full(n, .6), np.full(n, .5)).mean()
    assert better > 0.65, better


@case("the drawn bracket: Toronto pinned, opposite its likeliest opponent")
def _():
    p = bk["focus_conf"]
    seat = bk["best_seat"]
    assert bk["nodes"][f"{p}{seat}"][0]["team"] == "TOR"
    partner = {1: 2, 2: 1, 3: 4, 4: 3, 5: 6, 6: 5, 7: 8, 8: 7}[seat]
    assert bk["nodes"][f"{p}{partner}"][0]["team"] == bk["best_seat_opponent"]


@case("the drawn bracket: one club per seat, each round from its two feeders")
def _():
    for p in ("E", "W"):
        seated = [bk["nodes"][f"{p}{k}"][0]["team"] for k in range(1, 9)]
        assert len(set(seated)) == 8, seated
    for key, (a, b) in model.FEEDERS.items():
        top = bk["nodes"][key][0]["team"]
        assert top in (bk["nodes"][a][0]["team"], bk["nodes"][b][0]["team"]), key


@case("coherent picks: pins kept, greedy fill, later slots go to the likelier feeder")
def _():
    C = collections.Counter
    counts = {f"E{k}": C() for k in range(1, 9)}
    counts["E1"].update({0: 50, 1: 40}); counts["E2"].update({0: 45, 2: 30})
    counts["E3"].update({1: 60, 3: 10}); counts["E4"].update({4: 20})
    for k in range(5, 9):
        counts[f"E{k}"].update({10 + k: 30})
    counts["Er1a"] = C({0: 30, 2: 5}); counts["Er1b"] = C({1: 25, 4: 10})
    counts["Er1c"] = C({15: 10, 16: 20}); counts["Er1d"] = C({17: 5, 18: 9})
    counts["Er2a"] = C({0: 3, 1: 12}); counts["Er2b"] = C({16: 7, 18: 2})
    counts["Ecf"] = C({1: 4, 16: 6})
    picks = model.coherent_picks(counts, {"E2": 9})
    assert picks["E2"] == 9                       # the pin wins over a likelier club
    assert picks["E3"] == 1 and picks["E1"] == 0  # 1 goes where it is likeliest
    assert picks["Er1a"] == 0 and picks["Er1b"] == 1
    assert picks["Er2a"] == 1 and picks["Ecf"] == 16


@case("Toronto's road narrows round by round, and the shares make sense")
def _():
    r = bk["road"]
    assert 1 >= r["r1"] >= r["r2"] >= r["cf"] >= r["cup"] >= 0
    assert abs(sum(bk["seat_dist"].values()) - 1) < 1e-9
    assert abs(sum(bk["labels"].values()) - 1) < 1e-9
    assert abs(bk["p_qualify"] - st.focus_in.mean()) < 1e-12


@case("the browser draws the bracket by the same rule")
def _():
    src = open("app.js").read()
    for needle in ("function readBracket", "used[t]", "better(n, pick[FEED",
                   "pick[PARTNER[best - 1]] = bo"):
        assert needle in src, needle


if __name__ == "__main__":
    sys.exit(run("BRACKET TEST"))
