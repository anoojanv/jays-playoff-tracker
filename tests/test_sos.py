"""
Strength of schedule: what an average club would win against each team's remaining
opponents, home and road included. Descriptive only — the simulation already prices
every game — so these cases pin down what the number means.

Run:  python tests/test_sos.py
"""
import sys
from _harness import case, run, load

model = load()


@case("every club with games left gets a rate strictly between 0 and 1")
def _():
    sos = model.strength_of_schedule()
    for t in model.TEAMS:
        assert sos[t] is not None and 0 < sos[t] < 1, (t, sos[t])


@case("a league of identical clubs gives everyone the same schedule, bar home ice")
def _():
    flat = {t: 0.5 for t in model.TEAMS}
    sos = model.strength_of_schedule(flat)
    home = {t: 0 for t in model.TEAMS}
    for _, a, h in model.games:
        home[h] += 1
    for t in model.TEAMS:
        expected = (home[t] * model.matchup(0.5, 0.5, True)
                    + (model.rem[t] - home[t]) * model.matchup(0.5, 0.5, False)) / model.rem[t]
        assert abs(sos[t] - expected) < 1e-12, t


@case("making Toronto's opponents better makes Toronto's schedule harder")
def _():
    opps = {a if h == "TOR" else h for _, a, h in model.games if "TOR" in (a, h)}
    tal = dict(model.talent)
    before = model.strength_of_schedule(tal)["TOR"]
    for t in opps:
        tal[t] = min(0.95, tal[t] + 0.05)
    after = model.strength_of_schedule(tal)["TOR"]
    assert after < before, (before, after)


@case("a club's own strength does not enter its own schedule")
def _():
    tal = dict(model.talent)
    before = model.strength_of_schedule(tal)["TOR"]
    tal["TOR"] = 0.9
    assert abs(model.strength_of_schedule(tal)["TOR"] - before) < 1e-12


if __name__ == "__main__":
    sys.exit(run("SOS TEST"))
