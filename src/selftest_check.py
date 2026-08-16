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
        '<meta name="data-fingerprint" content="{fp}">'
        '</head><body>Blue Jays</body></html>')


def as_dicts(src):
    return {k: {"w": v[0], "l": v[1], "rs": v[2], "ra": v[3]} for k, v in src.items()}


def standings_stub(al, nl):
    def _s(league):
        return as_dicts(al if league == 103 else nl)
    return _s


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


def run_case(name, al, nl, expect, live_html, force=False):
    """live_html is the body the published page returns, or None to fail the request."""
    cc.fd.standings = standings_stub(al, nl)
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
    AL = {k: list(v) for k, v in BASE["AL"].items()}
    NL = {k: list(v) for k, v in BASE["NL"].items()}
    fp_now = cc.fd.fingerprint(as_dicts(AL), as_dicts(NL))

    AL_after = {k: list(v) for k, v in AL.items()}     # pretend the Jays just won one
    AL_after["Blue Jays"][0] += 1
    AL_after["Blue Jays"][2] += 5
    AL_after["Rays"][1] += 1
    AL_after["Rays"][3] += 5

    try:
        results = [
            run_case("nothing finished since the last publish",
                     AL, NL, expect=False, live_html=PAGE.format(fp=fp_now)),
            run_case("a game finished (Jays win, Rays loss)",
                     AL_after, NL, expect=True, live_html=PAGE.format(fp=fp_now)),
            run_case("live page unreachable",
                     AL, NL, expect=True, live_html=None),
            run_case("live page predates the fingerprint meta",
                     AL, NL, expect=True,
                     live_html="<html><head></head><body>old page</body></html>"),
            run_case("live page fingerprint parsed and matches",
                     AL, NL, expect=False, live_html=PAGE.format(fp=fp_now)),
            run_case("FORCE_BUILD overrides everything",
                     AL, NL, expect=True, live_html=PAGE.format(fp=fp_now), force=True),
        ]
    finally:
        urllib.request.urlopen = _REAL_URLOPEN

    # the fingerprint must not depend on dict ordering
    shuffled = dict(reversed(list(AL.items())))
    stable = (cc.fd.fingerprint(as_dicts(AL), as_dicts(NL))
              == cc.fd.fingerprint(as_dicts(shuffled), as_dicts(NL)))
    print(f"--- fingerprint stable regardless of key order\n    "
          f"{'OK' if stable else 'FAIL'}")
    results.append(stable)

    # a finished game must actually move the fingerprint, or polling never rebuilds
    moves = cc.fd.fingerprint(as_dicts(AL), as_dicts(NL)) != \
        cc.fd.fingerprint(as_dicts(AL_after), as_dicts(NL))
    print(f"--- fingerprint changes when a game finishes\n    "
          f"{'OK' if moves else 'FAIL'}")
    results.append(moves)

    print("\n" + "=" * 58)
    if all(results):
        print(f"SELF-TEST PASSED — polling logic behaves on all {len(results)} checks")
        return 0
    print("SELF-TEST FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
