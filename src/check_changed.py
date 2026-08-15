"""
Cheap change detector — decides whether a full rebuild is worth running.

Fetches the two standings endpoints (about a second), fingerprints every club's record,
and compares that to the fingerprint embedded in the page that is currently published.
The deployed site is therefore its own state file: nothing to persist between runs, and
if a deploy is ever rolled back the next poll notices and rebuilds.

Uses the standard library only — no numpy, no pip install — so a poll that finds nothing
new costs a few seconds of runner time.

Writes `changed=true|false` to $GITHUB_OUTPUT. Fails loudly if MLB is unreachable;
defaults to rebuilding if the live page can't be read, since publishing is the safe error.
"""
import os, re, sys, importlib.util, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SITE_URL", "https://jays-playoff-tracker.netlify.app").rstrip("/")

spec = importlib.util.spec_from_file_location("fd", os.path.join(HERE, "fetch_data.py"))
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)


def live_fingerprint():
    """Read the fingerprint out of the currently-published page."""
    try:
        req = urllib.request.Request(
            SITE + "/?cachebust=" + os.environ.get("GITHUB_RUN_ID", "0"),
            headers={"User-Agent": "jays-tracker-check/1.0", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"  could not read the live page ({e}) — will rebuild to be safe")
        return None
    m = re.search(r'<meta name="data-fingerprint" content="([^"]*)"', html)
    if not m:
        print("  live page has no fingerprint (published before this feature) — rebuilding")
        return None
    return m.group(1)


def main():
    out = []
    if os.environ.get("FORCE_BUILD", "").lower() in ("1", "true", "yes"):
        print("FORCE_BUILD set — rebuilding regardless")
        return emit(True)

    al = fd.standings(103)
    nl = fd.standings(104)
    current = fd.fingerprint(al, nl)
    j = al["Blue Jays"]
    print(f"  MLB now: Blue Jays {j['w']}-{j['l']}  ·  fingerprint {current}")

    live = live_fingerprint()
    if live is not None:
        print(f"  published: fingerprint {live}")

    changed = live != current
    if changed:
        print("\nSomething finished since the last publish — running the full build.")
    else:
        print("\nNo games have finished since the last publish — skipping the build.")
    return emit(changed)


def emit(changed):
    val = "true" if changed else "false"
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as f:
            f.write(f"changed={val}\n")
    print(f"changed={val}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
