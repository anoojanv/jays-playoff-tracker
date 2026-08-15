"""
Run the whole pipeline and write public/index.html.

  python src/build.py              # fetch fresh data, then build
  python src/build.py --no-fetch   # rebuild from the existing build/data.json

Every step is checked. If anything fails the build stops with a non-zero exit code so
the GitHub Actions job goes red and nothing is published.
"""
import os, sys, shutil, subprocess, json, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PUBLIC = os.path.join(ROOT, "public")

STEPS = ["fetch_data.py", "sim.py", "ensemble.py", "analyze.py", "export_sim.py", "build_html.py"]


def run(script):
    print(f"\n=== {script} " + "=" * (58 - len(script)))
    r = subprocess.run([sys.executable, script], cwd=HERE)
    if r.returncode != 0:
        sys.exit(f"\nFAILED at {script} (exit {r.returncode}) — nothing will be published.")


def verify(path):
    """Cheap guards against publishing something broken."""
    html = open(path, encoding="utf-8").read()
    problems = []
    if len(html) < 30_000:
        problems.append(f"suspiciously small ({len(html)} bytes)")
    ext = [u for u in re.findall(r'(?:src|href)="(?!data:|#)([^"]+)"', html)
           if not u.startswith("data:")]
    if ext:
        problems.append(f"external references present: {ext[:5]}")
    low = html.lower()
    for needle in ("winslider", "play it out", "__sim__", "liveodds", "data-preset"):
        if needle not in low:
            problems.append(f"missing expected content: {needle!r}")
    if "localStorage" in html:
        problems.append("uses localStorage")
    # the polling check compares this against the live page; an empty one would make
    # every poll rebuild, silently throwing away the whole point of the cheap check
    fp = re.search(r'<meta name="data-fingerprint" content="([^"]*)"', html)
    if not fp or not fp.group(1).strip():
        problems.append("data fingerprint is missing or empty")
    if problems:
        sys.exit("FAILED verification:\n  - " + "\n  - ".join(problems))
    print(f"  verified: {len(html)/1024:.0f} KB, self-contained, interactive markup present")


def main():
    steps = STEPS if "--no-fetch" not in sys.argv else STEPS[1:]
    for s in steps:
        run(s)

    os.makedirs(PUBLIC, exist_ok=True)
    src = os.path.join(HERE, "tracker.html")
    dst = os.path.join(PUBLIC, "index.html")
    shutil.copy(src, dst)

    print("\n=== verify " + "=" * 54)
    verify(dst)

    d = json.load(open(os.path.join(ROOT, "build", "data.json")))
    r = json.load(open(os.path.join(HERE, "results.json")))
    j = d["AL"]["Blue Jays"]
    print(f"\nBlue Jays {j[0]}-{j[1]} through {d['as_of']} · "
          f"playoff odds {r['odds']['playoff']*100:.1f}%")
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
