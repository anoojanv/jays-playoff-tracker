"""
Build the page in every state a season passes through.

Almost every number on the page is conditional on the Leafs qualifying: the bracket,
per-game leverage, rival dependency, the shape of the points curve. At the edges those
conditionals degenerate:

  * preseason   -> every club on zero, no recent form, no momentum, no standings to rank
  * clinched    -> every swing is identical, so anything normalised by (max - min)
                   divides by zero
  * eliminated  -> not one simulated season qualifies, so every conditional mean is NaN

Each is guaranteed to happen to somebody every year, and each arrives exactly when the
build must keep publishing rather than go red. This drives a real build for each.

Run:  python tests/test_endgame.py
"""
import json, os, re, subprocess, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
FIXTURE = os.path.join(HERE, "fixture_data.json")

spec = importlib.util.spec_from_file_location("mf", os.path.join(HERE, "make_fixture.py"))
mf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mf)


def preseason(d):
    """Nothing played: the whole schedule ahead, every club on zero."""
    games = mf.schedule()
    for t in d["TEAMS"].values():
        t.update(w=0, l=0, otl=0, gf=0, ga=0, rw=0)
    d["GAMES"] = sorted([g["date"], g["away"], g["home"]] for g in games)
    d["TIMES"] = {f'{g["date"]}|{g["away"]}|{g["home"]}':
                  {"utc": g["date"] + "T23:00:00Z", "state": "FUT"}
                  for g in games if "TOR" in (g["away"], g["home"])}
    d["RECENT"] = []
    d["preseason"] = True
    d["as_of"] = "2026-10-06"


def record(w, l, otl):
    def edit(d):
        t = d["TEAMS"]["TOR"]
        assert w + l + otl == t["w"] + t["l"] + t["otl"], "must keep games played"
        t.update(w=w, l=l, otl=otl, rw=min(w, t["rw"] + max(0, w - t["w"])))
    return edit


# (label, edit, what the page must say)
CASES = [
    ("preseason — nothing played yet", preseason, "Season opens"),
    ("in the thick of it", None, "Play it out"),
    ("clinched — nothing left to decide", record(50, 0, 0), "all but locked up"),
    ("mathematically eliminated", record(0, 50, 0), "All but out"),
]


def visible(html):
    """The page minus its scripts — isNaN() in the JavaScript is not a bug."""
    return re.sub(r"<script.*?</script>", " ", html, flags=re.S)


def broken(html):
    """A NaN or infinity anywhere outside the scripts: text, a style, a title."""
    return re.search(r"NaN|(?<![a-zA-Z])nan(?![a-zA-Z])|(?<![a-zA-Z])inf%|Infinity",
                     visible(html))


def build(edit):
    """Run the real pipeline against a doctored fixture; return (ok, tail_of_output)."""
    data = json.load(open(FIXTURE))
    if edit:
        edit(data)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    json.dump(data, open(os.path.join(ROOT, "build", "data.json"), "w"))

    # sim_state.npz is keyed on the data fingerprint, which these edits do not change,
    # so a stale cache would silently feed the previous case's seasons downstream
    for junk in ("sim_state.npz", "results.json", "path.json",
                 "ensemble.json", "simdata.json", "tracker.html"):
        try:
            os.remove(os.path.join(SRC, junk))
        except FileNotFoundError:
            pass

    r = subprocess.run([sys.executable, os.path.join(SRC, "build.py"), "--no-fetch"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr)[-1400:]


def main():
    # build.py resolves build/ and public/ from its own location, so this has to run in
    # the real tree; put back whatever data.json was there when we finish
    real_build = os.path.join(ROOT, "build", "data.json")
    saved = open(real_build).read() if os.path.exists(real_build) else None

    fails = []
    try:
        for label, edit, needle in CASES:
            ok, tail = build(edit)
            page = os.path.join(ROOT, "public", "index.html")
            html = open(page, encoding="utf-8").read() if ok and os.path.exists(page) else ""
            print(f"--- {label}")
            if ok and len(html) > 30_000 and needle in html and not broken(html):
                print(f"    build OK, {len(html)/1024:.0f} KB published, says {needle!r}")
            else:
                print("    FAILED" + ("" if not ok else
                                      f" — page lacks {needle!r}" if needle not in html
                                      else " — NaN on the page"))
                print("    " + tail.replace("\n", "\n    ")[-900:])
                fails.append(label)
    finally:
        if saved is not None:
            open(real_build, "w").write(saved)

    print("\n" + "=" * 58)
    if fails:
        print("ENDGAME TEST FAILED for: " + ", ".join(fails))
        return 1
    print(f"ENDGAME TEST PASSED — the page builds in all {len(CASES)} states")
    return 0


if __name__ == "__main__":
    sys.exit(main())
