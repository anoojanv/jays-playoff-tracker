"""Render the Blue Jays playoff tracker from simulation output."""
import json, datetime, html

R = json.load(open("results.json"))
P = json.load(open("path.json"))
E = json.load(open("ensemble.json"))
import data as _D
EXT = _D.BREF or {}

JAYS = "Blue Jays"
ODDS = R["odds"]["playoff"]
LO, HI = E["lo"], E["hi"]
W, L = R["record"]["w"], R["record"]["l"]
GL = R["games_left"]
CUT = R["cut_wins"]["p50"]
PROJ = R["proj_wins"]["mean"]

# ---- every factual claim the prose makes, derived rather than typed ----
# These used to be literals ("12 of the 39 remaining games", "24-15", "83 wins", a whole
# sentence about a postponement) — true the day they were written, wrong every night
# after it. Anything asserted on the page is now computed from the current build.
CLUSTER = R.get("cluster", [])
CLUSTER_GAMES = R["cluster_games"]
CUT_TARGET = P["cut_target_w"]
ROS_W, ROS_L = P["ros_needed_w"], P["ros_needed_l"]

# run differential vs record, in whichever direction it actually points
_pyth_w = R["pythag_record"][JAYS][0]
_delta = W - _pyth_w
_deltas = {t: R["rivals"][t]["w"] - R["pythag_record"][t][0] for t in R["pythag_record"]}
_superlative = (" — the largest overperformance in the league"
                if _delta > 0 and _delta >= max(_deltas.values()) - 1e-9 else "")
if abs(_delta) < 0.5:
    pythag_note = ("Toronto's record is almost exactly what their run differential "
                   "supports, so the gap is a matter of field construction rather than "
                   "of how the Jays themselves are rated.")
else:
    pythag_note = (f"Toronto has won about {abs(_delta):.0f} "
                   f"{'more' if _delta > 0 else 'fewer'} games than their run differential "
                   f"supports{_superlative}, and this model leans harder on run "
                   f"differential than theirs does.")

# a hand-added makeup game is a thumb on the scale; say so on the page
if _D.SYNTHETIC:
    _sg = "; ".join(f"{a} at {h} on {datetime.date.fromisoformat(d).strftime('%b %-d')}"
                    for d, a, h in _D.SYNTHETIC)
    synthetic_note = (f" <b>One caveat:</b> {len(_D.SYNTHETIC)} makeup "
                      f"game{'s' if len(_D.SYNTHETIC) > 1 else ''} not yet on MLB's "
                      f"calendar {'were' if len(_D.SYNTHETIC) > 1 else 'was'} added by "
                      f"hand so the schedule reconciles to 162 ({_sg}).")
else:
    synthetic_note = ""

# ---- palette (validated: see validate_palette.js runs) ----
C = dict(
    # Blue Jays light theme. Roles: BLUE = data marks, RED = attention (the live
    # scenario, must-see games, the rival that matters most), NAVY = structural
    # reference rules and primary ink. All validated on the white card surface:
    #   blue/red categorical pair -> CVD worst-pair dE 21.8, normal-vision 35.7
    #   leverage ramp -> monotone L, adjacent dL >= .06, light end 2.28:1 vs white
    page="#EAF1FA", surf="#FFFFFF", card="#FFFFFF", card2="#EDF3FB",
    brand="#134A8E",          # Blue Jays royal - header block, section headings
    blue="#1C5FAD",           # data marks (royal, stepped into the light-mode band)
    red="#E8291C",            # Blue Jays red - attention
    navy="#16264B",           # deep navy - primary ink + static reference rules
    ink="#16264B", ink2="#4A5C7A",
    mute="#5F7290",           # 4.89:1 on white - small uppercase labels must clear AA
    redtext="#DA2115",        # 4.99:1 - brand red is 4.41:1, too low for 11px text
    grid="#E3EBF6", axis="#C3D2E6",
    ramp=["#0F4283", "#1F569B", "#3676C1", "#5A94D6", "#7FB0E2"],   # dark -> light
    good="#157F3C", warn="#B07500", crit="#E8291C",
    scen="#E8291C",           # the user's live scenario marker
)


DATE = datetime.date.fromisoformat(R["as_of"])
STAMP = DATE.strftime("%A, %B %-d, %Y")

TEAM_ABBR = {"Blue Jays": "TOR", "Yankees": "NYY", "Red Sox": "BOS", "Rays": "TB",
             "Orioles": "BAL", "White Sox": "CWS", "Tigers": "DET", "Twins": "MIN",
             "Guardians": "CLE", "Royals": "KC", "Astros": "HOU", "Rangers": "TEX",
             "Mariners": "SEA", "Athletics": "ATH", "Angels": "LAA", "Reds": "CIN"}


def pct(x, d=1):
    return f"{x*100:.{d}f}%"


def ramp_for(v, lo, hi):
    """Map a leverage value onto the validated 5-step ordinal ramp (dark end = highest)."""
    if hi <= lo:
        return C["ramp"][2]
    t = (v - lo) / (hi - lo)
    return C["ramp"][::-1][min(4, int(t * 5))]


# ------------------------------------------------------------------ wild card race
# Who leads each division, and who is chasing, both read off the current standings.
# These were literals — a fixed {Rays, White Sox, Astros} and a fixed list of nine
# challengers — so the table silently went wrong the moment a division changed hands:
# a fallen leader would have been missing from the race entirely, and the new leader
# would still have been listed as a wild-card contender.
def _winpct(t):
    v = R["rivals"][t]
    return v["w"] / (v["w"] + v["l"])


div_leaders = {max(members, key=_winpct) for members in _D.DIVISIONS.values()}
_chasers = sorted((t for t in R["rivals"] if t not in div_leaders),
                  key=_winpct, reverse=True)
race_order = _chasers[:9]
if JAYS not in race_order:              # always show Toronto, however far back
    race_order = _chasers[:8] + [JAYS]
wc_rows = []
jays_pct = W / (W + L)
for t in race_order:
    v = R["rivals"][t]
    tp = v["w"] / (v["w"] + v["l"])
    gb = ((v["w"] - W) + (L - v["l"])) / 2
    wc_rows.append(dict(team=t, w=v["w"], l=v["l"], pct=tp, rd=v["rd"],
                        gl=v["games_left"], proj=v["proj_w"], odds=v["playoff"], gb=gb))
wc_rows.sort(key=lambda r: -r["pct"])
# the cut line sits after the 3rd wild card (top 3 non-division-leaders)
cut_after = 3

AL_ORDER = json.load(open("simdata.json"))["teams"]
wc_html = ""
for i, r in enumerate(wc_rows):
    ti = AL_ORDER.index(r["team"])
    if i == cut_after:
        wc_html += ('<tr class="cut"><td colspan="6" class="cutlab">'
                    '— wild card cut line —</td></tr>')
    g = r["gb"] + 0.0
    gbtxt = "—" if r["team"] == JAYS else ("0.0" if abs(g) < 0.05 else f"{g:+.1f}")
    rdcls = "rdpos" if r["rd"] > 0 else "rdneg"
    cls = "jays" if r["team"] == JAYS else ""
    wc_html += (
        f'<tr class="{cls}"><td class="tm">{r["team"]}</td>'
        f'<td style="text-align:right">{r["w"]}–{r["l"]}</td>'
        f'<td style="text-align:right" class="gb">{gbtxt}</td>'
        f'<td style="text-align:right" class="{rdcls}">{r["rd"]:+d}</td>'
        f'<td style="text-align:right" class="hide-s">{r["proj"]:.0f}</td>'
        f'<td><div class="oddsbar"><div class="obt"><div class="obf" '
        f'data-oddsbar="{ti}" style="width:{r["odds"]*100:.0f}%"></div></div>'
        f'<div class="obn" data-oddsnum="{ti}">{r["odds"]*100:.0f}%</div></div></td></tr>')

# ------------------------------------------------------------------ win curve
curve = {int(k): v for k, v in R["win_curve"].items()}
# The chart used to be clipped to a literal 76-88, which cut the curve off for any club
# outside that band. sim.py already bounds win_curve to the simulated 0.5-99.5 percentile
# range, so plot what it produced.
xs = sorted(curve)
ys = [curve[w][0] for w in xs]

CW, CH = 660, 250
PADL, PADR, PADT, PADB = 44, 14, 16, 34
_xspan = (xs[-1] - xs[0]) or 1          # a decided race can leave one bucket
px = lambda w: PADL + (w - xs[0]) / _xspan * (CW - PADL - PADR)
py = lambda p: PADT + (1 - p) * (CH - PADT - PADB)

pts = " ".join(f"{px(w):.1f},{py(p):.1f}" for w, p in zip(xs, ys))
area = f"{PADL},{py(0):.1f} " + pts + f" {px(xs[-1]):.1f},{py(0):.1f}"

curve_marks = []
for target, lab in [(R["wins_10"], "10%"), (R["wins_50"], "50%"), (R["wins_90"], "90%")]:
    if target and xs[0] <= target <= xs[-1]:
        curve_marks.append((target, curve[target][0], lab))

_w10, _w90 = R["wins_10"], R["wins_90"]
if _w10 in curve and _w90 in curve and _w90 > _w10:
    _p10, _p90 = curve[_w10][0], curve[_w90][0]
    curve_note = (
        f"The curve is steep exactly where Toronto sits. <b>{_w10} wins is a "
        f"{_p10*100:.0f}% proposition; {_w90} wins is a {_p90*100:.0f}% one.</b> "
        f"Every win in between is worth roughly "
        f"{(_p90-_p10)/(_w90-_w10)*100:.0f} points of playoff probability — which is why "
        f"the leverage numbers below are as large as they are.")
else:
    # no win total clears 10% (eliminated) or none falls short of 90% (clinched)
    curve_note = ("The race is settled: across the whole plausible range of final win "
                  "totals the answer barely moves, so no single game shifts it much.")

gridlines = ""
for gy in [0, .25, .5, .75, 1.0]:
    y = py(gy)
    gridlines += (f'<line x1="{PADL}" x2="{CW-PADR}" y1="{y:.1f}" y2="{y:.1f}" '
                  f'stroke="{C["grid"]}" stroke-width="1"/>'
                  f'<text x="{PADL-8}" y="{y+4:.1f}" text-anchor="end" font-size="10" '
                  f'fill="{C["mute"]}" style="font-variant-numeric:tabular-nums">{int(gy*100)}%</text>')

xticks = ""
for w in xs:
    if w % 2 == 0:
        xticks += (f'<text x="{px(w):.1f}" y="{CH-PADB+16}" text-anchor="middle" font-size="10" '
                   f'fill="{C["mute"]}" style="font-variant-numeric:tabular-nums">{w}</text>')

dots = ""
for w, p, lab in curve_marks:
    dots += (f'<circle cx="{px(w):.1f}" cy="{py(p):.1f}" r="5" fill="{C["blue"]}" '
             f'stroke="{C["surf"]}" stroke-width="2"/>'
             f'<text x="{px(w):.1f}" y="{py(p)-13:.1f}" text-anchor="middle" font-size="11" '
             f'font-weight="800" fill="{C["navy"]}" stroke="#FFFFFF" stroke-width="3.5" '
             f'paint-order="stroke" stroke-linejoin="round">{w}W</text>')

hover = ""
for w, p in zip(xs, ys):
    hover += (f'<rect x="{px(w)-13:.1f}" y="{PADT}" width="26" height="{CH-PADT-PADB}" '
              f'fill="transparent"><title>{w} wins → {pct(p)} chance of a playoff spot</title></rect>')

cutx = px(CUT) if xs[0] <= CUT <= xs[-1] else None
cutline = ""
if cutx:
    cutline = (f'<line x1="{cutx:.1f}" x2="{cutx:.1f}" y1="{PADT+26}" y2="{CH-PADB}" '
               f'stroke="{C["navy"]}" stroke-width="2"/>'
               f'<text x="{cutx-8:.1f}" y="{CH-PADB-8:.1f}" text-anchor="end" font-size="10" '
               f'font-weight="700" fill="{C["navy"]}" stroke="#FFFFFF" stroke-width="3.5" '
               f'paint-order="stroke" stroke-linejoin="round">MEDIAN CUT LINE {CUT:.0f}W</text>')

# ------------------------------------------------------------------ series roadmap
sp = P["series_path"]
sw_lo = min(s["swing_series"] for s in sp)
sw_hi = max(s["swing_series"] for s in sp)
series_rows = ""
for si, s_ in enumerate(sp):
    n = s_["n"]
    tgt = int(round(s_["need"]))
    loc = "vs" if s_["home"] else "@"
    d0 = datetime.date.fromisoformat(s_["start"]).strftime("%b %-d")
    d1 = datetime.date.fromisoformat(s_["end"]).strftime("%-d")
    col = ramp_for(s_["swing_series"], sw_lo, sw_hi)
    # once the race is decided every swing is identical, so guard the range
    bw = (8 + (s_["swing_series"] - sw_lo) / (sw_hi - sw_lo) * 92
          if sw_hi > sw_lo else 50)
    opp_ab = TEAM_ABBR.get(s_["opp"], s_["opp"])
    btns = ""
    for k in range(n, -1, -1):
        isreq = " req" if k == tgt else ""
        btns += (f'<button type="button" data-w="{k}" aria-pressed="false" class="pk{isreq}" '
                 f'title="Blue Jays go {k}\u2013{n-k} against {opp_ab}">{k}\u2013{n-k}</button>')
    series_rows += f"""
    <tr data-series="{si}">
      <td class="dt">{d0}\u2013{d1}</td>
      <td class="op"><span class="loc">{loc}</span> <b>{opp_ab}</b>
          <span class="rec">{s_['opp_rec']}</span></td>
      <td class="pkcell"><div class="pkg" role="group"
          aria-label="Set the Blue Jays result for the {opp_ab} series">{btns}</div></td>
      <td class="ex" style="color:{C['ink2']}">{s_['need']:.2f}</td>
      <td class="ex hide-s">{s_['exp']:.2f}</td>
      <td class="lv">
        <div class="lvwrap" title="Win this series \u2192 {pct(s_['p_in_if_win_series'])}. Lose it \u2192 {pct(s_['p_in_if_lose_series'])}.">
          <div class="lvbar" style="width:{bw:.0f}%;background:{col}"></div>
          <span class="lvnum">{s_['swing_series']*100:.1f}</span>
        </div>
      </td>
    </tr>"""

# ------------------------------------------------------------------ dependency
dep = R["dependency"]
dep_items = sorted(dep.items(), key=lambda x: -x[1]["swing"])[:6]
# zero once the race is decided — every rival swing collapses to nothing
dmax = max(abs(v["swing"]) for _, v in dep_items) or 1.0
dep_rows = ""
for i, (t, v) in enumerate(dep_items):
    wpx = abs(v["swing"]) / dmax * 100
    bar_col = C["red"] if i == 0 else C["blue"]      # emphasis: the one that matters most
    dep_rows += f"""
    <div class="deprow">
      <div class="depname">{TEAM_ABBR.get(t,t)}</div>
      <div class="deptrack">
        <div class="depbar" style="width:{wpx:.0f}%;background:{bar_col}" title="If {t} finish cold (~{v['cold_w']:.0f}W) the Jays are {pct(v['if_rival_cold'])}; if they finish hot (~{v['hot_w']:.0f}W), {pct(v['if_rival_hot'])}."></div>
      </div>
      <div class="depnum">{pct(v['if_rival_cold'],1)} <span class="arrow">↔</span> {pct(v['if_rival_hot'],1)}</div>
    </div>"""

# ------------------------------------------------------------------ must-see TV
lev = sorted(R["leverage"], key=lambda x: -x["leverage"])
seen, must_see = set(), []
for g in lev:
    key = (g["opp"], g["date"][:7])
    if len(must_see) >= 5:
        break
    if key in seen:
        continue
    seen.add(key)
    must_see.append(g)

def why_for(g):
    """Say why a game matters, using only facts true in THIS build.

    This was a hand-written lookup table keyed by opponent. It read better, but every
    entry asserted something that decays -- a run differential to the run ("+90"), a
    standings position, "the only time the Jays see them again", "the opener" -- and the
    page republishes nightly, so those claims went stale within days of being written.
    """
    opp = g["opp"]
    rv = R["rivals"].get(opp)
    later = sum(1 for x in R["leverage"] if x["opp"] == opp and x["date"] > g["date"])

    if rv:
        lead = (f"{opp} are {rv['w']}&ndash;{rv['l']} ({rv['rd']:+d} run differential), "
                f"{rv['playoff']*100:.0f}% to reach the playoffs.")
    else:                                    # an interleague opponent has no AL odds
        lead = f"{opp} are outside the AL field, so only Toronto's own win column moves."

    if later == 0:
        when = " This is the last time the Jays see them"
    else:
        when = f" {later} more meeting{'s' if later > 1 else ''} left"

    if opp in CLUSTER:
        stake = ", and every win here passes them directly in the wild-card race."
    elif rv and rv["playoff"] > 0.5:
        stake = ", and they are on track to take one of the spots Toronto wants."
    else:
        stake = ", so this is about Toronto's win total more than the head-to-head."
    return lead + when + stake
mustsee_rows = ""
for i, g in enumerate(must_see):
    d = datetime.date.fromisoformat(g["date"])
    loc = "vs" if g["home"] else "@"
    mustsee_rows += f"""
    <div class="mstile">
      <div class="msrank">{i+1}</div>
      <div class="msbody">
        <div class="msdate">{d.strftime('%a %b %-d')}</div>
        <div class="msmatch">{loc} {g['opp']}</div>
        <div class="mswhy">{why_for(g)}</div>
      </div>
      <div class="msswing"><b>±{g['leverage']*100:.1f}</b><span>pts of<br>playoff odds</span></div>
    </div>"""

# ------------------------------------------------------------------ ensemble strip
ens = sorted(E["scenarios"], key=lambda s: s["odds"])
ens_rows = ""
for s in ens:
    x = (s["odds"] - 0.05) / (0.14 - 0.05) * 100
    prim = "primary" in s["label"]
    ens_rows += (f'<div class="ensrow"><div class="enslab">{html.escape(s["label"].replace(" - primary model",""))}'
                 f'{" <em>◂ primary</em>" if prim else ""}</div>'
                 f'<div class="enstrack"><div class="ensdot{" p" if prim else ""}" style="left:{x:.1f}%"></div></div>'
                 f'<div class="ensval">{pct(s["odds"])}</div></div>')

SIM = json.load(open("simdata.json"))
SIM["curveX0"], SIM["curveX1"] = round(px(xs[0]), 2), round(px(xs[-1]), 2)
SIM["curveW0"], SIM["curveW1"] = xs[0], xs[-1]
SIM["rosNeededW"] = P["ros_needed_w"]
SIM["projWins"] = round(PROJ, 2)
SIM["seriesNeeded"] = int(round(P["series_won_needed"]))
SIMJSON = json.dumps(SIM, separators=(",", ":"))
APPJS = open("app.js").read()

# comparison odds are best-effort: hide the pill entirely if the scrape failed
if EXT and EXT.get("odds"):
    _d = EXT.get("date")
    _dtxt = datetime.date.fromisoformat(_d).strftime("%b %-d") if _d else "latest"
    bref_pill = f'<div class="pill">Baseball-Reference: {EXT["odds"]}% ({_dtxt})</div>'
    bref_note_open = ("<b>Why this differs from Baseball-Reference's "
                      f"{EXT['odds']}%:</b>")
else:
    bref_pill = ""
    bref_note_open = "<b>On the gap with other public models:</b>"

series_won = P["series_won_needed"]
# games back of the third wild card (the first team below the cut line is index cut_after-1)
wc3 = wc_rows[cut_after - 1]
gb_wc3 = wc3["gb"] if wc3["team"] != JAYS else 0.0

# how many series can still be lost — read off the simulated qualifying seasons rather
# than asserted ("Must not lose more than 4 series" was a literal)
_dist = {int(k): v for k, v in P["series_won_dist_qualify"].items()}
_cum, series_floor = 0.0, P["n_series"]
for _k in sorted(_dist):
    _cum += _dist[_k]
    if _cum >= 0.10:
        series_floor = _k
        break
series_pill = (f"Qualifies winning fewer than {series_floor} of {P['n_series']} series "
               f"less than 10% of the time")

# ---- three numbers the model already computed but the page never showed ----
ELIM = R["elimination_number"]
elim_note = (f"The {ELIM}{'st' if ELIM % 10 == 1 and ELIM != 11 else 'nd' if ELIM % 10 == 2 and ELIM != 12 else 'rd' if ELIM % 10 == 3 and ELIM != 13 else 'th'} "
             f"loss from here leaves Toronto short of the {CUT_TARGET}-win median cut "
             f"line — {max(0, ELIM - 1)} to spare across {GL} games.")

# the next stretch, at the pace the rest of the season actually demands
NEXT = {int(k): v for k, v in R["next12"].items()}
NEXT_N = R["next_n"]
if NEXT:
    _want = int(round(ROS_W / GL * NEXT_N)) if GL else 0
    _pace = min(NEXT, key=lambda w: (abs(w - _want), -w))   # nearest total we sampled
    _better = min((w for w in NEXT if w > _pace), default=None)
    next_v = f"{_pace}&ndash;{NEXT_N - _pace}"
    next_note = f"Matching the required pace holds the odds at {pct(NEXT[_pace][0])}."
    if _better is not None:
        next_note += f" Going {_better}&ndash;{NEXT_N - _better} instead: {pct(NEXT[_better][0])}."
else:
    next_v, next_note = "&mdash;", "Fewer games remain than this window needs."

# how much of the chase is passing people rather than just winning
PASS_N = len(CLUSTER)
pass_v = f"{R['pass_given_in']:.1f} of {PASS_N}"
pass_note = (f"Clubs in the {', '.join(CLUSTER)} cluster that Toronto finishes ahead of, "
             f"averaged over the seasons where they qualify.")

# ---- the three notes that used to assert last week's facts ----
_spread = HI - LO
ens_verdict = ("That is a narrow band — the number is coming from the standings and the "
               "schedule, not from a modelling choice."
               if _spread <= 0.06 else
               "That is a wide band — how much you trust run differential over raw "
               "W&ndash;L genuinely changes the answer.")

_dep_team, _dep = max(R["dependency"].items(), key=lambda kv: abs(kv[1]["swing"]))
_dep_games = sum(s["n"] for s in R["series"] if s["opp"] == _dep_team)
dep_note = (f"<b>{_dep_team} are the single most important other club</b> for Toronto — "
            f"a {abs(_dep['swing'])*100:.1f}-point swing between a cold and a hot finish"
            + (f", and the two meet {_dep_games} more time"
               f"{'s' if _dep_games != 1 else ''} this season."
               if _dep_games else ", though they do not meet again."))

_leaders_txt = ", ".join(TEAM_ABBR.get(t, t)
                         for t in sorted(div_leaders, key=_winpct, reverse=True))


def _ordinal(n):
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


# where Toronto actually sits in its own division — the header said "4th AL East" flat
_own_div = next(d for d, members in _D.DIVISIONS.items() if JAYS in members)
_div_rank = sorted(_D.DIVISIONS[_own_div], key=_winpct, reverse=True).index(JAYS) + 1
div_pos = f"{_ordinal(_div_rank)} {_own_div}"

# ---- header mark ----------------------------------------------------------------
# An original monogram, not the club's logo: the Blue Jays' marks belong to the team and
# to MLB, and this page carries a "not affiliated" notice. Same construction as the
# favicon so the tab and the header agree. Inline because verify() forbids any external
# reference — swap the paths for your own artwork if you want, but keep it inline.
LOGO = (
    '<svg class="logo" viewBox="0 0 64 64" role="img" aria-label="Blue Jays playoff '
    'tracker mark" focusable="false">'
    '<rect width="64" height="64" rx="15" fill="#0B1A33"/>'
    '<path d="M15 45V19h12a6.3 6.3 0 010 12.6H15" stroke="#4691E8" stroke-width="5.2" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M27 31.6a6.3 6.3 0 010 12.6H15" stroke="#4691E8" stroke-width="5.2" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M38 19l6.5 24L51 19" stroke="#E8555F" stroke-width="5.2" fill="none" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>')

# ---- section navigation ----------------------------------------------------------
SECTIONS = [("play", "Play it out"), ("takes", "What it takes"), ("race", "WC race"),
            ("curve", "Wins needed"), ("roadmap", "Road map"),
            ("watch", "Scoreboard"), ("calendar", "Calendar")]
if _D.INJURIES:
    SECTIONS.append(("injuries", "Injuries"))
nav_html = "".join(f'<a href="#{sid}">{html.escape(lab)}</a>' for sid, lab in SECTIONS)

# ---- injuries --------------------------------------------------------------------
_inj_rows = ""
for p in _D.INJURIES:
    if p.get("note"):
        ret, cls = html.escape(p["note"]), "reported"
    elif p.get("eligible"):
        _d = datetime.date.fromisoformat(p["eligible"])
        _back = (_d - DATE).days
        ret = (f"{_d.strftime('%b %-d')}"
               + (f" &middot; {_back}d" if 0 < _back <= 60 else ""))
        cls = "elig"
    else:
        ret, cls = "not yet set", "unknown"
    _inj_rows += (
        f'<tr><td class="ip">{html.escape(p["name"])}'
        f'<span class="ipos">{html.escape(p.get("pos") or "")}</span></td>'
        f'<td class="ist">{html.escape(p.get("status") or "")}</td>'
        f'<td class="iret {cls}">{ret}</td></tr>')

# ---- must-see calendar -----------------------------------------------------------
# The remaining schedule as month grids, shaded by how much each game moves the odds,
# with the five biggest circled. Replaces a flat top-five list: same information, plus
# every other game around it, which is what a run-in actually looks like.
_lev = R["leverage"]
_lv = [g["leverage"] for g in _lev] or [0.0]
_lmin, _lmax = min(_lv), max(_lv)
_top5 = {(g["date"], g["opp"]) for g in sorted(_lev, key=lambda x: -x["leverage"])[:5]}
_by_date = {}
for g in _lev:
    _by_date.setdefault(g["date"], []).append(g)


def _ramp_ix(v):
    if _lmax <= _lmin:
        return 2
    return min(4, int((v - _lmin) / (_lmax - _lmin) * 5))


ramp_legend = "".join(f'<span style="background:{c}"></span>'
                        for c in C["ramp"][::-1])

cal_html = ""
if _by_date:
    _first = datetime.date.fromisoformat(min(_by_date))
    _last = datetime.date.fromisoformat(max(_by_date))
    _m = datetime.date(_first.year, _first.month, 1)
    while _m <= _last:
        _nxt = datetime.date(_m.year + (_m.month == 12), _m.month % 12 + 1, 1)
        cells = ""
        lead = (datetime.date(_m.year, _m.month, 1).weekday() + 1) % 7   # Sunday-first
        cells += '<div class="cday out"></div>' * lead
        d = datetime.date(_m.year, _m.month, 1)
        while d < _nxt:
            key = d.isoformat()
            gs = _by_date.get(key)
            if not gs:
                cells += f'<div class="cday off"><i>{d.day}</i></div>'
            else:
                g = max(gs, key=lambda x: x["leverage"])
                ix = _ramp_ix(g["leverage"])
                bg = C["ramp"][::-1][ix]
                star = (key, g["opp"]) in _top5
                cells += (
                    f'<div class="cday game{" key" if star else ""}" '
                    f'style="background:{bg};color:{"#fff" if ix >= 2 else C["navy"]}" '
                    f'title="{"vs" if g["home"] else "at"} {html.escape(g["opp"])} '
                    f'&middot; {g["leverage"]*100:.1f} pts of playoff odds">'
                    f'<i>{d.day}</i><b>{"" if g["home"] else "@"}'
                    f'{html.escape(TEAM_ABBR.get(g["opp"], g["opp"][:3].upper()))}</b></div>')
            d += datetime.timedelta(days=1)
        cal_html += (f'<div class="cmon"><div class="cmname">'
                     f'{_m.strftime("%B %Y")}</div><div class="cgrid">'
                     + "".join(f'<div class="cdow">{x}</div>' for x in "SMTWTFS")
                     + cells + '</div></div>')
        _m = _nxt

injuries_section = (f'''<div class="card" id="injuries" style="margin-top:14px">
  <h2>Injury report <span class="sub">&mdash; {len(_D.INJURIES)} on the injured list</span></h2>
  <table class="injt">
    <thead><tr><th>Player</th><th>Status</th><th style="text-align:right">Earliest return</th></tr></thead>
    <tbody>{_inj_rows}</tbody>
  </table>
  <div class="note">Status comes from the club\'s roster feed. <b>Earliest return</b> is the
    first date the injured list allows, not a projection — a player can miss well past it.
    Dates in red are reported timelines entered by hand.</div>
</div>''' if _D.INJURIES else "")

HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blue Jays Playoff Tracker — {DATE.strftime('%b %-d, %Y')}</title>
<meta name="robots" content="noindex,nofollow">
<meta name="data-fingerprint" content="{_D.FINGERPRINT}">
<meta name="theme-color" content="{C['brand']}">
<meta name="description" content="Toronto {W}–{L}. {ODDS*100:.1f}% to reach the playoffs. What it takes: {P['ros_needed_w']}–{P['ros_needed_l']} the rest of the way, {series_won:.0f} of {P['n_series']} remaining series. Updated {DATE.strftime('%b %-d')}.">
<meta property="og:type" content="website">
<meta property="og:title" content="Blue Jays Playoff Tracker — {ODDS*100:.1f}%">
<meta property="og:description" content="Toronto {W}–{L}, {abs(gb_wc3):.1f} back of the third wild card. Needs {P['ros_needed_w']}–{P['ros_needed_l']} to reach the {CUT:.0f}-win cut line. {R['nsim']:,} simulated seasons, updated {DATE.strftime('%b %-d')}.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%230B1A33'/%3E%3Cpath d='M7 22V10h6a3.2 3.2 0 010 6.4H7' stroke='%234691E8' stroke-width='2.6' fill='none' stroke-linecap='round'/%3E%3Cpath d='M13 16.4a3.2 3.2 0 010 6.4H7' stroke='%234691E8' stroke-width='2.6' fill='none' stroke-linecap='round'/%3E%3Cpath d='M19 10l3.5 12L26 10' stroke='%23E8555F' stroke-width='2.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{C['page']};color:{C['ink']};
 font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
 padding:18px;line-height:1.45;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1120px;margin:0 auto}}
.card{{background:{C['card']};border:1px solid rgba(19,74,142,.13);border-radius:14px;
 padding:18px 20px;box-shadow:0 1px 2px rgba(19,74,142,.05),0 2px 10px rgba(19,74,142,.04)}}
h2{{font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:{C['brand']};
 font-weight:800;margin-bottom:14px}}
.sub{{font-size:12px;color:{C['ink2']};font-weight:400;letter-spacing:0;text-transform:none}}

/* header - the brand block */
.hdr{{background:{C['brand']};border-radius:14px;padding:22px 26px;
 display:flex;align-items:center;gap:20px;margin-bottom:14px;position:relative;
 overflow:hidden;box-shadow:0 2px 14px rgba(19,74,142,.22)}}
.hdr:before{{content:"";position:absolute;left:0;top:0;bottom:0;width:7px;
 background:{C['red']}}}
.hdr h1{{font-size:27px;font-weight:800;letter-spacing:-.02em;line-height:1.1;color:#fff}}
.hdr h1 span{{color:#fff;background:{C['red']};padding:0 8px;border-radius:5px;
 margin:0 2px}}
.hdr .stamp{{font-size:12px;color:rgba(255,255,255,.74);margin-top:6px}}
.hdr .rec{{margin-left:auto;text-align:right;color:#fff}}
.hdr .rec b{{font-size:32px;font-weight:800;letter-spacing:-.02em}}
.hdr .rec div{{font-size:11px;color:rgba(255,255,255,.72);letter-spacing:.08em;
 text-transform:uppercase}}

/* ---- the control panel: this is the thing you touch, so it gets its own language.
   Blue = model data. RED = your input. Nothing red on this page is a readout. ---- */
.panel{{background:{C['card']};border:2px solid {C['red']};border-radius:16px;
 padding:18px 22px 20px;margin-bottom:14px;
 box-shadow:0 2px 4px rgba(19,74,142,.06),0 6px 22px rgba(232,41,28,.10)}}
.pnhead{{display:flex;align-items:center;gap:10px;margin-bottom:4px}}
.pnhead h2{{margin-bottom:0;color:{C['redtext']}}}
.livetag{{font-size:9.5px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
 color:#fff;background:{C['redtext']};padding:3px 8px;border-radius:20px}}
.pnbody{{display:grid;grid-template-columns:250px 1fr;gap:26px;align-items:start;
 margin-top:14px}}
.pnodds{{border-right:1px solid {C['grid']};padding-right:22px}}
.big{{font-size:64px;font-weight:800;letter-spacing:-.035em;line-height:1;
 color:{C['brand']};font-variant-numeric:proportional-nums}}
.big small{{font-size:25px;font-weight:700}}
.oddscap{{font-size:11px;color:{C['mute']};letter-spacing:.04em;margin-top:2px}}
.meter{{height:8px;border-radius:4px;background:{C['card2']};overflow:hidden;margin:12px 0 8px}}
.mfill{{height:100%;border-radius:4px;background:{C['brand']};width:0;
 transition:width .4s cubic-bezier(.2,.7,.3,1)}}
.livedelta{{font-size:11.5px;color:{C['mute']};min-height:17px;line-height:1.35}}
.livedelta.up{{color:{C['good']};font-weight:700}}
.livedelta.down{{color:{C['redtext']};font-weight:700}}

.sldtop{{display:flex;align-items:baseline;justify-content:space-between;gap:12px}}
.sldval{{font-size:30px;font-weight:800;letter-spacing:-.02em;color:{C['redtext']};
 font-variant-numeric:tabular-nums}}
.sldcap{{font-size:11px;color:{C['mute']};letter-spacing:.05em;text-transform:uppercase;
 font-weight:700;margin-left:7px}}
.sldpace{{font-size:11.5px;color:{C['ink2']}}}
.sldwrap{{position:relative;margin:6px 0 30px}}

/* the slider itself - deliberately oversized so it reads as a control at a glance */
input[type=range].sld{{-webkit-appearance:none;appearance:none;width:100%;height:34px;
 background:transparent;cursor:pointer;display:block;margin:0}}
input[type=range].sld:focus{{outline:none}}
input[type=range].sld::-webkit-slider-runnable-track{{height:14px;border-radius:7px;
 border:1px solid rgba(19,74,142,.2);
 background:linear-gradient(90deg,{C['red']} 0%,{C['red']} var(--fill,50%),
  {C['card2']} var(--fill,50%),{C['card2']} 100%)}}
input[type=range].sld::-webkit-slider-thumb{{-webkit-appearance:none;appearance:none;
 width:32px;height:32px;border-radius:50%;background:{C['red']};border:4px solid #fff;
 box-shadow:0 2px 8px rgba(19,74,142,.4);margin-top:-10px}}
input[type=range].sld:focus-visible::-webkit-slider-thumb{{box-shadow:0 0 0 4px rgba(232,41,28,.3)}}
input[type=range].sld::-moz-range-track{{height:14px;border-radius:7px;background:{C['card2']};
 border:1px solid rgba(19,74,142,.2)}}
input[type=range].sld::-moz-range-progress{{height:14px;border-radius:7px;background:{C['red']}}}
input[type=range].sld::-moz-range-thumb{{width:28px;height:28px;border-radius:50%;
 background:{C['red']};border:4px solid #fff;box-shadow:0 2px 8px rgba(19,74,142,.4)}}
.sldticks{{position:relative;height:14px;margin-top:-2px}}
.tick{{position:absolute;transform:translateX(-50%);font-size:10px;color:{C['mute']};
 white-space:nowrap;padding-top:8px}}
.tick i{{position:absolute;top:0;left:50%;width:1px;height:6px;background:{C['axis']}}}
.tick.need{{color:{C['brand']};font-weight:800}}
.tick.need i{{background:{C['brand']};width:2px;height:9px}}
.tick.end{{transform:translateX(-100%)}}
.tick.end i{{left:auto;right:0}}
.tick.start{{transform:none}}
.tick.start i{{left:0}}

.pnread{{display:flex;flex-wrap:wrap;align-items:flex-end;gap:22px;margin-top:16px;
 padding-top:14px;border-top:1px solid {C['grid']}}}
.sv{{display:block;font-size:22px;font-weight:800;letter-spacing:-.02em;color:{C['navy']};
 font-variant-numeric:tabular-nums}}
.sl{{display:block;font-size:10px;letter-spacing:.07em;text-transform:uppercase;
 color:{C['mute']};margin-top:2px}}
.perf{{margin-left:auto;font-size:10px;color:{C['mute']};font-variant-numeric:tabular-nums}}

.range{{margin-top:4px}}
.rtrack{{height:8px;border-radius:4px;background:{C['card2']};position:relative;margin:7px 0 6px}}
.rfill{{position:absolute;height:100%;border-radius:4px;background:{C['blue']};opacity:.4}}
.rtick{{position:absolute;top:-4px;width:3px;height:16px;border-radius:2px;background:{C['brand']}}}
.rlab{{display:flex;justify-content:space-between;font-size:10.5px;color:{C['mute']};
 font-variant-numeric:tabular-nums}}
.statv{{font-size:40px;font-weight:800;letter-spacing:-.03em;line-height:1.05;color:{C['navy']}}}
.statl{{font-size:11.5px;color:{C['ink2']};margin-top:7px}}
html{{scroll-behavior:smooth}}
.logo{{width:46px;height:46px;flex:none;border-radius:11px;
 box-shadow:0 1px 6px rgba(0,0,0,.28)}}
.hdrid{{display:flex;align-items:center;gap:15px}}

/* ---- section nav: sticky, so the page is navigable once it gets long ---- */
.snav{{position:sticky;top:0;z-index:30;display:flex;gap:6px;overflow-x:auto;
 background:rgba(234,241,250,.93);backdrop-filter:blur(8px);
 padding:9px 2px;margin-bottom:14px;border-bottom:1px solid {C['grid']};
 scrollbar-width:none}}
.snav::-webkit-scrollbar{{display:none}}
.snav a{{flex:none;font-size:11.5px;font-weight:700;letter-spacing:.01em;
 color:{C['brand']};background:{C['surf']};border:1px solid {C['axis']};
 border-radius:999px;padding:6px 12px;text-decoration:none;white-space:nowrap;
 transition:background .15s,color .15s,border-color .15s}}
.snav a:hover,.snav a:focus-visible{{background:{C['brand']};color:#fff;
 border-color:{C['brand']};outline:none}}
[id]{{scroll-margin-top:62px}}

/* ---- injuries ---- */
.injt{{width:100%;border-collapse:collapse;margin-top:4px}}
.injt th{{font-size:10px;text-transform:uppercase;letter-spacing:.07em;
 color:{C['mute']};text-align:left;font-weight:700;padding:0 8px 7px 0;
 border-bottom:1px solid {C['grid']}}}
.injt td{{padding:9px 8px 9px 0;border-bottom:1px solid {C['grid']};
 font-size:13px;vertical-align:baseline}}
.injt tr:last-child td{{border-bottom:none}}
.ip{{font-weight:700;color:{C['navy']}}}
.ipos{{font-size:10px;font-weight:700;color:{C['mute']};margin-left:7px;
 letter-spacing:.06em}}
.ist{{color:{C['ink2']};font-size:12px}}
.iret{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;
 font-weight:700;font-size:12px}}
.iret.elig{{color:{C['brand']}}}
.iret.reported{{color:{C['redtext']};font-weight:600;white-space:normal;
 text-align:right;max-width:190px}}
.iret.unknown{{color:{C['mute']};font-weight:600}}

/* ---- schedule calendar ---- */
.cwrap{{display:flex;gap:16px;flex-wrap:wrap;margin-top:4px}}
.cmon{{flex:1 1 260px;min-width:236px}}
.cmname{{font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
 color:{C['mute']};margin-bottom:7px}}
.cgrid{{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}}
.cdow{{font-size:9px;font-weight:700;color:{C['axis']};text-align:center;
 padding-bottom:2px}}
.cday{{aspect-ratio:1;border-radius:6px;position:relative;overflow:hidden;
 display:flex;flex-direction:column;align-items:center;justify-content:center}}
.cday.out{{background:transparent}}
.cday.off{{background:{C['card2']}}}
.cday i{{position:absolute;top:2px;left:4px;font-style:normal;font-size:8.5px;
 font-weight:700;opacity:.62;font-variant-numeric:tabular-nums}}
.cday.off i{{color:{C['axis']};opacity:1}}
.cday b{{font-size:10.5px;font-weight:800;letter-spacing:-.02em;margin-top:5px}}
.cday.key{{box-shadow:inset 0 0 0 2.5px {C['red']}}}
.cleg{{display:flex;align-items:center;gap:9px;margin-top:12px;flex-wrap:wrap;
 font-size:10.5px;color:{C['mute']}}}
.clramp{{display:flex;gap:2px}}
.clramp span{{width:17px;height:9px;border-radius:2px}}
.clkey{{width:11px;height:11px;border-radius:3px;
 box-shadow:inset 0 0 0 2.5px {C['red']};background:{C['card2']}}}
@media(max-width:560px){{.cmon{{flex:1 1 100%}} .snav a{{font-size:11px;padding:5px 10px}}}}
.facts{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:13px}}
.fact{{background:{C['card2']};border-radius:8px;padding:10px 11px}}
.factv{{font-size:19px;font-weight:800;color:{C['navy']};line-height:1.1;
 font-variant-numeric:tabular-nums}}
.factl{{font-size:10px;color:{C['mute']};text-transform:uppercase;letter-spacing:.04em;
 font-weight:700;margin-top:5px}}
.factn{{font-size:11px;color:{C['ink2']};margin-top:6px;line-height:1.38}}
@media(max-width:560px){{.facts{{grid-template-columns:1fr}}}}
.pill{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.08em;
 text-transform:uppercase;padding:4px 9px;border-radius:20px;background:{C['card2']};
 color:{C['brand']};margin-top:10px}}

.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}}
.grid2b{{display:grid;grid-template-columns:1.15fr .85fr;gap:14px;margin-bottom:14px;
 align-items:start}}

/* table */
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:{C['mute']};
 text-align:left;font-weight:700;padding:0 6px 8px}}
td{{padding:7px 6px;border-top:1px solid {C['grid']};font-variant-numeric:tabular-nums}}
tr.jays td{{background:rgba(28,95,173,.09)}}
tr.jays td:first-child{{box-shadow:inset 3px 0 0 {C['brand']}}}
tr.cut td{{border-bottom:2px solid {C['navy']}}}
.cutlab{{font-size:9.5px;letter-spacing:.1em;color:{C['navy']};font-weight:800;
 text-transform:uppercase;padding:4px 6px 1px}}
.tm{{font-weight:700;color:{C['navy']}}}
.gb{{color:{C['ink2']}}}
.oddsbar{{display:flex;align-items:center;gap:7px}}
.obt{{flex:1;height:6px;border-radius:3px;background:{C['card2']};overflow:hidden;min-width:40px}}
.obf{{height:100%;border-radius:3px;background:{C['blue']};transition:width .4s}}
.obn{{width:38px;text-align:right;font-size:11.5px;color:{C['ink2']}}}
.rdpos{{color:{C['good']};font-weight:600}} .rdneg{{color:{C['redtext']};font-weight:600}}

/* series */
td.dt{{color:{C['ink2']};white-space:nowrap;font-size:11.5px}}
td.op{{white-space:nowrap;color:{C['navy']}}}
.loc{{color:{C['mute']};font-size:11px}}
.rec{{color:{C['mute']};font-size:11px;margin-left:3px}}
.badge{{display:inline-block;min-width:44px;text-align:center;padding:2px 7px;border-radius:5px;
 font-size:11px;font-weight:800;letter-spacing:.02em}}
td.ex{{color:{C['mute']};text-align:right;width:44px}}
.lvwrap{{display:flex;align-items:center;gap:8px}}
.lvbar{{height:7px;border-radius:4px}}
.lvnum{{font-size:11px;color:{C['ink2']};width:26px}}

/* dependency */
.deprow{{display:flex;align-items:center;gap:10px;margin-bottom:9px}}
.depname{{width:36px;font-weight:800;font-size:12px;color:{C['navy']}}}
.deptrack{{flex:1;height:8px;background:{C['card2']};border-radius:4px;overflow:hidden}}
.depbar{{height:100%;border-radius:4px}}
.depnum{{font-size:11px;color:{C['ink2']};width:104px;text-align:right;
 font-variant-numeric:tabular-nums}}
.arrow{{color:{C['mute']}}}

/* ensemble */
.ensrow{{display:flex;align-items:center;gap:10px;margin-bottom:7px;font-size:11.5px}}
.enslab{{width:250px;color:{C['ink2']}}}
.enslab em{{color:{C['brand']};font-style:normal;font-weight:700;font-size:10px}}
.enstrack{{flex:1;height:2px;background:{C['grid']};position:relative}}
.ensdot{{position:absolute;top:-4px;width:10px;height:10px;border-radius:50%;
 background:{C['mute']};margin-left:-5px;border:2px solid {C['card']}}}
.ensdot.p{{background:{C['brand']};width:14px;height:14px;top:-6px;margin-left:-7px}}
.ensval{{width:44px;text-align:right;font-variant-numeric:tabular-nums;color:{C['navy']};
 font-weight:600}}

/* must see */
.ms{{background:{C['card']};border:1px solid rgba(232,41,28,.28);border-radius:14px;
 padding:18px 20px;position:relative;overflow:hidden;
 box-shadow:0 1px 2px rgba(19,74,142,.05),0 2px 10px rgba(19,74,142,.04)}}
.ms:before{{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:{C['red']}}}
.ms h2{{color:{C['redtext']}}}
.mstile{{display:flex;align-items:center;gap:14px;padding:11px 0;
 border-top:1px solid {C['grid']}}}
.mstile:first-of-type{{border-top:none}}
.msrank{{width:26px;height:26px;flex:none;border-radius:7px;background:{C['red']};
 color:#fff;font-weight:800;font-size:13px;display:flex;align-items:center;
 justify-content:center}}
.msbody{{flex:1}}
.msdate{{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:{C['mute']};
 font-weight:700}}
.msmatch{{font-size:16px;font-weight:800;letter-spacing:-.01em;margin:1px 0 3px;
 color:{C['navy']}}}
.mswhy{{font-size:11.5px;color:{C['ink2']};line-height:1.4}}
.msswing{{text-align:right;flex:none;width:78px}}
.msswing b{{font-size:20px;font-weight:800;color:{C['red']};letter-spacing:-.02em}}
.hint b{{color:{C['redtext']}}}
.msswing span{{display:block;font-size:9px;color:{C['mute']};letter-spacing:.05em;
 text-transform:uppercase;line-height:1.3;margin-top:2px}}

.note{{font-size:10.5px;color:{C['ink2']};line-height:1.65;margin-top:14px}}
.note b{{color:{C['navy']}}}
details summary{{cursor:pointer;font-size:11px;color:{C['brand']};margin-top:10px;
 font-weight:600}}
details table{{margin-top:8px;font-size:11px}}
.tscroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
/* grid children default to min-width:auto, which lets wide tables stretch the track
   instead of scrolling inside it. This is what makes .tscroll actually work. */
.hero>*,.grid2>*,.grid2b>*,.pnbody>*{{min-width:0}}

/* live odds meter + delta */
.meter{{height:7px;border-radius:4px;background:{C['card2']};overflow:hidden;margin:12px 0 9px}}
.mfill{{height:100%;border-radius:4px;background:{C['brand']};width:0;
 transition:width .42s cubic-bezier(.2,.7,.3,1)}}
.livedelta{{font-size:11.5px;color:{C['mute']};min-height:17px;transition:color .3s}}
.livedelta.up{{color:{C['good']};font-weight:700}}
.livedelta.down{{color:{C['redtext']};font-weight:700}}
.scenrow{{display:flex;gap:22px;margin-top:14px}}
.sv{{display:block;font-size:22px;font-weight:800;letter-spacing:-.02em;color:{C['navy']};
 font-variant-numeric:tabular-nums}}
.sl{{display:block;font-size:10px;letter-spacing:.08em;text-transform:uppercase;
 color:{C['mute']};margin-top:2px}}
.card.scen{{border-color:rgba(232,41,28,.3)}}

/* series picker - buttons must not look like the data badges that used to sit here */
.presets{{display:flex;flex-wrap:wrap;gap:7px;margin-top:2px}}
.ps{{font:inherit;font-size:11.5px;font-weight:700;color:{C['brand']};background:#fff;
 border:1.5px solid rgba(19,74,142,.28);border-radius:20px;padding:7px 14px;cursor:pointer;
 box-shadow:0 1px 0 rgba(19,74,142,.08);transition:all .13s}}
.ps:hover{{background:{C['brand']};color:#fff;border-color:{C['brand']};
 transform:translateY(-1px);box-shadow:0 3px 8px rgba(19,74,142,.25)}}
.ps:focus-visible{{outline:3px solid rgba(232,41,28,.45);outline-offset:2px}}
.pkg{{display:inline-flex;gap:4px}}
button.pk{{font:inherit;font-size:11px;font-weight:700;letter-spacing:.01em;
 color:{C['navy']};background:#fff;border:1.5px solid rgba(19,74,142,.28);
 border-radius:7px;padding:7px 8px;cursor:pointer;min-width:46px;
 box-shadow:0 1px 0 rgba(19,74,142,.10);
 font-variant-numeric:tabular-nums;transition:all .12s}}
button.pk.req{{background:#E7F0FB;border-color:rgba(19,74,142,.4)}}
button.pk:hover{{color:{C['redtext']};border-color:{C['red']};background:#FFF3F2;
 transform:translateY(-1px);box-shadow:0 3px 8px rgba(232,41,28,.2)}}
button.pk.on{{background:{C['redtext']};color:#fff;border-color:{C['redtext']};
 box-shadow:0 2px 7px rgba(218,33,21,.32)}}
button.pk:focus-visible{{outline:3px solid rgba(232,41,28,.45);outline-offset:2px}}
tr[data-series].locked td{{background:rgba(232,41,28,.055)}}
tr[data-series].locked td:first-child{{box-shadow:inset 3px 0 0 {C['red']}}}
tr[data-series].locked .lvwrap{{opacity:.32}}
.hint{{font-size:11.5px;color:{C['ink2']};margin-bottom:12px;line-height:1.5}}
.hint b{{color:{C['redtext']}}}
@media(max-width:840px){{
 .hero,.grid2,.grid2b{{grid-template-columns:1fr}}
 .pnbody{{grid-template-columns:1fr;gap:18px}}
 .pnodds{{border-right:none;border-bottom:1px solid {C['grid']};padding:0 0 14px}}
 .hdr{{flex-wrap:wrap}} .hdr .rec{{margin-left:0}}
 .enslab{{width:150px}}
}}
@media(max-width:560px){{
 body{{padding:10px}}
 .scenrow{{gap:16px}} .sv{{font-size:19px}}
 button.pk{{min-width:42px;padding:8px 5px;font-size:10.5px}}
 .pkg{{gap:3px}}
 .panel{{padding:15px 14px 18px}}
 .big{{font-size:52px}}
 .sldval{{font-size:25px}} .sldpace{{display:none}}
 .pnread{{gap:16px}} .perf{{margin-left:0;width:100%}}
 .card,.ms,.hdr{{padding:15px 14px}}
 .hdr h1{{font-size:20px}} .hdr .rec b{{font-size:25px}}
 .big{{font-size:56px}} .statv{{font-size:34px}}
 table{{font-size:11.5px}} td{{padding:6px 4px}} th{{padding:0 4px 7px}}
 .hide-s{{display:none}}
 .depnum{{width:88px;font-size:10px}}
 .enslab{{width:128px;font-size:10.5px}}
 .msswing{{width:62px}} .msswing b{{font-size:17px}}
 .msmatch{{font-size:15px}}
}}
</style></head><body><div class="wrap">

<div class="hdr">
  <div class="hdrid">
    {LOGO}
    <div>
    <h1>TORONTO <span>BLUE JAYS</span> — PLAYOFF TRACKER</h1>
    <div class="stamp">Standings through {STAMP} · {R['nsim']:,} simulated seasons</div>
    </div>
  </div>
  <div class="rec">
    <b>{W}–{L}</b>
    <div>{div_pos} · {GL} games left</div>
  </div>
</div>

<nav class="snav" aria-label="Jump to section">{nav_html}</nav>

<div class="panel" id="play">
  <div class="pnhead">
    <h2>Play it out <span class="sub">&mdash; drag the slider to set how Toronto finishes</span></h2>
    <span class="livetag">live</span>
  </div>
  <div class="pnbody">
    <div class="pnodds">
      <div class="big"><span id="liveOdds">{ODDS*100:.1f}</span><small>%</small></div>
      <div class="oddscap">chance of a playoff spot</div>
      <div class="meter"><div class="mfill" id="liveBar"></div></div>
      <div class="livedelta" id="liveDelta">model baseline &mdash; nothing set yet</div>
    </div>

    <div class="pnctl">
      <div class="sldtop">
        <div><span class="sldval" id="sliderVal">&mdash;</span>
             <span class="sldcap">rest-of-season record</span></div>
        <div class="sldpace" id="sliderPace"></div>
      </div>
      <div class="sldwrap">
        <input type="range" class="sld" id="winSlider" min="0" max="{GL}" step="1"
               value="{int(round(PROJ-W))}"
               aria-label="Rest-of-season wins for the Blue Jays, out of {GL} games">
        <div class="sldticks">
          <span class="tick start" style="left:0%"><i></i>0 wins</span>
          <span class="tick need" style="left:{P['ros_needed_w']/GL*100:.1f}%"><i></i>needs {P['ros_needed_w']}</span>
          <span class="tick end" style="left:100%"><i></i>{GL}</span>
        </div>
      </div>
      <div class="presets">
        <button type="button" data-preset="reset" class="ps">Reset</button>
        <button type="button" data-preset="min" class="ps">Bare minimum</button>
        <button type="button" data-preset="twoone" class="ps">2&ndash;1 every series</button>
        <button type="button" data-preset="sweep" class="ps">Sweep everything</button>
        <button type="button" data-preset="cold" class="ps">Slump (1&ndash;2 each)</button>
      </div>
      <div class="pnread">
        <div><span class="sv" id="liveRec">&mdash;</span><span class="sl" id="liveRecSub">drag the slider, or tap a series below</span></div>
        <div><span class="sv" id="liveProj">{PROJ:.1f}</span><span class="sl">projected wins</span></div>
        <div><span class="sv" id="liveCut">{R['cut_wins']['mean']:.1f}</span><span class="sl">cut line</span></div>
        <div class="perf" id="perfNote">simulating&hellip;</div>
      </div>
    </div>
  </div>
</div>

<div class="grid2">
  <div class="card">
    <h2>How solid is that number?</h2>
    <div class="range">
      <div class="rtrack">
        <div class="rfill" style="left:{(LO-0.05)/0.14*100:.0f}%;width:{(HI-LO)/0.14*100:.0f}%"></div>
        <div class="rtick" style="left:{(ODDS-0.05)/0.14*100:.0f}%"></div>
      </div>
      <div class="rlab"><span>{pct(LO)} floor</span>
        <span>10-model range</span><span>{pct(HI)} ceiling</span></div>
    </div>
    <div class="statl" style="margin-top:12px">Ten model specifications, varying how much
      run differential counts against raw W&ndash;L, how hard team strength is regressed,
      whether recent form matters, and the size of home-field advantage. Every one lands
      between {pct(LO)} and {pct(HI)}.</div>
    {bref_pill}
  </div>

  <div class="card" id="takes">
    <h2>What it takes</h2>
    <div class="statv">{P['ros_needed_w']}&ndash;{P['ros_needed_l']}</div>
    <div class="statl">To reach <b>{CUT_TARGET} wins</b>, the median cut line &mdash; a
      <b>.{int(P['ros_needed_w']/GL*1000)}</b> pace over the last {GL} games. The Jays have
      played .{int(W/(W+L)*1000)} ball all year, and win <b>{series_won:.1f}</b> of their
      {P['n_series']} remaining series in the runs where they qualify.</div>
    <div class="pill">{series_pill}</div>
    <div class="facts">
      <div class="fact"><div class="factv">{ELIM}</div>
        <div class="factl">Elimination number</div>
        <div class="factn">{elim_note}</div></div>
      <div class="fact"><div class="factv">{next_v}</div>
        <div class="factl">Next {NEXT_N} games</div>
        <div class="factn">{next_note}</div></div>
      <div class="fact"><div class="factv">{pass_v}</div>
        <div class="factl">Clubs to pass</div>
        <div class="factn">{pass_note}</div></div>
    </div>
  </div>
</div>

<div class="grid2b">
  <div class="card" id="race">
    <h2>The AL Wild Card race <span class="sub">— three spots, nine teams</span></h2>
    <div class="tscroll"><table>
      <thead><tr><th>Team</th><th style="text-align:right">W–L</th>
        <th style="text-align:right">GB<br>of TOR</th><th style="text-align:right">Run<br>diff</th>
        <th style="text-align:right" class="hide-s">Proj</th><th>Playoff odds</th></tr></thead>
      <tbody>{wc_html}</tbody></table></div>
    <div class="note">Division leaders ({_leaders_txt}) are excluded — they occupy the
      three automatic berths. <b>GB of TOR</b> is games ahead of Toronto: a positive
      number is a team the Jays must pass.</div>
  </div>

  <div class="card" id="curve">
    <h2>How many wins is enough?</h2>
    <svg viewBox="0 0 {CW} {CH}" width="100%" role="img"
         aria-label="Probability of a playoff spot by final win total">
      {gridlines}
      <polygon points="{area}" fill="{C['blue']}" opacity="0.13"/>
      <polyline points="{pts}" fill="none" stroke="{C['blue']}" stroke-width="2"
        stroke-linejoin="round" stroke-linecap="round"/>
      {cutline}{dots}{xticks}
      <line id="scenMark" x1="0" x2="0" y1="{PADT+26}" y2="{CH-PADB}" stroke="{C['scen']}"
        stroke-width="2" style="opacity:0;transition:opacity .3s"/>
      <text id="scenMarkLab" x="0" y="{PADT+16}" font-size="10" font-weight="800"
        fill="{C['redtext']}" stroke="#FFFFFF" stroke-width="3.5" paint-order="stroke"
        stroke-linejoin="round" style="opacity:0;transition:opacity .3s"></text>
      {hover}
      <line x1="{PADL}" x2="{CW-PADR}" y1="{py(0):.1f}" y2="{py(0):.1f}"
        stroke="{C['axis']}" stroke-width="1"/>
      <text x="{CW/2:.0f}" y="{CH-4}" text-anchor="middle" font-size="10"
        fill="{C['mute']}" letter-spacing="1">FINAL WIN TOTAL</text>
    </svg>
    <div class="note">{curve_note}</div>
    <details><summary>Show the table</summary>
      <table><thead><tr><th>Final wins</th><th>Rest-of-season</th>
        <th style="text-align:right">Playoff odds</th></tr></thead><tbody>
        {"".join(f'<tr><td>{w}</td><td class="gb">{w-W}–{GL-(w-W)}</td>'
                 f'<td style="text-align:right">{curve[w][0]*100:.1f}%</td></tr>'
                 for w in xs)}
      </tbody></table></details>
  </div>
</div>

<div class="grid2b">
  <div class="card" id="roadmap">
    <h2>The road map <span class="sub">&mdash; set any series yourself</span></h2>
    <div class="hint"><b>Tap any result below</b> to lock what the Jays do in that series
      &mdash; it turns red, the whole simulation re-runs, and the slider above moves to
      match. Rivals' records change too, because a Jays win is also an opponent's loss. Tap
      a red button again to hand that series back to the model. The lightly shaded button in
      each row is what the model says they need.</div>
    <noscript><div class="hint">The scenario picker needs JavaScript. Everything below is
      still the model baseline.</div></noscript>
    <div class="tscroll"><table>
      <thead><tr><th>Dates</th><th>Opponent</th><th>Tap to set</th>
        <th style="text-align:right">Need</th><th style="text-align:right" class="hide-s">Exp</th>
        <th>Swing</th></tr></thead>
      <tbody>{series_rows}</tbody></table></div>
    <div class="note"><b>Need</b> is the average number of wins Toronto takes from that
      series in the simulated seasons where they qualify; <b>Exp</b> is what the model
      actually expects them to win. <b>The gap between those two columns is the whole
      problem</b> — the Jays are projected to win about 1.4 of 3 in the hard series and
      need close to 2 in every single one, all thirteen of them, including on the road
      in Tampa and the Bronx. <b>Swing</b> is the gap in playoff odds between taking a
      series and losing it.</div>
  </div>

  <div class="card" id="watch">
    <h2>Scoreboard watching <span class="sub">— who to root against</span></h2>
    {dep_rows}
    <div class="note">Bar length is how much the Jays' odds move between a rival's
      cold finish (25th percentile) and hot finish (75th). {dep_note}</div>

    <h2 style="margin-top:20px">Model sensitivity <span class="sub">— is {pct(ODDS,0)} real?</span></h2>
    {ens_rows}
    <div class="note">Ten specifications, varying how much weight run differential gets
      against raw W–L, how hard team strength is regressed, whether recent form counts,
      and the size of home-field advantage. <b>Every one lands between {pct(LO)} and
      {pct(HI)}.</b> {ens_verdict}</div>
  </div>
</div>

<div class="ms" id="calendar">
  <h2>The run-in <span class="sub">— every game left, shaded by how much it moves the odds</span></h2>
  <div class="cwrap">{cal_html}</div>
  <div class="cleg">
    <span>Lower leverage</span>
    <span class="clramp">{ramp_legend}</span>
    <span>Higher</span>
    <span style="margin-left:6px"><span class="clkey"></span></span>
    <span>the five that decide the season · <b>@</b> marks a road game</span>
  </div>
  <h2 style="margin-top:22px">Must-see TV</h2>
  {mustsee_rows}
</div>

{injuries_section}

<div class="note">
<b>Method.</b> Team strength is Pythagenpat expected win% (exponent = runs-per-game<sup>0.287</sup>)
blended 80/20 with actual W–L, then regressed toward .500 with a 68-game prior. Every
remaining game on the real MLB schedule is simulated with a log5 matchup probability plus
home-field advantage (.535), {R['nsim']:,} seasons, full AL field with three division
winners and three wild cards. All conditional numbers — series targets, per-game leverage,
rival dependency — are read off the same set of simulated seasons, so they are mutually
consistent. <b>The scenario picker</b> re-runs this same model live in your browser (14,000 seasons a
click) rather than reading a number off the curve above. That matters: locking a Jays win
also locks the opponent's loss, and {CLUSTER_GAMES} of the {GL} remaining games are against
teams in the wild-card cluster — so going {ROS_W}&ndash;{ROS_L} is worth a little more than
"{CUT_TARGET} wins" on its own implies. <b>Known limits:</b> ties are broken at random rather
than by head-to-head; the model knows run differential, not injuries, rotations or September
call-ups.{synthetic_note} Data: MLB Stats API. Comparison odds: Baseball-Reference.
{bref_note_open} {pythag_note}
</div>

<div class="note" style="margin-top:10px;color:{C['mute']}">
Generated {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC ·
rebuilt nightly once every game has finished ·
not affiliated with or endorsed by the Toronto Blue Jays or MLB
</div>

</div>
<script>window.__SIM__={SIMJSON};</script>
<script>{APPJS}</script>
</body></html>"""

open("tracker.html", "w").write(HTML)
print(f"wrote tracker.html ({len(HTML):,} bytes)")
