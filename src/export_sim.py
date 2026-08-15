"""Export the model (talent, schedule, series structure) for the in-browser simulator."""
import json
import data as D

exec(open("sim.py").read().split('with open("results.json"')[0])

AL_IDX = {t: i for i, t in enumerate(AL_TEAMS)}

gH, gA, gP, gJ = [], [], [], []      # home idx, away idx, P(home win), jays-game slot (-1 if none)
jays_game_slots = {}
slot = 0
for i, (date, a, h) in enumerate(games):
    hi = AL_IDX.get(h, -1)
    ai = AL_IDX.get(a, -1)
    gH.append(hi); gA.append(ai); gP.append(round(float(p_home[i]), 6))
    if JAYS in (a, h):
        gJ.append(slot)
        jays_game_slots[i] = slot
        slot += 1
    else:
        gJ.append(-1)

# series structure, aligned with analyze.py's `series`
PATH = json.load(open("path.json"))["series_path"]
ser = []
for si, s in enumerate(series):
    idxs = [jays_game_slots[jays_game_ix[k]] for k in s["ix"]]
    ser.append({
        "opp": s["opp"], "home": s["home"], "n": len(idxs),
        "start": s["start"], "end": s["end"],
        "slots": idxs,
        "need": round(PATH[si]["need"], 3),
        "exp": round(PATH[si]["exp"], 3),
        # is the Jays the home team in each game of this series?
        "jaysHome": [games[jays_game_ix[k]][2] == JAYS for k in s["ix"]],
    })

out = {
    "teams": AL_TEAMS,
    "abbr": ["TOR" if t == "Blue Jays" else
             {"Yankees": "NYY", "Red Sox": "BOS", "Rays": "TB", "Orioles": "BAL",
              "White Sox": "CWS", "Tigers": "DET", "Twins": "MIN", "Guardians": "CLE",
              "Royals": "KC", "Astros": "HOU", "Rangers": "TEX", "Mariners": "SEA",
              "Athletics": "ATH", "Angels": "LAA"}[t] for t in AL_TEAMS],
    "baseW": [D.AL[t][0] for t in AL_TEAMS],
    "baseL": [D.AL[t][1] for t in AL_TEAMS],
    "divs": [[AL_IDX[m] for m in mem] for mem in D.DIVISIONS.values()],
    "divNames": list(D.DIVISIONS),
    "gH": gH, "gA": gA, "gP": gP, "gJ": gJ,
    "series": ser,
    "jaysIdx": AL_IDX[JAYS],
    "nJaysGames": slot,
    "baselineOdds": float(jays_in.mean()),
}
json.dump(out, open("simdata.json", "w"), separators=(",", ":"))
print(f"games {len(gH)}  jays games {slot}  series {len(ser)}")
print(f"simdata.json {len(json.dumps(out, separators=(',',':')))/1024:.1f} KB")
print(f"python baseline odds {out['baselineOdds']*100:.2f}%")
