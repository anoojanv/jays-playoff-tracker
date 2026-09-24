"""
Around the league: every remaining game Toronto is not playing, scored against Toronto's
odds from the same simulated seasons, and told which side to cheer.

Run:  python tests/test_spoiler.py
"""
import sys, math
from _harness import case, run, load

model = load()
st = model.simulate(nsim=12000, seed=11)
around = model.around_the_league(st)


@case("Toronto's own games are never listed, and neither are all-Western games")
def _():
    for g in around:
        assert "TOR" not in (g["away"], g["home"])
        assert "Eastern" in (model.CONF[g["away"]], model.CONF[g["home"]])
    east_games = sum(1 for _, a, h in model.games
                     if "TOR" not in (a, h) and "Eastern" in (model.CONF[a], model.CONF[h]))
    assert len(around) == east_games


@case("the club to root for is the one whose win raises Toronto's odds")
def _():
    fin = st.focus_in
    for g in around[:40]:
        i = model.games.index((g["date"], g["away"], g["home"]))
        w = st.home_wins[i]
        up = fin[w].mean() - fin[~w].mean()
        assert g["root"] == (g["home"] if up > 0 else g["away"])
        assert abs(g["leverage"] - abs(up)) < 1e-12


@case("a West-vs-East game: root for the Western club far more often than not")
def _():
    cross = [g for g in around if g["sure"] and
             {model.CONF[g["away"]], model.CONF[g["home"]]} == {"Eastern", "Western"}]
    assert len(cross) > 20
    west = sum(1 for g in cross if model.CONF[g["root"]] == "Western")
    assert west / len(cross) > 0.9, f"{west} of {len(cross)}"


@case("'sure' means the swing clears twice its own Monte Carlo error")
def _():
    n = st.nsim
    for g in around[:80]:
        i = model.games.index((g["date"], g["away"], g["home"]))
        w = st.home_wins[i]
        nw = int(w.sum())
        p1, p2 = st.focus_in[w].mean(), st.focus_in[~w].mean()
        se = math.sqrt(p1 * (1 - p1) / nw + p2 * (1 - p2) / (n - nw))
        assert g["sure"] == (g["leverage"] > 2 * se)


@case("sorted by date, biggest first within a day")
def _():
    for x, y in zip(around, around[1:]):
        assert (x["date"], -x["leverage"]) <= (y["date"], -y["leverage"])


@case("'both in the race' marks exactly the games between two live clubs")
def _():
    po = {t: st.playoff[model.idx[t]].mean() for t in model.TEAMS}
    live = lambda t: 0.05 < po[t] < 0.98
    assert any(g["h2h"] for g in around) and not all(g["h2h"] for g in around)
    for g in around:
        assert g["h2h"] == (live(g["away"]) and live(g["home"])), g


if __name__ == "__main__":
    sys.exit(run("SPOILER TEST"))
