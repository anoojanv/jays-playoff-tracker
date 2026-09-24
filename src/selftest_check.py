"""
Offline test for check_changed.py — the polling logic that decides whether to rebuild.

Covers every path through the decision:
  1. nothing has changed since the last publish   -> skip
  2. a game has finished                          -> rebuild
  3. the live page is unreachable                 -> rebuild (publishing is the safe error)
  4. the live page has no fingerprint meta tag    -> rebuild
  5. the live page has a matching fingerprint     -> skip
  6. FORCE_BUILD is set                           -> rebuild regardless

Cases 3-5 drive the real live_fingerprint(), with only the HTTP call stubbed, so the
regex that reads the meta tag out of the published page is genuinely exercised. (It
previously stubbed live_fingerprint() wholesale, which meant cases 3 and 4 were the same
test and the regex was never run at all.)

Run:  python src/selftest_check.py
"""
import os, sys, io, json, contextlib, importlib.util, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

fixture = os.path.join(ROOT, "tests", "fixture_data.json")
if not os.path.exists(fixture):
    sys.exit(f"FATAL: fixture missing: {fixture}\n"
             "  Regenerate it with: python tests/make_fixture.py")
BASE = json.load(open(fixture))

spec = importlib.util.spec_from_file_location("cc", os.path.join(HERE, "check_changed.py"))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

PAGE = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="tracker-id" content="nhl-TOR-20262027">'
        '<meta name="data-fingerprint" content="{fp}">'
        '</head><body>Maple Leafs</body></html>')


def rows_of(teams):
    """The fixture's records, shaped like the NHL's /standings/now rows."""
    return [{"teamAbbrev": {"default": t}, "wins": v["w"], "losses": v["l"],
             "otLosses": v["otl"], "goalFor": v["gf"], "goalAgainst": v["ga"]}
            for t, v in teams.items()]


def standings_stub(teams):
    return lambda: ("20262027", rows_of(teams))


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def urlopen_stub(body):
    """Stand in for the network so the real live_fingerprint() can run against `body`."""
    def _open(req, timeout=None):
        if body is None:
            raise urllib.error.URLError("connection refused")
        return _Resp(body.encode())
    return _open


def run_case(name, teams, expect, live_html, force=False):
    """live_html is the body the published page returns, or None to fail the request."""
    cc.fd.standings_now = standings_stub(teams)
    urllib.request.urlopen = urlopen_stub(live_html)
    os.environ["FORCE_BUILD"] = "true" if force else ""
    os.environ.pop("GITHUB_OUTPUT", None)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cc.main()
    got = "changed=true" in buf.getvalue()
    ok = got == expect
    print(f"--- {name}\n    expected rebuild={expect}, got rebuild={got}  "
          f"{'OK' if ok else 'FAIL'}")
    return ok


_REAL_URLOPEN = urllib.request.urlopen


def main():
    T = {k: dict(v) for k, v in BASE["TEAMS"].items()}
    fp_now = cc.fd.fingerprint(rows_of(T))

    after = {k: dict(v) for k, v in T.items()}         # pretend the Leafs just won one
    after["TOR"]["w"] += 1; after["TOR"]["gf"] += 4; after["TOR"]["ga"] += 2
    after["MTL"]["l"] += 1; after["MTL"]["gf"] += 2; after["MTL"]["ga"] += 4

    try:
        results = [
            run_case("nothing finished since the last publish",
                     T, expect=False, live_html=PAGE.format(fp=fp_now)),
            run_case("a game finished (Leafs win, Canadiens loss)",
                     after, expect=True, live_html=PAGE.format(fp=fp_now)),
            run_case("live page unreachable",
                     T, expect=True, live_html=None),
            run_case("live page predates the fingerprint meta",
                     T, expect=True,
                     live_html="<html><head></head><body>old page</body></html>"),
            run_case("live page is the Blue Jays tracker this one replaced",
                     T, expect=True,
                     live_html=PAGE.replace("nhl-TOR-20262027", "mlb").format(fp="0a1b2c3d4e5f6a7b")),
            run_case("live page fingerprint parsed and matches",
                     T, expect=False, live_html=PAGE.format(fp=fp_now)),
            run_case("FORCE_BUILD overrides everything",
                     T, expect=True, live_html=PAGE.format(fp=fp_now), force=True),
        ]
    finally:
        urllib.request.urlopen = _REAL_URLOPEN

    # the fingerprint must not depend on row ordering
    stable = cc.fd.fingerprint(rows_of(T)) == cc.fd.fingerprint(list(reversed(rows_of(T))))
    print(f"--- fingerprint stable regardless of row order\n    "
          f"{'OK' if stable else 'FAIL'}")
    results.append(stable)

    # a finished game must actually move the fingerprint, or polling never rebuilds
    moves = cc.fd.fingerprint(rows_of(T)) != cc.fd.fingerprint(rows_of(after))
    print(f"--- fingerprint changes when a game finishes\n    "
          f"{'OK' if moves else 'FAIL'}")
    results.append(moves)

    # an overtime loss is a point in the standings, so it must move it too
    otl = {k: dict(v) for k, v in T.items()}
    otl["TOR"]["otl"] += 1
    moves_otl = cc.fd.fingerprint(rows_of(T)) != cc.fd.fingerprint(rows_of(otl))
    print(f"--- fingerprint changes on an overtime loss\n    "
          f"{'OK' if moves_otl else 'FAIL'}")
    results.append(moves_otl)

    print("\n" + "=" * 58)
    if all(results):
        print(f"SELF-TEST PASSED — polling logic behaves on all {len(results)} checks")
        return 0
    print("SELF-TEST FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
