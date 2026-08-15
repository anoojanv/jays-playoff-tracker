"""Path analysis: what a qualifying season actually looks like, series by series."""
import json, collections
import numpy as np
import data as D

exec(open("sim.py").read().split('with open("results.json"')[0])

path = {}
# conditional on making the playoffs, how did each series go?
rows = []
for s in series:
    sw = jays_won[s["ix"]].sum(axis=0)
    n = len(s["ix"])
    e_all = sw.mean()
    e_in = sw[jays_in].mean()
    e_out = sw[~jays_in].mean()
    # P(in | won the series)
    won_series = sw > n / 2
    rows.append({
        "opp": s["opp"], "home": s["home"], "start": s["start"], "end": s["end"], "n": n,
        "opp_rec": f"{TEAMS[s['opp']][0]}-{TEAMS[s['opp']][1]}",
        "opp_talent": round(talent[s["opp"]], 4),
        "exp": float(e_all), "need": float(e_in), "if_out": float(e_out),
        "target": int(np.ceil(e_in - 1e-9)),
        "p_in_if_win_series": float(jays_in[won_series].mean()),
        "p_in_if_lose_series": float(jays_in[~won_series].mean()),
        "swing_series": float(jays_in[won_series].mean() - jays_in[~won_series].mean()),
        "cond": {int(w): [float(jays_in[sw == w].mean()), float((sw == w).mean())]
                 for w in range(n + 1) if (sw == w).sum() >= 80},
    })

print(f"{'series':<28} {'opp':<10} {'exp':>5} {'need':>5} {'tgt':>4} {'win-swing':>10}")
tot_need = 0
for r in rows:
    tot_need += r["need"]
    tag = f"{'vs' if r['home'] else '@'} {r['opp']}"
    print(f"{r['start'][5:]}-{r['end'][5:]} {tag:<18} {r['opp_rec']:<10} "
          f"{r['exp']:5.2f} {r['need']:5.2f} {r['target']:4d} {r['swing_series']*100:9.1f}")
print(f"\nsum of E[wins|qualify] across series = {tot_need:.1f} of {sum(r['n'] for r in rows)}")
print(f"E[total wins | qualify] = {jays_wins[jays_in].mean():.1f}")
print(f"rest-of-season record needed for median cutline (83W): 24-15 (.615)")

# series records in qualifying seasons
sweeps = {}
for r in rows:
    sweeps[f"{r['start']}"] = r
srec = []
for s in series:
    sw = jays_won[s["ix"]].sum(axis=0)
    srec.append(sw)
srec = np.array(srec)
won_series_ct = (srec > np.array([[len(s["ix"])] for s in series]) / 2).sum(axis=0)
print(f"\nseries won (of {len(series)}): all sims {won_series_ct.mean():.1f} | qualifying sims {won_series_ct[jays_in].mean():.1f}")
dist_in = collections.Counter(won_series_ct[jays_in].tolist())
print("distribution of series won in qualifying seasons:",
      {k: round(v / jays_in.sum() * 100, 1) for k, v in sorted(dist_in.items())})

out = {
    "series_path": rows,
    "series_won_needed": float(won_series_ct[jays_in].mean()),
    "series_won_typical": float(won_series_ct.mean()),
    "n_series": len(series),
    "e_wins_if_qualify": float(jays_wins[jays_in].mean()),
    "ros_needed_w": int(round(83 - D.AL["Blue Jays"][0])),
    "ros_needed_l": int(rem["Blue Jays"] - round(83 - D.AL["Blue Jays"][0])),
    "series_won_dist_qualify": {int(k): float(v / jays_in.sum()) for k, v in sorted(dist_in.items())},
}
json.dump(out, open("path.json", "w"), indent=1)
