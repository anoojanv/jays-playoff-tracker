"""
Build the page for a season that is already decided.

Almost every number on the page is conditional on the Blue Jays qualifying — series
targets, per-game leverage, rival dependency, the shape of the win curve. When the race
stops being a race those conditionals degenerate, and the page used to die on them:

  * clinched  -> every series swing is identical, so normalising by (max - min) divided
                 by zero in three places
  * eliminated -> not one of the 120,000 simulated seasons qualifies, every conditional
                 mean is NaN, and int(ceil(NaN)) raised ValueError

Both are guaranteed to happen to somebody every September, and they arrive exactly when
the build must keep publishing rather than go red. This drives a real build for each.

Run:  python tests/test_endgame.py
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
FIXTURE = os.path.join(HERE, "fixture_data.json")

# (label, wins, losses) for Toronto, holding games-played at 123 so the schedule still
# reconciles to 162 and only the shape of the race changes
CASES = [
    ("in the thick of it", 67, 56),
    ("clinched — nothing left to decide", 118, 5),
    ("mathematically eliminated", 12, 111),
]


def build(w, l, workdir):
    """Run the real pipeline against a doctored fixture; return (ok, tail_of_output)."""
    data = json.load(open(FIXTURE))
    data["AL"]["Blue Jays"][0] = w
    data["AL"]["Blue Jays"][1] = l
    os.makedirs(os.path.join(workdir, "build"), exist_ok=True)
    json.dump(data, open(os.path.join(workdir, "build", "data.json"), "w"))

    # sim_state.npz is keyed on the data fingerprint, which these edits do not change,
    # so a stale cache would silently feed the previous case's seasons to analyze.py
    for junk in ("sim_state.npz", "results.json", "path.json",
                 "ensemble.json", "simdata.json", "tracker.html"):
        try:
            os.remove(os.path.join(SRC, junk))
        except FileNotFoundError:
            pass

    r = subprocess.run([sys.executable, os.path.join(SRC, "build.py"), "--no-fetch"],
                       cwd=workdir, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr)[-1400:]


def main():
    # build.py resolves build/ and public/ relative to src/, so this has to run in the
    # real tree; put back whatever data.json was there when we finish
    real_build = os.path.join(ROOT, "build", "data.json")
    saved = open(real_build).read() if os.path.exists(real_build) else None

    fails = []
    try:
        for label, w, l in CASES:
            ok, tail = build(w, l, ROOT)
            page = os.path.join(ROOT, "public", "index.html")
            size = os.path.getsize(page) if ok and os.path.exists(page) else 0
            print(f"--- Blue Jays {w}-{l}: {label}")
            if ok and size > 30_000:
                print(f"    build OK, {size/1024:.0f} KB published")
            else:
                print("    FAILED")
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
