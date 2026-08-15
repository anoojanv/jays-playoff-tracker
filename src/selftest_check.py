"""
Offline test for check_changed.py — the polling logic that decides whether to rebuild.

Covers the four cases that matter:
  1. nothing has changed since the last publish  -> skip
  2. a game has finished                          -> rebuild
  3. the live page can't be read                  -> rebuild (publishing is the safe error)
  4. the live page predates the fingerprint       -> rebuild

Run:  python src/selftest_check.py
"""
import os, sys, json, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

fixture = os.path.join(ROOT, "build", "data.json")
if not os.path.exists(fixture):
    print("selftest skipped: no build/data.json fixture yet (run src/build.py once)")
    raise SystemExit(0)
BASE = json.load(open(fixture))

spec = importlib.util.spec_from_file_location("cc", os.path.join(HERE, "check_changed.py"))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)


def standings_stub(al, nl):
    def _s(league):
        src = al if league == 103 else nl
        return {k: {"w": v[0], "l": v[1], "rs": v[2], "ra": v[3]} for k, v in src.items()}
    return _s


def run_case(name, al, nl, live_fp, force=False, expect=None):
    cc.fd.standings = standings_stub(al, nl)
    cc.live_fingerprint = lambda: live_fp
    os.environ["FORCE_BUILD"] = "true" if force else ""
    os.environ.pop("GITHUB_OUTPUT", None)
    print(f"\n--- {name}")
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cc.main()
    got = "changed=true" in buf.getvalue()
    ok = got == expect
    print(f"    expected rebuild={expect}, got rebuild={got}  {'OK' if ok else 'FAIL'}")
    return ok


def main():
    AL = {k: list(v) for k, v in BASE["AL"].items()}
    NL = {k: list(v) for k, v in BASE["NL"].items()}
    fp_now = cc.fd.fingerprint(
        {k: {"w": v[0], "l": v[1], "rs": v[2], "ra": v[3]} for k, v in AL.items()},
        {k: {"w": v[0], "l": v[1], "rs": v[2], "ra": v[3]} for k, v in NL.items()})

    AL_after = {k: list(v) for k, v in AL.items()}     # pretend the Jays just won one
    AL_after["Blue Jays"][0] += 1
    AL_after["Blue Jays"][2] += 5
    AL_after["Rays"][1] += 1
    AL_after["Rays"][3] += 5

    results = [
        run_case("nothing finished since the last publish",
                 AL, NL, fp_now, expect=False),
        run_case("a game finished (Jays win, Rays loss)",
                 AL_after, NL, fp_now, expect=True),
        run_case("live page unreachable",
                 AL, NL, None, expect=True),
        run_case("live page predates the fingerprint meta",
                 AL, NL, None, expect=True),
        run_case("FORCE_BUILD overrides everything",
                 AL, NL, fp_now, force=True, expect=True),
    ]

    # the fingerprint must be stable across dict ordering
    shuffled = dict(reversed(list(AL.items())))
    a = cc.fd.fingerprint({k: {"w": v[0], "l": v[1], "rs": v[2], "ra": v[3]} for k, v in AL.items()},
                          {k: {"w": v[0], "l": v[1], "rs": v[2], "ra": v[3]} for k, v in NL.items()})
    b = cc.fd.fingerprint({k: {"w": v[0], "l": v[1], "rs": v[2], "ra": v[3]} for k, v in shuffled.items()},
                          {k: {"w": v[0], "l": v[1], "rs": v[2], "ra": v[3]} for k, v in NL.items()})
    stable = a == b
    print(f"\n--- fingerprint stable regardless of key order\n    {'OK' if stable else 'FAIL'}")
    results.append(stable)

    print("\n" + "=" * 58)
    if all(results):
        print("SELF-TEST PASSED — polling logic behaves on all five paths")
        return 0
    print("SELF-TEST FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
