"""Render the Maple Leafs playoff tracker from simulation output."""
import datetime, html, json, math, os

import data as D
import history as _H
import model as M

R = json.load(open("results.json"))
P = json.load(open("path.json"))
E = json.load(open("ensemble.json"))
SIM = json.load(open("simdata.json"))

FOCUS = D.FOCUS
TEAM = D.TEAMS[FOCUS]
FULL = f"{TEAM['city']} {TEAM['name']}"                       # Toronto Maple Leafs
NICK = TEAM["name"]                                           # Maple Leafs
THE = "the " + NICK.split()[-1]                                # the Leafs, in running prose
SITE_URL = os.environ.get("SITE_URL", "https://jays-playoff-tracker.netlify.app").rstrip("/")

ODDS = R["odds"]["playoff"]
LO, HI = E["lo"], E["hi"]
REC = R["record"]
W, L, OTL, PTS, GP = REC["w"], REC["l"], REC["otl"], REC["pts"], REC["gp"]
GL = R["games_left"]
CUT = R["cut_pts"]["p50"]
PROJ = R["proj_pts"]["mean"]
CUT_TARGET = R["cut_target"]
NEED = P["ros_needed_pts"]
PRESEASON = D.PRESEASON
CONF_NAME = R["focus_conf"]
DIVS = D.CONFERENCES[CONF_NAME]
CLUSTER = R["cluster"]
TEAMS_R = R["teams"]

# ---- palette. Leafs navy for structure and for anything you touch; a lighter steel blue
# for model data, so a control never reads as a readout. Red appears only for bad news —
# a falling number, a negative goal differential — never as a team colour.
C = dict(
    page="#EEF2F8", surf="#FFFFFF", card="#FFFFFF", card2="#EAF0F8",
    brand="#00205B",          # Leafs navy: header, headings, structure
    input="#00205B",          # anything the reader sets: slider, toggles, presets
    blue="#3D6DB5",           # model data: bars, the curve, fills
    navy="#00205B", ink="#0F1E3D", ink2="#465A78",
    mute="#5C6E8C",           # 4.8:1 on white — small uppercase labels clear AA
    bad="#B42318", good="#157F3C", warn="#B07500",
    grid="#E1E8F2", axis="#C0CEE2",
    ramp=["#00205B", "#1F447F", "#3D6DB5", "#6D95CC", "#A3BFE3"],   # dark -> light
)
NAVY_RGB = "0,32,91"
BLUE_RGB = "61,109,181"

DATE = datetime.date.fromisoformat(D.AS_OF)
STAMP = DATE.strftime("%A, %B %-d, %Y")


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def _ordinal(n):
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def nm(t):
    return TEAMS_R[t]["name"]


def rec_of(t):
    v = TEAMS_R[t]
    return f"{v['w']}&ndash;{v['l']}&ndash;{v['otl']}"


def ramp_ix(v, lo, hi):
    if hi <= lo:
        return 2
    return min(4, int((v - lo) / (hi - lo) * 5))


# ------------------------------------------------------------------ the race table
SOS = R.get("sos", {}) or {}
_race_teams = [t for t in M.CONF_TEAMS[CONF_NAME]]
_sv = [SOS[t] for t in _race_teams if SOS.get(t) is not None]
SOS_LO, SOS_HI = (min(_sv), max(_sv)) if _sv else (0.0, 1.0)


def sos_cell(v):
    if v is None:
        return '<span class="sosna">&mdash;</span>'
    i = ramp_ix(SOS_HI - v, 0, SOS_HI - SOS_LO)            # low win% = hard = dark
    bg = C["ramp"][::-1][i]
    fg = "#fff" if i >= 2 else C["navy"]
    return (f'<span class="sos" style="background:{bg};color:{fg}">'
            f'{("%.3f" % v).lstrip("0")}</span>')


def race_row(t, pos):
    v = TEAMS_R[t]
    ti = SIM["teams"].index(t)
    gd = v["gd"]
    cls = "focus" if t == FOCUS else ""
    return (f'<tr class="{cls}"><td class="pos">{pos}</td><td class="tm">{t}'
            f'<span class="tmn">{html.escape(v["name"])}</span></td>'
            f'<td class="r">{v["gp"]}</td><td class="r">{rec_of(t)}</td>'
            f'<td class="r pts">{v["pts"]}</td>'
            f'<td class="r {"rdpos" if gd > 0 else "rdneg" if gd < 0 else ""}">'
            f'{gd:+d}</td>'
            f'<td class="r hide-s">{sos_cell(SOS.get(t))}</td>'
            f'<td class="r hide-s">{v["proj_pts"]:.0f}</td>'
            f'<td><div class="oddsbar"><div class="obt"><div class="obf" '
            f'data-oddsbar="{ti}" style="width:{v["playoff"] * 100:.0f}%"></div></div>'
            f'<div class="obn" data-oddsnum="{ti}">{v["playoff"] * 100:.0f}%</div>'
            f'</div></td></tr>')


RACE = R["race"]
race_html = ""
for d in RACE["divisions"]:
    race_html += f'<tr class="grp"><td colspan="9">{html.escape(d)}</td></tr>'
    for k, t in enumerate(RACE["top3"][d]):
        race_html += race_row(t, k + 1)
race_html += '<tr class="grp"><td colspan="9">Wild card</td></tr>'
for k, t in enumerate(RACE["wildcard"]):
    if k == 2:
        race_html += ('<tr class="cut"><td colspan="9" class="cutlab">'
                      '&mdash; playoff cut line &mdash;</td></tr>')
    race_html += race_row(t, f"WC{k + 1}" if k < 2 else "")

# ------------------------------------------------------------------ points curve
curve = {int(k): v for k, v in R["pts_curve"].items()}
xs = sorted(curve)
ys = [curve[p][0] for p in xs]
CW, CH = 660, 250
PADL, PADR, PADT, PADB = 44, 14, 16, 34
_xspan = (xs[-1] - xs[0]) or 1
px = lambda p: PADL + (p - xs[0]) / _xspan * (CW - PADL - PADR)
py = lambda v: PADT + (1 - v) * (CH - PADT - PADB)
pts_line = " ".join(f"{px(p):.1f},{py(v):.1f}" for p, v in zip(xs, ys))
area = f"{PADL},{py(0):.1f} " + pts_line + f" {px(xs[-1]):.1f},{py(0):.1f}"

gridlines = ""
for gy in [0, .25, .5, .75, 1.0]:
    y = py(gy)
    gridlines += (f'<line x1="{PADL}" x2="{CW - PADR}" y1="{y:.1f}" y2="{y:.1f}" '
                  f'stroke="{C["grid"]}" stroke-width="1"/>'
                  f'<text x="{PADL - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="10" '
                  f'fill="{C["mute"]}" style="font-variant-numeric:tabular-nums">'
                  f'{int(gy * 100)}%</text>')
_step = 5 if _xspan > 30 else 2
xticks = "".join(
    f'<text x="{px(p):.1f}" y="{CH - PADB + 16}" text-anchor="middle" font-size="10" '
    f'fill="{C["mute"]}" style="font-variant-numeric:tabular-nums">{p}</text>'
    for p in xs if p % _step == 0)
dots = ""
for target, lab in [(R["pts_10"], "10%"), (R["pts_50"], "50%"), (R["pts_90"], "90%")]:
    if target and xs[0] <= target <= xs[-1] and target in curve:
        v = curve[target][0]
        dots += (f'<circle cx="{px(target):.1f}" cy="{py(v):.1f}" r="5" fill="{C["blue"]}" '
                 f'stroke="#fff" stroke-width="2"/>'
                 f'<text x="{px(target):.1f}" y="{py(v) - 13:.1f}" text-anchor="middle" '
                 f'font-size="11" font-weight="800" fill="{C["navy"]}" stroke="#fff" '
                 f'stroke-width="3.5" paint-order="stroke">{target}</text>')
hover = "".join(
    f'<rect x="{px(p) - 7:.1f}" y="{PADT}" width="14" height="{CH - PADT - PADB}" '
    f'fill="transparent"><title>{p} points → {pct(v)} chance of a playoff spot</title></rect>'
    for p, v in zip(xs, ys))
cutline = ""
if xs[0] <= CUT <= xs[-1]:
    cx = px(CUT)
    cutline = (f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{PADT + 26}" y2="{CH - PADB}" '
               f'stroke="{C["navy"]}" stroke-width="2"/>'
               f'<text x="{cx - 8:.1f}" y="{CH - PADB - 8:.1f}" text-anchor="end" '
               f'font-size="10" font-weight="700" fill="{C["navy"]}" stroke="#fff" '
               f'stroke-width="3.5" paint-order="stroke">MEDIAN CUT LINE {CUT:.0f} PTS</text>')

_p10, _p90 = R["pts_10"], R["pts_90"]
if _p10 in curve and _p90 in curve and _p90 > _p10:
    curve_note = (f"<b>{_p10} points is a {curve[_p10][0] * 100:.0f}% proposition; {_p90} "
                  f"is a {curve[_p90][0] * 100:.0f}% one.</b> Every point in between is worth "
                  f"about {(curve[_p90][0] - curve[_p10][0]) / (_p90 - _p10) * 100:.0f} "
                  f"points of playoff probability. The cut line is the second wild card's "
                  f"total, which moves season to season — hence a curve, not a number.")
else:
    curve_note = ("The race is settled: across the plausible range of final totals the "
                  "answer barely moves.")

# ------------------------------------------------------------------ scoreboard watching
dep = R["dependency"]
dep_items = sorted(dep.items(), key=lambda x: -x[1]["swing"])[:6]
dmax = max((abs(v["swing"]) for _, v in dep_items), default=0) or 1.0
dep_rows = ""
for i, (t, v) in enumerate(dep_items):
    ti = SIM["teams"].index(t)
    dep_rows += f"""
    <div class="deprow">
      <div class="depname">{t}</div>
      <div class="depctl" role="group" aria-label="Force how the {html.escape(nm(t))} finish">
        <button type="button" class="db" data-rival="{ti}" data-mode="-1" aria-pressed="false"
          title="Force the {html.escape(nm(t))} cold — around {v['cold_pts']:.0f} points">cold</button>
        <button type="button" class="db" data-rival="{ti}" data-mode="1" aria-pressed="false"
          title="Force the {html.escape(nm(t))} hot — around {v['hot_pts']:.0f} points">hot</button>
      </div>
      <div class="deptrack"><div class="depbar" style="width:{abs(v['swing']) / dmax * 100:.0f}%;
        background:{C['navy'] if i == 0 else C['blue']}"
        title="If the {html.escape(nm(t))} finish cold (~{v['cold_pts']:.0f} pts) {THE} are {pct(v['if_rival_cold'])}; hot (~{v['hot_pts']:.0f}), {pct(v['if_rival_hot'])}."></div></div>
      <div class="depnum">{pct(v['if_rival_cold'])} <span class="arrow">&harr;</span> {pct(v['if_rival_hot'])}</div>
    </div>"""
if dep_items:
    _dt, _dv = dep_items[0]
    dep_note = (f"<b>The {html.escape(nm(_dt))} are the single most important other club</b> "
                f"for {THE} &mdash; a {abs(_dv['swing']) * 100:.1f}-point swing between "
                f"their cold and hot finishes.")
else:
    dep_note = ""

# ------------------------------------------------------------------ model sensitivity
ens = sorted(E["scenarios"], key=lambda s: s["odds"])
_eod = [s["odds"] for s in ens] or [0.0]
_epad = max((max(_eod) - min(_eod)) * 0.10, 0.004)
_elo, _espan = min(_eod) - _epad, (max(_eod) - min(_eod)) + 2 * _epad
ens_rows = "".join(
    f'<div class="ensrow"><div class="enslab">{html.escape(s["label"])}'
    f'{" <em>◂ primary</em>" if s["primary"] else ""}</div>'
    f'<div class="enstrack"><div class="ensdot{" p" if s["primary"] else ""}" '
    f'style="left:{(s["odds"] - _elo) / _espan * 100:.1f}%"></div></div>'
    f'<div class="ensval">{pct(s["odds"])}</div></div>' for s in ens)
_noprior = next((s for s in ens if "no prior" in s["label"]), None)
_rest = [s["odds"] for s in ens if s is not _noprior]
_rest_spread = (max(_rest) - min(_rest)) if _rest else 0
if PRESEASON and _noprior:
    ens_verdict = (f"The outlier is the one that ignores last season: with no games played "
                   f"it rates all 32 clubs identically and lands on "
                   f"{pct(_noprior['odds'], 0)}, which is just the share of clubs that make "
                   f"it. <b>In the preseason, last season is doing almost all of the "
                   f"work</b>, and it gives way to this season's results as they arrive. "
                   f"Set that one aside and the other nine span "
                   f"{_rest_spread * 100:.0f} points.")
elif HI - LO <= 0.06:
    ens_verdict = ("A narrow band &mdash; the number is coming from the standings and the "
                   "schedule, not from a modelling choice.")
else:
    ens_verdict = ("A wide band &mdash; how much you trust goal differential over the record, "
                   "and how much last season still counts, genuinely changes the answer.")

# ------------------------------------------------------------------ must-see games
_lev = R["leverage"]
must_see, _per_opp = [], {}
for g in sorted(_lev, key=lambda x: -x["leverage"]):
    if len(must_see) >= 5:
        break
    if _per_opp.get(g["opp"], 0) >= 2:
        continue
    _per_opp[g["opp"]] = _per_opp.get(g["opp"], 0) + 1
    must_see.append(g)


def why_for(g):
    opp = g["opp"]
    v = TEAMS_R[opp]
    later = sum(1 for x in _lev if x["opp"] == opp and x["date"] > g["date"])
    if v["conf"] != CONF_NAME:
        lead = (f"The {html.escape(v['name'])} are in the other conference, so only "
                f"{THE}' own points move.")
    else:
        lead = (f"The {html.escape(v['name'])} are {v['playoff'] * 100:.0f}% to reach the "
                f"playoffs" + (f", {v['pts']} points from {v['gp']} games." if v["gp"]
                               else "."))
    when = (" The last meeting of the season" if later == 0 else
            f" {later} more meeting{'s' if later > 1 else ''} to come")
    if opp in CLUSTER:
        stake = ", and a win here takes points straight off a club in the race."
    else:
        stake = "."
    return lead + when + stake


mustsee_rows = ""
for i, g in enumerate(must_see):
    d = datetime.date.fromisoformat(g["date"])
    mustsee_rows += f"""
    <div class="mstile">
      <div class="msrank">{i + 1}</div>
      <div class="msbody">
        <div class="msdate">{d.strftime('%a %b %-d')}</div>
        <div class="msmatch">{'vs' if g['home'] else '@'} {html.escape(nm(g['opp']))}</div>
        <div class="mswhy">{why_for(g)}</div>
      </div>
      <div class="msswing"><b>&plusmn;{g['leverage'] * 100:.1f}</b><span>pts of<br>playoff odds</span></div>
    </div>"""

# ------------------------------------------------------------------ calendar: next two months
_by_date = {}
for g in _lev:
    _by_date.setdefault(g["date"], []).append(g)
_lv = [g["leverage"] for g in _lev] or [0.0]
_lmin, _lmax = min(_lv), max(_lv)
_top5 = {(g["date"], g["opp"]) for g in must_see}
cal_html = ""
if _by_date:
    _first = datetime.date.fromisoformat(min(_by_date))
    _m = datetime.date(_first.year, _first.month, 1)
    for _ in range(2):
        _nxt = datetime.date(_m.year + (_m.month == 12), _m.month % 12 + 1, 1)
        cells = '<div class="cday out"></div>' * ((_m.weekday() + 1) % 7)
        d = _m
        while d < _nxt:
            key = d.isoformat()
            gs = _by_date.get(key)
            if not gs:
                cells += f'<div class="cday off"><i>{d.day}</i></div>'
            else:
                g = gs[0]
                ix = ramp_ix(g["leverage"], _lmin, _lmax)
                cap = (f'{d.strftime("%a %b %-d")} &middot; {"vs" if g["home"] else "at"} '
                       f'{html.escape(nm(g["opp"]))} &middot; win &rarr; {pct(g["p_win"])}, '
                       f'loss &rarr; {pct(g["p_loss"])} ({g["leverage"] * 100:.1f} pts)')
                cells += (f'<div class="cday game{" key" if (key, g["opp"]) in _top5 else ""}" '
                          f'tabindex="0" data-cap="{cap}" style="background:{C["ramp"][::-1][ix]};'
                          f'color:{"#fff" if ix >= 2 else C["navy"]}"><i>{d.day}</i>'
                          f'<b>{"" if g["home"] else "@"}{g["opp"]}</b></div>')
            d += datetime.timedelta(days=1)
        cal_html += (f'<div class="cmon"><div class="cmname">{_m.strftime("%B %Y")}</div>'
                     f'<div class="cgrid">'
                     + "".join(f'<div class="cdow">{x}</div>' for x in "SMTWTFS")
                     + cells + '</div></div>')
        _m = _nxt
ramp_legend = "".join(f'<span style="background:{c}"></span>' for c in C["ramp"][::-1])

# ------------------------------------------------------------------ around the league
AROUND = R.get("around", [])
AROUND_TOP = max((g["leverage"] for g in AROUND), default=0.0) or 1.0


def around_rows(items, show_date=True):
    out = ""
    for g in items:
        sure = g.get("sure", True)
        root_home = g["root"] == g["home"]
        mark = lambda n, on: f'<span class="alroot">{n}</span>' if (on and sure) else n
        tip = (f'Root for the {html.escape(nm(g["root"]))} — worth '
               f'{g["leverage"] * 100:.1f} points of {THE}&#39; playoff odds' if sure else
               "Too close to call: inside the simulation's own margin of error")
        out += (f'<div class="alrow{"" if sure else " toss"}" title="{tip}">'
                + (f'<div class="aldate">{datetime.date.fromisoformat(g["date"]).strftime("%b %-d")}</div>'
                   if show_date else "")
                + f'<div class="almatch">{mark(g["away"], not root_home)} <i>at</i> '
                  f'{mark(g["home"], root_home)}'
                + ('<span class="alh2h">both in the race</span>' if g["h2h"] and sure else "")
                + f'</div><div class="altrack"><div class="albar" '
                  f'style="width:{max(2, g["leverage"] / AROUND_TOP * 100):.0f}%"></div></div>'
                + (f'<div class="alnum">{g["leverage"] * 100:.1f}</div>' if sure
                   else '<div class="alnum tossl">toss-up</div>') + '</div>')
    return out


_next_date = R.get("around_next_date")
_tonight = [g for g in AROUND if g["date"] == _next_date][:8]
_biggest = sorted((g for g in AROUND if g.get("sure", True)), key=lambda g: -g["leverage"])[:6]
_h2h = next((g for g in AROUND if g["h2h"] and g.get("sure", True)), None)
around_note = (
    f"When two clubs still in the race meet &mdash; the {html.escape(nm(_h2h['away']))} at "
    f"the {html.escape(nm(_h2h['home']))} on "
    f"{datetime.date.fromisoformat(_h2h['date']).strftime('%b %-d')} &mdash; the game is "
    f"worth less than either club's bar suggests, because one of them has to lose."
    if _h2h else
    "Each game here moves one club's total in one direction.")
around_section = ""
if AROUND:
    around_section = f"""<div class="grid1">
  <div class="card" id="around">
    <h2>Around the league <span class="sub">&mdash; the games {THE} aren't playing</span></h2>
    <div class="hint">Every remaining game touching the {CONF_NAME} Conference, scored against
      {THE}' odds from the same simulated seasons as everything else. <b>The highlighted club
      is the one to root for.</b></div>
    <div class="algrid">
      <div><div class="alhead">{datetime.date.fromisoformat(_next_date).strftime("%A, %B %-d") if _next_date else "Next games"}</div>
        {around_rows(_tonight, show_date=False) or '<div class="alempty">No other games that day.</div>'}</div>
      <div><div class="alhead">Biggest left, any date</div>{around_rows(_biggest)}</div>
    </div>
    <div class="note">{around_note} A game marked <b>toss-up</b> is inside the simulation's own
      margin of error, so the page does not pretend to know which way to cheer.</div>
  </div>
</div>"""

# ------------------------------------------------------------------ the bracket
BK = R.get("bracket")
bracket_section = ""
if BK:
    NODES = BK["nodes"]
    fp = BK["focus_conf"]
    op = "W" if fp == "E" else "E"
    my_divs = BK["divisions"]
    ot_divs = BK["other_divisions"]

    def seat_labels(divs):
        a, b = divs[0][0], divs[1][0]
        return [f"{a}1", "WC", f"{a}2", f"{a}3", f"{b}1", "WC", f"{b}2", f"{b}3"]

    def node(key, label=None, cls=""):
        rows = NODES.get(key) or []
        top = rows[0] if rows else {"team": "?", "p": 0.0}
        you = " you" if top["team"] == FOCUS else ""
        alt = ", ".join(f'{r["team"]} {r["p"] * 100:.0f}%' for r in rows[:3])
        return (f'<div class="bknode{you}{cls}" data-node="{key}" title="{html.escape(alt)}">'
                f'<span class="bkfill" data-bk-fill style="width:{top["p"] * 100:.0f}%"></span>'
                + (f'<span class="bkseed">{label}</span>' if label else "")
                + f'<span class="bkteam" data-bk-team>{top["team"]}</span>'
                  f'<span class="bkpct" data-bk-p>{top["p"] * 100:.0f}%</span></div>')

    def side(p, divs, mirror):
        lab = seat_labels(divs)
        c1 = "".join(f'<div class="bkgrp link">{node(f"{p}{2 * k + 1}", lab[2 * k])}'
                     f'{node(f"{p}{2 * k + 2}", lab[2 * k + 1])}</div>' for k in range(4))
        c2 = (f'<div class="bkgrp link">{node(f"{p}r1a")}{node(f"{p}r1b")}</div>'
              f'<div class="bkgrp link">{node(f"{p}r1c")}{node(f"{p}r1d")}</div>')
        c3 = f'<div class="bkgrp link">{node(f"{p}r2a")}{node(f"{p}r2b")}</div>'
        side_cls = "w" if mirror else "e"
        mob = " mhide" if p != fp else ""
        cols = [f'<div class="bkcol {side_cls}{mob}" data-round="First round">{c1}</div>',
                f'<div class="bkcol {side_cls}{mob}" data-round="Second round">{c2}</div>',
                f'<div class="bkcol {side_cls}{mob}" data-round="Conference final">{c3}</div>']
        return "".join(reversed(cols)) if mirror else "".join(cols)

    final_col = (f'<div class="bkcol fin" data-round="Stanley Cup Final">'
                 f'<div class="bkgrp"><div class="bkconf">{CONF_NAME} champion</div>'
                 f'{node(f"{fp}cf")}</div>'
                 f'<div class="bkgrp">{node("cup", "", " champ")}</div>'
                 f'<div class="bkgrp"><div class="bkconf">'
                 f'{"Western" if fp == "E" else "Eastern"} champion</div>'
                 f'{node(f"{op}cf")}</div></div>')

    road = BK["road"]
    road_rows = "".join(
        f'<div class="bkrd"><span class="bkrdl">{lab}</span>'
        f'<div class="bkrdt"><div class="bkrdf" data-road="{k}" '
        f'style="width:{road[k] * 100:.0f}%"></div></div>'
        f'<span class="bkrdv" data-road-v="{k}">{road[k] * 100:.{1 if k == "cup" else 0}f}%</span></div>'
        for k, lab in (("r1", "Win round one"), ("r2", "Win round two"),
                       ("cf", f"Win the {CONF_NAME}"), ("cup", "Win the Cup")))

    _opp = BK["best_seat_opponent"]
    _head = (f'Most likely <b>{BK["best_label"]}</b> ({BK["best_seat_p"] * 100:.0f}% of '
             f'qualifying seasons)' + (
                 f', {"hosting" if BK["best_seat_hosts"] >= 0.5 else "at"} '
                 f'<b>the {html.escape(nm(_opp))}</b> in the first round' if _opp else ""))
    _labels = "; ".join(f"{k} {v * 100:.0f}%" for k, v in list(BK["labels"].items())[:5])

    bracket_section = f"""<div class="grid1">
  <div class="card" id="bracket">
    <h2>If they get in <span class="sub">&mdash; the whole playoff bracket, over the seasons
      {THE} qualify</span></h2>
    <div class="bkhead" id="bkHead">{_head}</div>
    <div class="bkroad">{road_rows}</div>
    <div class="tscroll"><div class="bk">
      <div class="bkgridh">
        <span>First round</span><span>Second round</span><span>Conf. final</span>
        <span class="c">Stanley Cup Final</span>
        <span class="rt">Conf. final</span><span class="rt">Second round</span><span class="rt">First round</span>
      </div>
      <div class="bkgrid">{side(fp, my_divs, False)}{final_col}{side(op, ot_divs, True)}</div>
    </div></div>
    <div class="note"><b>Every number here is conditional on {THE} qualifying</b>, which is
      itself {pct(BK["p_qualify"])} &mdash; most of the time none of this happens. The bracket
      is drawn as one picture: {THE} sit in their likeliest seat opposite the club they most
      often meet from there, every other club takes one seat at most, and each later slot goes
      to whichever of its two feeders wins that series more often. The percentage is how often
      that club reaches that slot; hover for the next two.
      How they get in, across all those seasons: {_labels}. The top three in each division
      qualify, then two wild cards; the better division winner draws the second wild card, so
      a wild card can land in either half. Every series is best of seven, 2&ndash;2&ndash;1&ndash;1&ndash;1,
      home ice to the better regular season, played with the same matchup that simulates an
      October game. The {CONF_NAME} side re-runs with any scenario you set above; the other
      conference can't be moved by anything on this page, so it holds still.</div>
  </div>
</div>"""

# ------------------------------------------------------------------ odds over time
_now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
_mom = R.get("momentum")
_mom_idx = (_mom or {}).get("index")
HIST = _H.append(_H.parse(D.HISTORY), _now, ODDS, _mom_idx)
HIST_META = _H.encode(HIST)
DELTA = _H.delta(_H.parse(D.HISTORY), _now, ODDS, _mom_idx)
TREND_SVG, TREND_NOTE = _H.sparkline(HIST, C)
trend_section = (f"""<div class="grid1">
  <div class="card" id="trend">
    <h2>How the odds got here <span class="sub">&mdash; every rebuild, most recent on the right</span></h2>
    <div class="trend">{TREND_SVG}</div>
    <div class="note">{TREND_NOTE}</div>
  </div>
</div>""" if TREND_SVG else "")


def _ago(h):
    return "a day" if 20 <= h <= 28 else (f"{h:.0f} hours" if h < 48 else f"{h / 24:.0f} days")


def _chip(value, unit, cls, digits=1):
    if value is None:
        return ""
    if abs(value) < (0.05 if digits else 0.5):
        return f'<span class="{cls} flat">no change</span>'
    tone = "up" if value > 0 else "down"
    arrow = "&#9650;" if value > 0 else "&#9660;"
    return f'<span class="{cls} {tone}">{arrow} {abs(value):.{digits}f}{unit}</span>'


odds_delta_html = mom_delta_html = ""
if DELTA:
    odds_delta_html = (f'<div class="oddsdelta">{_chip(DELTA["odds"] * 100, " pts", "chg")}'
                       f'<span class="chgwhen">vs {_ago(DELTA["age_hours"])} ago '
                       f'({pct(DELTA["prev_odds"])})</span></div>')
    if DELTA["momentum"] is not None:
        mom_delta_html = _chip(float(DELTA["momentum"]), "", "momchg", digits=0)

if _mom:
    _arr = "&#9650;" if _mom["index"] > 0 else ("&#9660;" if _mom["index"] < 0 else "&#9644;")
    _tip = (f"Recency-weighted form over the last {_mom['window']} games, scored against what "
            f"the model expected. 0 means playing exactly to their own level. Half-life "
            f"{_mom['half_life']} games.")
    momentum_badge = (
        f'<div class="mom mom-{_mom["tone"]}" title="{html.escape(_tip)}">'
        f'<div class="momtop"><span class="momarr">{_arr}</span>'
        f'<span class="momidx">{_mom["index"]:+d}</span></div>'
        f'<div class="momlab">{html.escape(_mom["label"])}{mom_delta_html}</div>'
        f'<div class="momsub">{_mom["l10_w"]}&ndash;{_mom["l10_l"]}&ndash;{_mom["l10_otl"]} '
        f'last 10 &middot; {_mom["l10_expected_w"]} W expected</div></div>')
else:
    momentum_badge = ""

# ------------------------------------------------------------------ the header's words
_open = min((g["date"] for g in _lev), default=None)
_open_txt = datetime.date.fromisoformat(_open).strftime("%B %-d") if _open else ""
if GL == 0:
    _vtxt = "Season complete"
elif ODDS >= 0.985:
    _vtxt = "A playoff spot is all but locked up"
elif ODDS >= 0.75:
    _vtxt = "In control of a playoff spot"
elif ODDS >= 0.6:
    _vtxt = "Favoured, but far from safe"
elif ODDS >= 0.4:
    _vtxt = "A genuine coin flip"
elif ODDS >= 0.15:
    _vtxt = "Uphill, but very much alive"
elif ODDS >= 0.005:
    _vtxt = f"A long shot &mdash; {THE} need help"
else:
    _vtxt = "All but out"
if PRESEASON:
    verdict_html = (f'<div class="verdict">Season opens {_open_txt} &mdash; on last season\'s '
                    f'form, {_vtxt[0].lower() + _vtxt[1:]}. It takes <b>{NEED} points</b> '
                    f'from {GL} games.</div>')
else:
    verdict_html = (f'<div class="verdict">{_vtxt}'
                    + (f' &mdash; it takes <b>{NEED} points</b> from here'
                       if GL and 0.005 <= ODDS < 0.985 else "") + "</div>")

DIVI = R["division"]
# the slider's scale. Near either end the "needs" label takes that end's place, so the
# two never print on top of each other or run off the card
_nf = (NEED / (2 * GL)) if GL else 0.0
_need_cls = " end" if _nf > 0.88 else " start" if _nf < 0.12 else ""
ticks_html = (
    ('' if _nf < 0.12 else '<span class="tick start" style="left:0%"><i></i>0</span>')
    + f'<span class="tick need{_need_cls}" style="left:{_nf * 100:.1f}%"><i></i>needs {NEED}</span>'
    + ('' if _nf > 0.88 else f'<span class="tick end" style="left:100%"><i></i>{2 * GL}</span>'))

div_pos = f"{_ordinal(DIVI['rank'])} {DIVI['name']}"
# before a puck drops every club is on zero, so a division place would be an alphabet
rec_line = (f"{GL} games to play" if PRESEASON
            else f"{PTS} pts &middot; {div_pos} &middot; {GL} left")
if PRESEASON:
    div_line = f"{pct(DIVI['odds'], 0)} to win the {DIVI['name']}"
elif DIVI["leader"] == FOCUS:
    div_line = f"Lead the {DIVI['name']} &middot; {pct(DIVI['odds'], 0)} to win it"
else:
    div_line = (f"{DIVI['back']} pts back of {DIVI['leader']} &middot; "
                f"{pct(DIVI['odds'], 0)} to win the {DIVI['name']}")

NG_ = R.get("next_game")
next_html = ""
if NG_ and GL:
    _nd = datetime.date.fromisoformat(NG_["date"])
    next_html = f"""
<div class="next" id="next" data-utc="{html.escape(NG_.get('utc') or '')}"
     data-state="{html.escape(NG_.get('state') or '')}" data-date="{NG_['date']}"
     data-opener="{'1' if GP == 0 else ''}">
  <div class="nxwhen"><b id="nxWhen">Next game</b>
    <span id="nxTime">{_nd.strftime('%a %b %-d')}</span></div>
  <div class="nxmatch">{'vs' if NG_['home'] else '@'} {html.escape(NG_['opp_name'])}
    <span class="rec">{NG_['opp_record']}</span></div>
  <div class="nxodds"><span class="nxw">Win &rarr; {pct(NG_['p_win'])}</span>
    <span class="nxl">Loss &rarr; {pct(NG_['p_loss'])}</span>
    <span class="nxswing">&plusmn;{NG_['leverage'] * 100:.1f} pts</span></div>
</div>"""

# ------------------------------------------------------------------ what it takes
LINE = R["line"]
if PRESEASON:
    line_v, line_l = "0", "Games played"
    line_n = (f"Everyone starts level on {_open_txt}. Until real games pile up, the order below "
              f"is a projection, not a standing.")
elif LINE["vs"]:
    _vs = html.escape(nm(LINE["vs"]))
    _gh = LINE["gp_diff"]
    _ghs = (f" with {abs(_gh)} game{'s' if abs(_gh) != 1 else ''} "
            f"{'in hand' if _gh > 0 else 'more played'}" if _gh else "")
    if LINE["in"]:
        line_v, line_l = f"+{LINE['gap']}", "Points clear"
        line_n = f"Ahead of the {_vs}, the first club out{_ghs}."
    else:
        line_v, line_l = f"&minus;{LINE['gap']}", "Points back"
        line_n = f"Behind the {_vs}, who hold the last playoff spot{_ghs}."
else:
    line_v, line_l, line_n = "&mdash;", "Points back", ""

NEXT = {int(k): v for k, v in R["next_pts"].items()}
NN_ = R["next_n"]
if NEXT and GL:
    _want = int(round(NEED / GL * NN_)) if GL else 0
    _pace = min(NEXT, key=lambda p: (abs(p - _want), -p))
    _better = min((p for p in NEXT if p > _pace + 1), default=None)
    next_v = f"{_pace} pts"
    next_note = f"The pace the season demands holds the odds at {pct(NEXT[_pace][0])}."
    if _better is not None:
        next_note += f" Taking {_better} instead: {pct(NEXT[_better][0])}."
else:
    next_v, next_note = "&mdash;", "Fewer games remain than this window needs."

pass_v = f"{R['pass_given_in']:.1f} of {len(CLUSTER)}"
pass_note = (f"Of the clubs projected within {M.CLUSTER_PTS:.0f} points of {THE} "
             f"({', '.join(CLUSTER)}), how many they finish ahead of in the seasons they "
             f"qualify.")

_prior = D.PRIOR.get(FOCUS)
if PRESEASON and _prior:
    _pp = 2 * _prior["w"] + _prior["otl"]
    takes_ctx = (f"Last season they took <b>{_pp}</b> from {_prior['gp']} games "
                 f"({_pp / (2 * _prior['gp']):.3f}) and missed. The model starts from that "
                 f"and lets this season take over as games are played.")
elif GP:
    takes_ctx = (f"Their pace so far is {PTS / (2 * GP):.3f}, {PTS} points from "
                 f"{GP} games.")
else:
    takes_ctx = ""

# ------------------------------------------------------------------ nav
SECTIONS = [("play", "Play it out")]
if TREND_SVG:
    SECTIONS.append(("trend", "How we got here"))
SECTIONS += [("takes", "What it takes"), ("race", "The race"), ("curve", "Points needed"),
             ("watch", "Scoreboard")]
if AROUND:
    SECTIONS.append(("around", "Around the league"))
if BK:
    SECTIONS.append(("bracket", "If they get in"))
SECTIONS.append(("calendar", "Calendar"))
nav_html = "".join(f'<a href="#{s}">{html.escape(l)}</a>' for s, l in SECTIONS)

GENERATED_UTC = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---- the browser bundle picks up what only the page knows
SIM["curveX0"], SIM["curveX1"] = round(px(xs[0]), 2), round(px(xs[-1]), 2)
SIM["curveP0"], SIM["curveP1"] = xs[0], xs[-1]
SIM["rosNeeded"] = NEED
SIM["projPts"] = round(PROJ, 2)
SIM["confPrefix"] = "E" if CONF_NAME == "Eastern" else "W"
SIM["shareName"] = FULL
SIM["shareTitle"] = f"{NICK} Playoff Tracker"
SIMJSON = json.dumps(SIM, separators=(",", ":"))
APPJS = open("app.js").read()

LIVE_JS = r"""<script>
/* Time, in the reader's terms. The build stamps UTC; the browser renders Eastern time,
   says "tonight" or "underway" about the next game, and warns when the page is old
   enough that a game is probably missing. No network, no storage. */
(function () {
  "use strict";
  var TZ = "America/Toronto";
  function fmt(d, opts) {
    try { return new Intl.DateTimeFormat("en-CA", Object.assign({ timeZone: TZ }, opts)).format(d); }
    catch (e) { return d.toUTCString(); }
  }
  function etDay(d) { return fmt(d, { year: "numeric", month: "2-digit", day: "2-digit" }); }
  function etTime(d) { return fmt(d, { hour: "numeric", minute: "2-digit" }).replace(/\.\s?/g, "").toUpperCase() + " ET"; }
  function etStamp(d) { return fmt(d, { weekday: "short", month: "short", day: "numeric" }) + ", " + etTime(d); }
  var now = new Date();

  var upd = document.getElementById("updAgo"), gen = null;
  if (upd && upd.dataset.utc) gen = new Date(upd.dataset.utc);
  if (gen && !isNaN(gen)) {
    var hrs = (now - gen) / 36e5;
    upd.textContent = "updated " + (hrs < 1 ? Math.max(1, Math.round(hrs * 60)) + " min ago"
                      : hrs < 48 ? Math.round(hrs) + "h ago" : Math.round(hrs / 24) + " days ago");
    var stale = document.getElementById("stale");
    if (stale && hrs > 30) {
      stale.innerHTML = "<b>This page is " + Math.round(hrs / 24 * 10) / 10 + " days old.</b> " +
        "It was last rebuilt " + etStamp(gen) + ", so at least one game is probably missing " +
        "and every number here is from before it. Use <b>Refresh</b> at the top to pull " +
        "the latest results in.";
      stale.hidden = false;
    }
    var g = document.getElementById("genET");
    if (g) g.textContent = etStamp(gen);
  }

  var nx = document.getElementById("next");
  if (nx) {
    var when = document.getElementById("nxWhen"), t = document.getElementById("nxTime");
    var start = nx.dataset.utc ? new Date(nx.dataset.utc) : null, state = nx.dataset.state;
    var dayLabel = nx.dataset.opener ? "Season opener" : "Next game";
    var day = nx.dataset.date, today = etDay(now);
    var tomorrow = etDay(new Date(now.getTime() + 864e5));
    if (day === today) dayLabel = "Tonight";
    else if (day === tomorrow) dayLabel = "Tomorrow";
    else if (day < today) dayLabel = "Awaiting rebuild";
    if (start && !isNaN(start)) {
      t.textContent = etStamp(start);
      var mins = (now - start) / 6e4;
      // the NHL feed marks a game in progress LIVE, or CRIT in its final minutes
      if (state === "LIVE" || state === "CRIT" || (mins > 0 && mins < 180)) {
        dayLabel = "Underway"; nx.classList.add("live");
      } else if (mins >= 180) { dayLabel = "Played · odds update after the next rebuild"; }
    }
    when.textContent = dayLabel;
  }

  var cap = document.getElementById("calCap");
  if (cap) {
    var cells = document.querySelectorAll(".cday.game[data-cap]");
    function show(e) { cap.innerHTML = e.currentTarget.dataset.cap; }
    for (var i = 0; i < cells.length; i++) {
      cells[i].addEventListener("click", show);
      cells[i].addEventListener("focus", show);
    }
  }
})();
</script>"""

_fav = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
        "%3Crect width='32' height='32' rx='7' fill='%2300205B'/%3E"
        "%3Cellipse cx='16' cy='19' rx='10' ry='4' fill='%23fff'/%3E"
        "%3Crect x='6' y='13' width='20' height='6' fill='%23fff'/%3E"
        "%3Cellipse cx='16' cy='13' rx='10' ry='4' fill='%23C9D6EA'/%3E%3C/svg%3E")

HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{NICK} Playoff Tracker — {DATE.strftime('%b %-d, %Y')}</title>
<meta name="robots" content="index,follow">
<meta name="tracker-id" content="{D.TRACKER_ID}">
<meta name="data-fingerprint" content="{D.FINGERPRINT}">
<meta name="page-history" content="{HIST_META}">
<meta name="theme-color" content="{C['brand']}">
<meta name="description" content="{FULL} {W}–{L}–{OTL}, {PTS} points. {ODDS * 100:.1f}% to reach the playoffs. It takes {NEED} points from {GL} games. Updated {DATE.strftime('%b %-d')}.">
<meta property="og:type" content="website">
<meta property="og:title" content="{NICK} Playoff Tracker — {ODDS * 100:.1f}%">
<meta property="og:description" content="{FULL} {W}–{L}–{OTL}. Needs {NEED} points to reach the {CUT:.0f}-point cut line. {R['nsim']:,} simulated seasons, updated {DATE.strftime('%b %-d')}.">
<meta property="og:url" content="{SITE_URL}/">
<meta property="og:image" content="{SITE_URL}/og.png?v={D.FINGERPRINT}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{_fav}">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{background:{C['page']};color:{C['ink']};
 background-image:radial-gradient(1100px 460px at 50% -180px,rgba({NAVY_RGB},.10),transparent 70%);
 background-repeat:no-repeat;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
 padding:20px 18px 44px;line-height:1.5;-webkit-font-smoothing:antialiased;
 text-rendering:optimizeLegibility}}
.wrap{{max-width:1180px;margin:0 auto}}
::selection{{background:rgba({BLUE_RGB},.2)}}
:focus-visible{{outline:2px solid {C['brand']};outline-offset:2px;border-radius:4px}}
.card{{background:{C['card']};border:1px solid rgba({NAVY_RGB},.07);border-radius:16px;
 padding:18px 20px;box-shadow:0 1px 2px rgba({NAVY_RGB},.05),0 2px 10px rgba({NAVY_RGB},.04)}}
h2{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:{C['brand']};
 display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;font-weight:800;margin-bottom:14px}}
.sub{{font-size:12px;color:{C['ink2']};font-weight:400;letter-spacing:0;text-transform:none}}
.hint{{font-size:11.5px;color:{C['ink2']};margin-bottom:12px;line-height:1.5}}
.hint b{{color:{C['navy']}}}
.note{{font-size:10.5px;color:{C['ink2']};line-height:1.7;margin-top:15px;padding-top:13px;
 border-top:1px solid {C['grid']}}}
.note b{{color:{C['navy']}}}
.grid1{{margin-bottom:16px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;align-items:start}}
.grid2b{{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;margin-bottom:16px;align-items:start}}
.grid2>*,.grid2b>*,.pnbody>*{{min-width:0}}
.tscroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
details summary{{cursor:pointer;font-size:11px;color:{C['brand']};margin-top:10px;font-weight:600}}
details table{{margin-top:8px;font-size:11px}}

/* header - the brand block */
.hdr{{background:linear-gradient(135deg,{C['brand']} 0%,#0A2E6E 100%);border-radius:18px;
 padding:26px 28px;display:flex;align-items:center;gap:20px;margin-bottom:14px;
 position:relative;overflow:hidden;box-shadow:0 2px 14px rgba({NAVY_RGB},.28)}}
.hdr:before{{content:"";position:absolute;left:0;top:0;bottom:0;width:7px;background:#A3BFE3}}
.hdr h1{{font-size:26px;font-weight:800;letter-spacing:-.025em;line-height:1.12;color:#fff;
 text-wrap:balance}}
.hdr h1 span{{color:{C['brand']};background:#fff;padding:0 8px;border-radius:5px;margin:0 2px}}
.hdr .stamp{{font-size:12px;color:rgba(255,255,255,.74);margin-top:6px}}
.verdict{{font-size:13.5px;color:rgba(255,255,255,.94);margin-top:9px;font-weight:650}}
.verdict b{{color:#CFE0FF;font-weight:800}}
.rfb{{font:inherit;font-size:11px;font-weight:700;letter-spacing:.04em;color:#fff;
 background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.34);border-radius:20px;
 padding:3px 10px 3px 8px;margin-left:10px;cursor:pointer;vertical-align:middle;
 transition:background .15s,border-color .15s}}
.rfb:hover{{background:rgba(255,255,255,.2);border-color:rgba(255,255,255,.6)}}
.rfb:disabled{{cursor:default;opacity:.75}}
.rfb:focus-visible{{outline:2px solid #fff;outline-offset:2px}}
.rfi{{display:inline-block;font-size:13px;line-height:1;margin-right:2px}}
.rfb.spin .rfi{{animation:rfspin 1s linear infinite}}
@keyframes rfspin{{to{{transform:rotate(360deg)}}}}
@media(prefers-reduced-motion:reduce){{.rfb.spin .rfi{{animation:none}}}}
.rfmsg{{display:inline-block;font-size:11.5px;color:rgba(255,255,255,.8);margin-left:8px;
 vertical-align:middle}}
.rfmsg.ok{{color:#9BEBC0;font-weight:600}} .rfmsg.bad{{color:#FFCE85;font-weight:600}}
@media(max-width:560px){{.rfmsg{{display:block;margin:5px 0 0}}}}
.hdrright{{margin-left:auto;display:flex;align-items:center;gap:18px}}
.hdr .rec{{text-align:right;color:#fff}}
.hdr .rec b{{font-size:34px;font-weight:800;letter-spacing:-.03em;
 font-variant-numeric:tabular-nums;display:block;line-height:1}}
.hdr .rec div{{font-size:11px;color:rgba(255,255,255,.72);letter-spacing:.08em;
 text-transform:uppercase}}
.hdr .rec .divline{{text-transform:none;letter-spacing:0;margin-top:4px}}
.mom{{flex:none;min-width:118px;padding:9px 13px;border-radius:12px;text-align:right;
 background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.18)}}
.momtop{{display:flex;align-items:baseline;justify-content:flex-end;gap:5px}}
.momarr{{font-size:11px;line-height:1}}
.momidx{{font-size:23px;font-weight:800;letter-spacing:-.02em;line-height:1;
 font-variant-numeric:tabular-nums}}
.momlab{{font-size:10px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;margin-top:3px}}
.momsub{{font-size:9.5px;color:rgba(255,255,255,.66);margin-top:3px;white-space:nowrap}}
.mom-hot .momidx,.mom-hot .momlab,.mom-hot .momarr{{color:#5BE49B}}
.mom-warm .momidx,.mom-warm .momlab,.mom-warm .momarr{{color:#9BEBC0}}
.mom-flat .momidx,.mom-flat .momlab,.mom-flat .momarr{{color:rgba(255,255,255,.86)}}
.mom-cool .momidx,.mom-cool .momlab,.mom-cool .momarr{{color:#FFCE85}}
.mom-icy .momidx,.mom-icy .momlab,.mom-icy .momarr{{color:#FFAE6B}}
.momchg{{margin-left:6px;font-size:9.5px;font-weight:800}}
.momchg.up{{color:#5BE49B}} .momchg.down{{color:#FFAE6B}} .momchg.flat{{color:rgba(255,255,255,.6)}}
@media(max-width:700px){{.hdrright{{gap:12px}} .mom{{min-width:0;padding:7px 10px}} .momsub{{display:none}}}}

/* ---- next game + staleness: the two things a fan checks first ---- */
.next{{display:flex;align-items:center;gap:18px;flex-wrap:wrap;background:{C['card']};
 border:1px solid rgba({NAVY_RGB},.10);border-left:5px solid {C['brand']};border-radius:12px;
 padding:11px 16px;margin-bottom:12px;box-shadow:0 1px 2px rgba({NAVY_RGB},.04),0 6px 18px -12px rgba({NAVY_RGB},.2)}}
.nxwhen b{{display:block;font-size:10px;letter-spacing:.12em;text-transform:uppercase;
 color:{C['brand']};font-weight:800}}
.nxwhen span{{font-size:12.5px;color:{C['ink2']};font-variant-numeric:tabular-nums}}
.nxmatch{{font-size:18px;font-weight:800;color:{C['navy']};letter-spacing:-.01em}}
.nxodds{{margin-left:auto;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;
 font-size:12.5px;font-variant-numeric:tabular-nums;font-weight:700}}
.nxw{{color:{C['good']}}} .nxl{{color:{C['bad']}}}
.nxswing{{font-size:10.5px;color:{C['mute']};font-weight:700;letter-spacing:.04em}}
.next.live .nxwhen b{{animation:pulse 1.6s ease-in-out infinite}}
@keyframes pulse{{50%{{opacity:.45}}}}
.rec{{color:{C['mute']};font-size:11px;margin-left:3px}}
.stale{{background:#FFF4E5;border:1px solid #F1C88A;color:#7A4B00;border-radius:10px;
 padding:10px 14px;font-size:12.5px;margin-bottom:12px;line-height:1.45}}
.stale b{{color:#5C3800}}
@media(max-width:560px){{.next{{gap:10px;padding:10px 12px}} .nxmatch{{font-size:16px}}
 .nxodds{{margin-left:0;width:100%;gap:10px}}}}

/* ---- section nav ---- */
.snav{{position:sticky;top:0;z-index:30;display:flex;gap:6px;overflow-x:auto;
 background:rgba(238,242,248,.93);backdrop-filter:blur(8px);padding:9px 2px;margin-bottom:14px;
 border-bottom:1px solid {C['grid']};scrollbar-width:none}}
.snav::-webkit-scrollbar{{display:none}}
.snav a{{flex:none;font-size:11.5px;font-weight:650;color:{C['ink2']};background:rgba(255,255,255,.7);
 border:1px solid rgba({NAVY_RGB},.10);border-radius:999px;padding:6.5px 13px;text-decoration:none;
 white-space:nowrap;transition:background .18s,color .18s,border-color .18s}}
.snav a:hover,.snav a:focus-visible,.snav a.act{{background:{C['brand']};color:#fff;
 border-color:{C['brand']};outline:none}}
[id]{{scroll-margin-top:62px}}

/* ---- the control panel: what you touch is navy and solid; model data is steel blue ---- */
.panel{{background:{C['card']};border:1px solid rgba({NAVY_RGB},.26);border-radius:18px;
 padding:20px 24px 22px;margin-bottom:16px;position:relative;overflow:hidden;
 box-shadow:0 1px 2px rgba({NAVY_RGB},.05),0 10px 30px -14px rgba({NAVY_RGB},.34)}}
.panel:before{{content:"";position:absolute;left:0;right:0;top:0;height:3px;
 background:linear-gradient(90deg,{C['input']},{C['blue']})}}
.pnhead{{display:flex;align-items:center;gap:10px;margin-bottom:4px}}
.pnhead h2{{margin-bottom:0}}
.livetag{{font-size:9.5px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
 color:#fff;background:{C['input']};padding:3px 8px;border-radius:20px}}
.pnbody{{display:grid;grid-template-columns:250px 1fr;gap:26px;align-items:start;margin-top:14px}}
.pnodds{{border-right:1px solid {C['grid']};padding-right:22px}}
.big{{font-size:64px;font-weight:800;letter-spacing:-.035em;line-height:1;color:{C['brand']}}}
.big small{{font-size:25px;font-weight:700}}
.oddscap{{font-size:11px;color:{C['mute']};letter-spacing:.04em;margin-top:2px}}
.meter{{height:7px;border-radius:4px;background:{C['card2']};overflow:hidden;margin:12px 0 9px}}
.mfill{{height:100%;border-radius:4px;background:{C['blue']};width:0;
 transition:width .42s cubic-bezier(.2,.7,.3,1)}}
.livedelta{{font-size:11.5px;color:{C['mute']};min-height:17px;line-height:1.35}}
.livedelta.up{{color:{C['good']};font-weight:700}} .livedelta.down{{color:{C['bad']};font-weight:700}}
.oddsdelta{{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap;margin-top:7px}}
.chg{{font-size:12.5px;font-weight:800;font-variant-numeric:tabular-nums}}
.chg.up{{color:{C['good']}}} .chg.down{{color:{C['bad']}}} .chg.flat{{color:{C['mute']};font-weight:700}}
.chgwhen{{font-size:10.5px;color:{C['mute']}}}
.sldtop{{display:flex;align-items:baseline;justify-content:space-between;gap:12px}}
.sldval{{font-size:30px;font-weight:800;letter-spacing:-.02em;color:{C['input']};
 font-variant-numeric:tabular-nums}}
.sldcap{{font-size:11px;color:{C['mute']};letter-spacing:.05em;text-transform:uppercase;
 font-weight:700;margin-left:7px}}
.sldpace{{font-size:11.5px;color:{C['ink2']}}}
.sldwrap{{position:relative;margin:6px 0 30px}}
input[type=range].sld{{-webkit-appearance:none;appearance:none;width:100%;height:34px;
 background:transparent;cursor:pointer;display:block;margin:0}}
input[type=range].sld:focus{{outline:none}}
input[type=range].sld::-webkit-slider-runnable-track{{height:14px;border-radius:7px;
 border:1px solid rgba({NAVY_RGB},.2);background:linear-gradient(90deg,{C['input']} 0%,
 {C['input']} var(--fill,50%),{C['card2']} var(--fill,50%),{C['card2']} 100%)}}
input[type=range].sld::-webkit-slider-thumb{{-webkit-appearance:none;appearance:none;width:32px;
 height:32px;border-radius:50%;background:{C['input']};border:4px solid #fff;
 box-shadow:0 2px 8px rgba({NAVY_RGB},.45);margin-top:-10px}}
input[type=range].sld:focus-visible::-webkit-slider-thumb{{box-shadow:0 0 0 4px rgba({BLUE_RGB},.4)}}
input[type=range].sld::-moz-range-track{{height:14px;border-radius:7px;background:{C['card2']};
 border:1px solid rgba({NAVY_RGB},.2)}}
input[type=range].sld::-moz-range-progress{{height:14px;border-radius:7px;background:{C['input']}}}
input[type=range].sld::-moz-range-thumb{{width:28px;height:28px;border-radius:50%;
 background:{C['input']};border:4px solid #fff;box-shadow:0 2px 8px rgba({NAVY_RGB},.45)}}
.sldticks{{position:relative;height:14px;margin-top:-2px}}
.tick{{position:absolute;transform:translateX(-50%);font-size:10px;color:{C['mute']};
 white-space:nowrap;padding-top:8px}}
.tick i{{position:absolute;top:0;left:50%;width:1px;height:6px;background:{C['axis']}}}
.tick.need{{color:{C['brand']};font-weight:800}}
.tick.need i{{background:{C['brand']};width:2px;height:9px}}
.tick.end{{transform:translateX(-100%)}} .tick.end i{{left:auto;right:0}}
.tick.start{{transform:none}} .tick.start i{{left:0}}
.presets{{display:flex;flex-wrap:wrap;gap:7px;margin-top:2px}}
.ps{{font:inherit;font-size:11.5px;font-weight:700;color:{C['brand']};background:#fff;
 border:1.5px solid rgba({NAVY_RGB},.28);border-radius:20px;padding:7px 14px;cursor:pointer;
 transition:all .13s}}
.ps:hover{{background:{C['input']};color:#fff;border-color:{C['input']};transform:translateY(-1px)}}
.pnread{{display:flex;flex-wrap:wrap;align-items:flex-end;gap:22px;margin-top:16px;padding-top:14px;
 border-top:1px solid {C['grid']}}}
.sv{{display:block;font-size:22px;font-weight:800;letter-spacing:-.02em;color:{C['navy']};
 font-variant-numeric:tabular-nums}}
.sl{{display:block;font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:{C['mute']};
 margin-top:2px}}
.perf{{margin-left:auto;font-size:10px;color:{C['mute']};font-variant-numeric:tabular-nums}}

/* ---- what it takes ---- */
.statv{{font-size:40px;font-weight:800;letter-spacing:-.03em;line-height:1.05;color:{C['navy']}}}
.statl{{font-size:11.5px;color:{C['ink2']};margin-top:7px}}
.facts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:9px;margin-top:13px}}
.fact{{background:{C['card2']};border-radius:8px;padding:10px 11px}}
.factv{{font-size:19px;font-weight:800;color:{C['navy']};line-height:1.1;font-variant-numeric:tabular-nums}}
.factl{{font-size:10px;color:{C['mute']};text-transform:uppercase;letter-spacing:.04em;
 font-weight:700;margin-top:5px}}
.factn{{font-size:11px;color:{C['ink2']};margin-top:6px;line-height:1.38}}
.pill{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
 padding:4px 9px;border-radius:20px;background:{C['card2']};color:{C['brand']};margin-top:10px}}

/* ---- the race table ---- */
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:{C['mute']};
 text-align:left;font-weight:700;padding:0 6px 8px}}
th.r,td.r{{text-align:right}}
td{{padding:6px 6px;border-top:1px solid {C['grid']};font-variant-numeric:tabular-nums}}
tr.grp td{{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;font-weight:800;
 color:{C['brand']};padding:10px 6px 4px;border-top:none}}
tr.focus td{{background:rgba({BLUE_RGB},.12)}}
tr.focus td:first-child{{box-shadow:inset 3px 0 0 {C['brand']}}}
tr.cut td{{border-bottom:2px solid {C['navy']}}}
.cutlab{{font-size:9.5px;letter-spacing:.1em;color:{C['navy']};font-weight:800;
 text-transform:uppercase;padding:4px 6px 1px}}
td.pos{{color:{C['mute']};font-size:10.5px;font-weight:700;width:34px}}
.tm{{font-weight:800;color:{C['navy']}}}
.tmn{{font-weight:500;color:{C['ink2']};margin-left:7px;font-size:11.5px}}
td.pts{{font-weight:800;color:{C['navy']}}}
.rdpos{{color:{C['good']};font-weight:600}} .rdneg{{color:{C['bad']};font-weight:600}}
.oddsbar{{display:flex;align-items:center;gap:7px}}
.obt{{flex:1;height:6px;border-radius:3px;background:{C['card2']};overflow:hidden;min-width:40px}}
.obf{{height:100%;border-radius:3px;background:{C['blue']};transition:width .4s}}
.obn{{width:38px;text-align:right;font-size:11.5px;color:{C['ink2']}}}
.sos{{display:inline-block;min-width:42px;padding:2px 6px;border-radius:5px;font-size:11px;
 font-weight:700;text-align:center}}
.sosna{{color:{C['axis']}}}

/* ---- scoreboard watching: hot/cold are inputs, so their active state is navy and solid ---- */
.deprow{{display:flex;align-items:center;gap:10px;margin-bottom:9px}}
.depname{{width:36px;font-weight:800;font-size:12px;color:{C['navy']}}}
.depctl{{display:inline-flex;gap:4px;flex:none}}
.db{{font:inherit;font-size:9.5px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;
 color:{C['ink2']};background:#fff;border:1.5px solid rgba({NAVY_RGB},.22);border-radius:6px;
 padding:3px 8px;cursor:pointer;transition:all .12s}}
.db:hover{{border-color:{C['input']};color:{C['input']}}}
.db.on{{background:{C['input']};border-color:{C['input']};color:#fff}}
.deptrack{{flex:1;height:8px;background:{C['card2']};border-radius:4px;overflow:hidden}}
.depbar{{height:100%;border-radius:4px}}
.depnum{{font-size:11px;color:{C['ink2']};width:104px;text-align:right;font-variant-numeric:tabular-nums}}
.arrow{{color:{C['mute']}}}
.ensrow{{display:flex;align-items:center;gap:10px;margin-bottom:7px;font-size:11.5px}}
.enslab{{width:240px;color:{C['ink2']}}}
.enslab em{{color:{C['brand']};font-style:normal;font-weight:700;font-size:10px}}
.enstrack{{flex:1;height:2px;background:{C['grid']};position:relative}}
.ensdot{{position:absolute;top:-4px;width:10px;height:10px;border-radius:50%;background:{C['mute']};
 margin-left:-5px;border:2px solid {C['card']}}}
.ensdot.p{{background:{C['brand']};width:14px;height:14px;top:-6px;margin-left:-7px}}
.ensval{{width:44px;text-align:right;font-variant-numeric:tabular-nums;color:{C['navy']};font-weight:600}}

/* ---- around the league ---- */
.algrid{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:4px}}
.alhead{{font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:{C['mute']};
 margin-bottom:9px;padding-bottom:6px;border-bottom:1px solid {C['grid']}}}
.alrow{{display:flex;align-items:center;gap:9px;margin-bottom:7px;font-size:12px}}
.aldate{{width:44px;flex:none;color:{C['mute']};font-size:11px}}
.almatch{{width:112px;flex:none;color:{C['ink2']};font-weight:700;white-space:nowrap}}
.almatch i{{font-style:normal;font-weight:400;color:{C['mute']};font-size:11px}}
.alroot{{color:{C['brand']};font-weight:800;box-shadow:inset 0 -2px 0 rgba({BLUE_RGB},.5)}}
.alh2h{{display:block;font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:{C['mute']}}}
.altrack{{flex:1;height:7px;background:{C['card2']};border-radius:4px;overflow:hidden;min-width:30px}}
.albar{{height:100%;border-radius:4px;background:{C['blue']}}}
.alnum{{width:32px;text-align:right;font-size:11px;color:{C['ink2']};font-variant-numeric:tabular-nums}}
.alrow.toss .almatch{{color:{C['mute']};font-weight:600}} .alrow.toss .albar{{background:{C['axis']}}}
.alnum.tossl{{width:46px;font-size:9.5px;color:{C['mute']};font-weight:700;text-transform:uppercase}}
.alempty{{font-size:11.5px;color:{C['mute']}}}

/* ---- the bracket: sixteen clubs, both conferences, the Final in the middle.
   Every column spaces its matchups evenly (space-around), so a round's matchups sit
   exactly between the two that feed them. ---- */
.bkhead{{font-size:14px;color:{C['ink2']};margin-bottom:14px;line-height:1.45}}
.bkhead b{{color:{C['navy']};font-weight:800}}
.bkroad{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px;
 padding-bottom:18px;border-bottom:1px solid {C['grid']}}}
.bkrd{{display:flex;flex-direction:column;gap:6px}}
.bkrdl{{font-size:10px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:{C['mute']}}}
.bkrdt{{height:7px;border-radius:4px;background:{C['card2']};overflow:hidden}}
.bkrdf{{height:100%;border-radius:4px;background:{C['blue']};transition:width .45s cubic-bezier(.2,.7,.3,1)}}
.bkrdv{{font-size:18px;font-weight:800;color:{C['navy']};letter-spacing:-.02em;
 font-variant-numeric:tabular-nums;line-height:1}}
.bk{{min-width:880px}}
.bkgridh,.bkgrid{{display:grid;grid-template-columns:repeat(3,1fr) 1.15fr repeat(3,1fr)}}
.bkgridh span{{font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
 color:{C['mute']};padding:0 8px 7px;border-bottom:1px solid {C['grid']};white-space:nowrap}}
.bkgridh span.c{{text-align:center;color:{C['brand']}}} .bkgridh span.rt{{text-align:right}}
.bkgrid{{margin-top:12px;min-height:440px}}
.bkcol{{display:flex;flex-direction:column;justify-content:space-around;padding:0 8px;min-width:0}}
.bkcol.fin{{justify-content:center;gap:10px}}
.bkgrp{{position:relative;display:flex;flex-direction:column;gap:4px}}
.bkconf{{font-size:8.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
 color:{C['mute']};text-align:center;margin-bottom:1px}}
.bkcol.e .bkgrp.link:before{{content:"";position:absolute;right:-8px;top:17px;bottom:17px;
 width:2px;background:{C['axis']};border-radius:1px}}
.bkcol.e .bkgrp.link:after{{content:"";position:absolute;right:-16px;top:50%;width:8px;
 height:2px;background:{C['axis']}}}
.bkcol.w .bkgrp.link:before{{content:"";position:absolute;left:-8px;top:17px;bottom:17px;
 width:2px;background:{C['axis']};border-radius:1px}}
.bkcol.w .bkgrp.link:after{{content:"";position:absolute;left:-16px;top:50%;width:8px;
 height:2px;background:{C['axis']}}}
.bknode{{position:relative;display:flex;align-items:center;gap:6px;padding:7px 9px;border-radius:8px;
 background:{C['card2']};border:1.5px solid transparent;overflow:hidden;transition:border-color .25s}}
.bkfill{{position:absolute;left:0;top:0;bottom:0;background:rgba({BLUE_RGB},.14);
 transition:width .45s cubic-bezier(.2,.7,.3,1)}}
.bkseed,.bkteam,.bkpct{{position:relative}}
.bkseed{{width:20px;flex:none;font-size:9px;font-weight:800;color:{C['mute']}}}
.bkteam{{font-size:13px;font-weight:800;color:{C['navy']}}}
.bkpct{{margin-left:auto;font-size:10.5px;color:{C['ink2']};font-variant-numeric:tabular-nums}}
.bknode.you{{border-color:{C['brand']}}}
.bknode.you .bkfill{{background:rgba({BLUE_RGB},.26)}}
.bknode.you .bkseed,.bknode.you .bkteam{{color:{C['brand']}}}
.bknode.champ{{background:{C['navy']};padding:12px 11px}}
.bknode.champ .bkteam{{color:#fff;font-size:16px}}
.bknode.champ .bkpct{{color:rgba(255,255,255,.72)}}
.bknode.champ .bkfill{{background:rgba(255,255,255,.14)}}
.bknode.champ.you{{background:{C['blue']}}}
@media(max-width:760px){{
 .bk{{min-width:0}} .bkgridh{{display:none}}
 .bkgrid{{grid-template-columns:1fr;gap:16px;min-height:0}}
 .bkcol{{padding:0;justify-content:flex-start;gap:8px}}
 .bkcol:before{{content:attr(data-round);font-size:9.5px;font-weight:800;letter-spacing:.09em;
  text-transform:uppercase;color:{C['mute']};padding-bottom:6px;border-bottom:1px solid {C['grid']}}}
 .bkcol.mhide{{display:none}}
 .bkgrp.link:before,.bkgrp.link:after{{display:none}}
 .bkroad{{grid-template-columns:1fr 1fr}}
}}

/* ---- calendar + must-see ---- */
.ms{{background:{C['card']};border:1px solid rgba({NAVY_RGB},.16);border-radius:14px;padding:18px 20px;
 position:relative;overflow:hidden;margin-bottom:16px}}
.ms:before{{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:{C['brand']}}}
.cwrap{{display:flex;gap:16px;flex-wrap:wrap;margin-top:4px}}
.cmon{{flex:1 1 260px;min-width:236px}}
.cmname{{font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:{C['mute']};margin-bottom:7px}}
.cgrid{{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}}
.cdow{{font-size:9px;font-weight:700;color:{C['axis']};text-align:center;padding-bottom:2px}}
.cday{{aspect-ratio:1;border-radius:6px;position:relative;overflow:hidden;display:flex;
 flex-direction:column;align-items:center;justify-content:center}}
.cday.out{{background:transparent}} .cday.off{{background:{C['card2']}}}
.cday i{{position:absolute;top:2px;left:4px;font-style:normal;font-size:8.5px;font-weight:700;opacity:.62}}
.cday.off i{{color:{C['axis']};opacity:1}}
.cday b{{font-size:10.5px;font-weight:800;letter-spacing:-.02em;margin-top:5px}}
.cday.key{{box-shadow:inset 0 0 0 2.5px #FFFFFF,inset 0 0 0 4px {C['brand']}}}
.cday.game{{cursor:pointer}}
.ccap{{font-size:11.5px;color:{C['ink2']};margin-top:10px;min-height:17px}}
.cleg{{display:flex;align-items:center;gap:9px;margin-top:12px;flex-wrap:wrap;font-size:10.5px;color:{C['mute']}}}
.clramp{{display:flex;gap:2px}} .clramp span{{width:17px;height:9px;border-radius:2px}}
.mstile{{display:flex;align-items:center;gap:14px;padding:11px 0;border-top:1px solid {C['grid']}}}
.mstile:first-of-type{{border-top:none}}
.msrank{{width:26px;height:26px;flex:none;border-radius:7px;background:{C['brand']};color:#fff;
 font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center}}
.msbody{{flex:1}}
.msdate{{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:{C['mute']};font-weight:700}}
.msmatch{{font-size:16px;font-weight:800;margin:1px 0 3px;color:{C['navy']}}}
.mswhy{{font-size:11.5px;color:{C['ink2']};line-height:1.4}}
.msswing{{text-align:right;flex:none;width:78px}}
.msswing b{{font-size:20px;font-weight:800;color:{C['brand']};letter-spacing:-.02em}}
.msswing span{{display:block;font-size:9px;color:{C['mute']};letter-spacing:.05em;text-transform:uppercase;
 line-height:1.3;margin-top:2px}}

/* ---- footer ---- */
.foot{{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;
 margin-top:20px;padding-top:15px;border-top:1px solid {C['grid']}}}
.byline{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:{C['mute']};font-weight:600}}
.byline b{{color:{C['brand']};font-weight:800}}
.footmeta{{font-size:10.5px;color:{C['mute']};line-height:1.6;text-align:right;flex:1;min-width:220px}}

@media(max-width:840px){{
 .grid2,.grid2b{{grid-template-columns:1fr}}
 .pnbody{{grid-template-columns:1fr;gap:18px}}
 .pnodds{{border-right:none;border-bottom:1px solid {C['grid']};padding:0 0 14px}}
 .hdr{{flex-wrap:wrap}} .hdrright{{margin-left:0}}
 .algrid{{grid-template-columns:1fr;gap:18px}}
 .enslab{{width:150px}}
}}
@media(max-width:560px){{
 body{{padding:10px}}
 .panel{{padding:15px 14px 18px}} .card,.ms,.hdr{{padding:15px 14px}}
 .big{{font-size:54px}} .sldval{{font-size:25px}} .sldpace{{display:none}}
 .pnread{{gap:16px}} .perf{{margin-left:0;width:100%}}
 .hdr h1{{font-size:20px}} .hdr .rec b{{font-size:25px}} .statv{{font-size:34px}}
 table{{font-size:11.5px}} td{{padding:6px 4px}} th{{padding:0 4px 7px}}
 .hide-s{{display:none}} .tmn{{display:none}}
 .depnum{{width:88px;font-size:10px}} .enslab{{width:128px;font-size:10.5px}}
 .msswing{{width:62px}} .msswing b{{font-size:17px}} .msmatch{{font-size:15px}}
 .facts{{grid-template-columns:1fr}} .cmon{{flex:1 1 100%}}
 .snav a{{font-size:11px;padding:5px 10px}}
 .foot{{flex-direction:column;align-items:flex-start}} .footmeta{{text-align:left}}
}}
</style></head><body><div class="wrap">

<div class="hdr">
  <div>
    <h1>TORONTO <span>MAPLE LEAFS</span> &mdash; PLAYOFF TRACKER</h1>
    <div class="stamp">{"Preseason" if PRESEASON else f"Standings through {STAMP}"} &middot;
      {R['nsim']:,} simulated seasons &middot; <span id="updAgo" data-utc="{GENERATED_UTC}"></span>
      <button type="button" id="refreshBtn" class="rfb"
              title="Check the NHL for games that have finished since this page was published"
              aria-label="Refresh data"><span class="rfi" aria-hidden="true">&#8635;</span> Refresh</button>
      <button type="button" id="shareBtn" class="rfb" title="Share the current odds"
              aria-label="Share"><span aria-hidden="true">&#8599;</span> Share</button>
      <span id="refreshMsg" class="rfmsg" aria-live="polite"></span></div>
    {verdict_html}
  </div>
  <div class="hdrright">
    <div class="rec">
      <b>{W}&ndash;{L}&ndash;{OTL}</b>
      <div>{rec_line}</div>
      <div class="divline">{div_line}</div>
    </div>
    {momentum_badge}
  </div>
</div>

<div class="stale" id="stale" role="status" hidden></div>
{next_html}
<nav class="snav" aria-label="Jump to section">{nav_html}</nav>

<div class="panel" id="play">
  <div class="pnhead">
    <h2>Play it out <span class="sub">&mdash; drag the slider to set how many points {THE} take from here</span></h2>
    <span class="livetag">live</span>
  </div>
  <div class="pnbody">
    <div class="pnodds">
      <div class="big"><span id="liveOdds">{ODDS * 100:.1f}</span><small>%</small></div>
      <div class="oddscap">chance of a playoff spot</div>
      {odds_delta_html}
      <div class="meter"><div class="mfill" id="liveBar" style="width:{ODDS * 100:.1f}%"></div></div>
      <div class="livedelta" id="liveDelta" aria-live="polite">model baseline &mdash; nothing set yet</div>
    </div>
    <div class="pnctl">
      <div class="sldtop">
        <div><span class="sldval" id="sliderVal">&mdash;</span>
             <span class="sldcap">rest-of-season points</span></div>
        <div class="sldpace" id="sliderPace"></div>
      </div>
      <div class="sldwrap">
        <input type="range" class="sld" id="ptsSlider" min="0" max="{2 * GL}" step="1"
               value="{int(round(PROJ - PTS))}"
               aria-label="Rest-of-season points for the {NICK}, out of {2 * GL}">
        <div class="sldticks">
{ticks_html}
        </div>
      </div>
      <div class="presets">
        <button type="button" data-preset="reset" class="ps">Reset</button>
        <button type="button" data-preset="min" class="ps">Bare minimum</button>
        <button type="button" data-preset="0.55" class="ps">.550 pace</button>
        <button type="button" data-preset="0.62" class="ps">.620 &mdash; contender</button>
        <button type="button" data-preset="0.45" class="ps">Slump (.450)</button>
      </div>
      <div class="pnread">
        <div><span class="sv" id="liveProj">{PROJ:.1f}</span><span class="sl">projected points</span></div>
        <div><span class="sv" id="liveCut">{R['cut_pts']['mean']:.1f}</span><span class="sl">cut line</span></div>
        <div><span class="sv" id="liveCup">{ODDS * (BK['road']['cup'] if BK else 0) * 100:.1f}%</span><span class="sl">win the Cup</span></div>
        <div class="perf" id="perfNote">simulating&hellip;</div>
      </div>
    </div>
  </div>
</div>

{trend_section}

<div class="grid1">
  <div class="card" id="takes">
    <h2>What it takes</h2>
    <div class="statv">{NEED} points</div>
    <div class="statl">from {GL} games, to reach <b>{CUT_TARGET}</b> &mdash; the median cut line,
      the second wild card's final total &mdash; a <b>{P['ros_pace']:.3f}</b> points pace.
      {takes_ctx} In the seasons where they qualify they take
      <b>{P['gained_if_qualify']:.1f}</b>, against {P['gained_all']:.1f} across all of them.</div>
    <div class="facts">
      <div class="fact"><div class="factv">{line_v}</div><div class="factl">{line_l}</div>
        <div class="factn">{line_n}</div></div>
      <div class="fact"><div class="factv">{next_v}</div><div class="factl">Next {NN_} games</div>
        <div class="factn">{next_note}</div></div>
      <div class="fact"><div class="factv">{pass_v}</div><div class="factl">Rivals beaten out</div>
        <div class="factn">{pass_note}</div></div>
      <div class="fact"><div class="factv">{pct(R['odds']['division'], 0)}</div>
        <div class="factl">Win the {R['focus_div']}</div>
        <div class="factn">{pct(R['odds']['top3'], 0)} to finish top three in the division,
          {pct(R['odds']['wildcard'], 0)} to get in as a wild card.</div></div>
    </div>
  </div>
</div>

<div class="grid2b">
  <div class="card" id="race">
    <h2>The {CONF_NAME} race <span class="sub">&mdash; three per division, then two wild cards</span></h2>
    <div class="tscroll"><table>
      <thead><tr><th></th><th>Team</th><th class="r">GP</th><th class="r">W&ndash;L&ndash;OTL</th>
        <th class="r">Pts</th><th class="r">GD</th><th class="r hide-s">Rem<br>SOS</th>
        <th class="r hide-s">Proj</th><th>Playoff odds</th></tr></thead>
      <tbody>{race_html}</tbody></table></div>
    <div class="note">{"<b>Preseason:</b> every club is level, so the order is by projected points, not by standings. " if PRESEASON else ""}
      Standings run on points, then games in hand, then regulation wins &mdash; the NHL's own
      order. <b>Rem SOS</b> is what an average club would win against that team's remaining
      opponents; darker is harder. It explains the odds rather than adjusting them: every game
      is already simulated against its real opponent.</div>
  </div>
  <div class="card" id="curve">
    <h2>How many points is enough?</h2>
    <svg viewBox="0 0 {CW} {CH}" width="100%" role="img" aria-label="Probability of a playoff spot by final points">
      {gridlines}
      <polygon points="{area}" fill="{C['blue']}" opacity="0.13"/>
      <polyline points="{pts_line}" fill="none" stroke="{C['blue']}" stroke-width="2"
        stroke-linejoin="round" stroke-linecap="round"/>
      {cutline}{dots}{xticks}
      <line id="scenMark" x1="0" x2="0" y1="{PADT + 26}" y2="{CH - PADB}" stroke="{C['input']}"
        stroke-width="2" style="opacity:0;transition:opacity .3s"/>
      <text id="scenMarkLab" x="0" y="{PADT + 16}" font-size="10" font-weight="800" fill="{C['input']}"
        stroke="#fff" stroke-width="3.5" paint-order="stroke" style="opacity:0;transition:opacity .3s"></text>
      {hover}
      <line x1="{PADL}" x2="{CW - PADR}" y1="{py(0):.1f}" y2="{py(0):.1f}" stroke="{C['axis']}" stroke-width="1"/>
      <text x="{CW / 2:.0f}" y="{CH - 4}" text-anchor="middle" font-size="10" fill="{C['mute']}"
        letter-spacing="1">FINAL POINTS</text>
    </svg>
    <div class="note">{curve_note}</div>
    <details><summary>Show the table</summary>
      <table><thead><tr><th>Final points</th><th class="r">Playoff odds</th></tr></thead><tbody>
        {"".join(f'<tr><td>{p}</td><td class="r">{curve[p][0] * 100:.1f}%</td></tr>' for p in xs)}
      </tbody></table></details>
  </div>
</div>

<div class="grid2">
  <div class="card" id="watch">
    <h2>Scoreboard watching <span class="sub">&mdash; who to root against</span></h2>
    {dep_rows}
    <div class="note">Bar length is how much {THE}' odds move between a rival's cold finish
      (25th percentile) and hot one (75th). <b>Tap cold or hot</b> to force that finish in the
      live simulator &mdash; the big number, the odds bars and the bracket all re-run with it.
      Tap again to release. {dep_note} These bars are about how a club <i>finishes</i>; for a
      single game, see <a href="#around" style="color:{C['brand']};font-weight:700">Around the league</a>.</div>
  </div>
  <div class="card">
    <h2>Model sensitivity <span class="sub">&mdash; is {pct(ODDS, 0)} real?</span></h2>
    {ens_rows}
    <div class="note">Ten specifications, varying how much goal differential counts against the
      record, how much last season still counts, how hard strength is regressed, home ice, and
      how often games go past regulation. They land between {pct(LO)} and {pct(HI)}. {ens_verdict}</div>
  </div>
</div>

{around_section}

{bracket_section}

<div class="ms" id="calendar">
  <h2>The next two months <span class="sub">&mdash; every game, shaded by how much it moves the odds</span></h2>
  <div class="cwrap">{cal_html}</div>
  <div class="ccap" id="calCap" aria-live="polite">Tap any game for the odds either way.</div>
  <div class="cleg"><span>Lower leverage</span><span class="clramp">{ramp_legend}</span>
    <span>Higher</span><span>&middot; outlined: the five that matter most &middot; <b>@</b> marks a road game</span></div>
  <h2 style="margin-top:22px">Must-see games</h2>
  {mustsee_rows}
</div>

<div class="note">
<b>Method.</b> Team strength is the probability of beating an average club: goal-based
Pythagorean win% (exponent 2.1) blended 70/30 with actual win%, pooled across last season and
this one, then regressed toward .500. Last season counts as {M.PRIOR_WEIGHT:.0f} games, so it
carries a preseason projection on its own and fades as this season's games arrive. Every remaining game on the real NHL schedule
&mdash; {D.SEASON_GAMES} per club this season &mdash; is simulated with a log5 matchup plus home ice
(home sides won {R['league']['home_win'] * 100:.1f}% last season). A separate draw decides whether the
game went past regulation ({R['league']['p_ot'] * 100:.1f}% did last season), which is what gives the
loser a point. Standings run on points, then regulation wins, then a coin; head-to-head, the
NHL's later tiebreakers, is not modelled. {R['nsim']:,} seasons, both conferences, full
playoff field. <b>The live panel</b> re-runs the {CONF_NAME} Conference in your browser
(5,000 seasons a change). <b>Known limits:</b> the model knows goals and results, not injuries,
goaltending changes or the trade deadline. Data: NHL public API.
</div>

<div class="foot">
  <div class="byline">Built by <b>AV</b></div>
  <div class="footmeta">Generated <span id="genET">{GENERATED_UTC.replace('T', ' ').rstrip('Z')} UTC</span> &middot;
    rebuilt automatically as games finish &middot;
    not affiliated with or endorsed by the Toronto Maple Leafs or the NHL</div>
</div>

</div>
{LIVE_JS}<script>window.__SIM__={SIMJSON};</script>
<script>{APPJS}</script>
</body></html>"""

open("tracker.html", "w").write(HTML)
print(f"wrote tracker.html ({len(HTML):,} bytes)")
