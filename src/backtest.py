"""
Grade the model against a season that already happened — the outside judge.

A model should not mark its own homework. This replays last season through the real
pipeline, one weekly snapshot at a time, knowing only what was known that morning: the
season before as the prior, and the games played up to that date. Each snapshot's
playoff odds for all 32 clubs are then scored against who actually made it, as the
league recorded it (the standings' clinch flag), not as this model would decide it.

Two baselines keep the score honest:
  * a coin — every club 50% — the floor any model must clear
  * the standings — 100% for clubs in a playoff spot that morning, 0% for the rest —
    which is what a fan reading the table is effectively assuming

Scoring is the Brier score (mean squared error of a probability; lower is better, a
coin scores 0.25). The calibration bins say whether "70%" came true about 70% of the
time. The 832 predictions are not independent — the same clubs, week after week — so
the page shows the counts alongside and makes no claim of significance.

Writes data/backtest_<season>.json, which is committed: the season is over, the result
never changes, and the nightly build must not depend on fetching a past season.

  python src/backtest.py                 # 2025-26, the season before the current one
  python src/backtest.py 20242025        # any completed season with a prior before it
"""
import datetime, importlib, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fetch_data as fd                                   # noqa: E402

NSIM = 5000
STEP_DAYS = 7
# the model's constants are fitted on this season and graded on the next; the settings
# they replaced are replayed alongside, so the improvement is measured, not asserted
FIT_SEASON = "20242025"
PREVIOUS = {"scale": 0.0, "prior_weight": 40.0, "reg_prior": 40.0}
EARLY_DAYS = 49            # "the first seven weeks", where the prior does most of the work


def fetch(season):
    """Everything needed to replay `season`, cached so a re-run needs no network."""
    cache = os.path.join(ROOT, "build", f"backtest_raw_{season}.json")
    if os.path.exists(cache):
        return json.load(open(cache))
    prior_id = fd.previous_season(season)
    end, prior_end = fd.season_end(season), fd.season_end(prior_id)
    final = fd.standings_on(end)
    prior = fd.standings_on(prior_end)
    teams, divisions, conferences = fd.alignment(final)
    by_id = {}
    for ab in sorted(teams):
        for g in fd.club_schedule(ab, season):
            by_id[g["id"]] = fd.parse_game(g)
    raw = {"season": season, "final": final, "prior": prior, "teams": teams,
           "divisions": divisions, "conferences": conferences,
           "games": sorted(by_id.values(), key=lambda g: (g["date"], g["id"]))}
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump(raw, open(cache, "w"))
    return raw


def snapshot(raw, date):
    """The data.json the pipeline would have built on the morning of `date`."""
    done = [g for g in raw["games"] if g["date"] < date and g["state"] in fd.FINAL_STATES]
    teams = {t: dict(v) for t, v in raw["teams"].items()}
    for t, r in fd.build_records(done, teams).items():
        teams[t].update(r)
    left = [[g["date"], g["away"], g["home"]] for g in raw["games"] if g["date"] >= date]
    lengths = {len([g for g in raw["games"] if t in (g["away"], g["home"])]) for t in teams}
    return {
        "season": raw["season"], "season_games": lengths.pop(), "focus": "TOR",
        "tracker_id": f"backtest-{raw['season']}", "preseason": not done,
        "as_of": date, "generated": date + "T07:00:00+00:00",
        "TEAMS": teams, "PRIOR": fd.prior_records(raw["prior"]),
        "LEAGUE": fd.league_rates(raw["prior"]),
        "DIVISIONS": raw["divisions"], "CONFERENCES": raw["conferences"],
        "GAMES": sorted(left), "TIMES": {}, "RECENT": fd.recent_form(done, "TOR"),
        "HISTORY": "", "fingerprint": f"backtest-{date}",
    }


def standings_call(d):
    """1 for clubs in a playoff spot that morning by points percentage, else 0.

    The same field the model uses — three per division, then two wild cards — read off
    the table as it stood. Before anyone has played, every club is a coin flip.
    """
    teams = d["TEAMS"]
    gp = {t: v["w"] + v["l"] + v["otl"] for t, v in teams.items()}
    if not any(gp.values()):
        return {t: 0.5 for t in teams}
    pct = {t: (2 * v["w"] + v["otl"]) / (2 * gp[t]) if gp[t] else 0.5
           for t, v in teams.items()}
    key = lambda t: (pct[t], teams[t]["rw"])
    out = {t: 0.0 for t in teams}
    for conf, divs in d["CONFERENCES"].items():
        rest = []
        for div in divs:
            order = sorted(d["DIVISIONS"][div], key=key, reverse=True)
            for t in order[:3]:
                out[t] = 1.0
            rest += order[3:]
        for t in sorted(rest, key=key, reverse=True)[:2]:
            out[t] = 1.0
    return out


def run_model(d, nsim=NSIM, **spec):
    """Load the real model against snapshot `d` and return every club's playoff odds.

    `spec` (scale, prior_weight, reg_prior) overrides the model's constants — used only
    to fit them on a training season, never to grade the season being reported."""
    path = os.path.join(tempfile.gettempdir(), f"backtest_{os.getpid()}.json")
    json.dump(d, open(path, "w"))
    os.environ["TRACKER_DATA"] = path
    for m in ("data", "model"):
        sys.modules.pop(m, None)
    model = importlib.import_module("model")
    if spec:
        pw = spec.get("prior_weight", model.PRIOR_WEIGHT)
        rp = spec.get("reg_prior", model.REG_PRIOR)
        st = model.simulate(nsim=nsim, seed=model.SEED,
                            tal=model.build_talent(prior_weight=pw, reg_prior=rp),
                            sd=model.talent_sd(spec.get("scale", model.SIGMA_SCALE), pw, rp))
    else:
        st = model.simulate(nsim=nsim, seed=model.SEED)
    os.remove(path)
    return {t: float(st.playoff[model.idx[t]].mean()) for t in model.TEAMS}


def brier(pairs):
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else None


def main():
    season = sys.argv[1] if len(sys.argv) > 1 else fd.previous_season(fd.SEASON)
    raw = fetch(season)
    truth = {r["teamAbbrev"]["default"]: int(r.get("clinchIndicator") != "e")
             for r in raw["final"]}
    assert sum(truth.values()) == 16, f"expected 16 qualifiers, got {sum(truth.values())}"

    first = min(g["date"] for g in raw["games"])
    tor_last = max(g["date"] for g in raw["games"] if "TOR" in (g["away"], g["home"]))
    dates, d = [], datetime.date.fromisoformat(first)
    while d.isoformat() <= tor_last:
        dates.append(d.isoformat())
        d += datetime.timedelta(days=STEP_DAYS)

    snaps = []
    for date in dates:
        data = snapshot(raw, date)
        odds = run_model(data)
        prev = run_model(data, **PREVIOUS)
        base = standings_call(data)
        gp = sum(v["w"] + v["l"] + v["otl"] for v in data["TEAMS"].values()) / len(truth)
        snaps.append({"date": date, "gp": round(gp, 1),
                      "model": {t: round(p, 3) for t, p in sorted(odds.items())},
                      "previous": {t: round(p, 3) for t, p in sorted(prev.items())},
                      "standings": base})
        print(f"  {date}  avg GP {gp:5.1f}  Leafs {odds['TOR'] * 100:5.1f}%  "
              f"Brier {brier([(odds[t], truth[t]) for t in truth]):.3f}")

    pairs = {k: [(s[k][t], truth[t]) for s in snaps for t in truth]
             for k in ("model", "previous", "standings")}
    pairs["coin"] = [(0.5, truth[t]) for s in snaps for t in truth]
    cutoff = (datetime.date.fromisoformat(first)
              + datetime.timedelta(days=EARLY_DAYS)).isoformat()
    early = [s for s in snaps if s["date"] < cutoff]
    early_pairs = {k: [(s[k][t], truth[t]) for s in early for t in truth]
                   for k in ("model", "previous", "standings")}
    early_pairs["coin"] = [(0.5, truth[t]) for s in early for t in truth]

    bins = []
    for b in range(10):
        lo, hi = b / 10, (b + 1) / 10
        inb = [(p, y) for p, y in pairs["model"] if lo <= p < hi or (b == 9 and p == 1.0)]
        if inb:
            bins.append({"lo": lo, "hi": hi, "n": len(inb),
                         "p": round(sum(p for p, _ in inb) / len(inb), 4),
                         "freq": round(sum(y for _, y in inb) / len(inb), 4)})

    misses = sorted(({"team": t, "date": s["date"], "p": s["model"][t], "made": truth[t]}
                     for s in snaps for t in truth),
                    key=lambda m: -abs(m["p"] - m["made"]))
    seen, worst = set(), []
    for m in misses:                         # one entry per club, its worst moment
        if m["team"] not in seen:
            seen.add(m["team"]); worst.append(m)
        if len(worst) == 5:
            break

    out = {
        "season": season, "prior_season": fd.previous_season(season),
        "generated": datetime.date.today().isoformat(),
        "nsim": NSIM, "step_days": STEP_DAYS, "n_predictions": len(pairs["model"]),
        "truth": truth,
        "names": {t: v["name"] for t, v in raw["teams"].items()},
        "held_out": season != FIT_SEASON, "fit_season": FIT_SEASON,
        "previous_settings": PREVIOUS,
        "brier": {k: round(brier(v), 4) for k, v in pairs.items()},
        "brier_early": {k: round(brier(v), 4) for k, v in early_pairs.items()},
        "early_weeks": EARLY_DAYS // 7,
        "by_date": [{"date": s["date"], "gp": s["gp"],
                     "model": round(brier([(s["model"][t], truth[t]) for t in truth]), 4),
                     "standings": round(brier([(s["standings"][t], truth[t]) for t in truth]), 4)}
                    for s in snaps],
        "bins": bins,
        "leafs": [{"date": s["date"], "p": s["model"]["TOR"]} for s in snaps],
        "worst": worst,
        "snapshots": [{"date": s["date"], "model": s["model"]} for s in snaps],
    }
    dest = os.path.join(ROOT, "data", f"backtest_{season}.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    b = out["brier"]
    e = out["brier_early"]
    print(f"\nBrier — model {b['model']:.4f} (previous settings {b['previous']:.4f}) · "
          f"standings {b['standings']:.4f} · coin {b['coin']:.4f}  "
          f"({out['n_predictions']} predictions, {len(snaps)} snapshots)")
    print(f"first {out['early_weeks']} weeks — model {e['model']:.4f} · previous "
          f"{e['previous']:.4f} · standings {e['standings']:.4f} · coin {e['coin']:.4f}")
    print(f"wrote {dest} ({os.path.getsize(dest) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
