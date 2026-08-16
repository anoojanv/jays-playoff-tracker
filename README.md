# Blue Jays playoff tracker

Rebuilds an interactive Toronto Blue Jays playoff-odds page every night and publishes it
to Netlify. Runs entirely on GitHub Actions — nothing on your machine, nothing to click.

**Live:** https://jays-playoff-tracker.netlify.app

---

## Setup — about 10 minutes, once

### 1. Put this on GitHub

```bash
cd jays-playoff-tracker
git init
git add .
git commit -m "Blue Jays playoff tracker"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/jays-playoff-tracker.git
git push -u origin main
```

Create the empty repo on GitHub first (github.com/new). It can be private — Actions and
Netlify both work fine with private repos.

### 2. Get a Netlify token

Netlify → avatar (top right) → **User settings** → **Applications** → **Personal access
tokens** → **New access token**. Call it something like `github-actions`, and copy the
token — Netlify shows it exactly once.

### 3. Add the token to GitHub

Your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository
secret**.

| Name | Value |
|---|---|
| `NETLIFY_AUTH_TOKEN` | the token from step 2 |

The site ID is already baked into the workflow
(`0a3e85c0-7356-4468-9b79-3d97c57dce8c`, your `jays-playoff-tracker` site). To publish
somewhere else instead, add a repository **variable** named `NETLIFY_SITE_ID` and it
takes precedence.

### 4. Watch the first run

Pushing in step 1 already kicked off a build — but it would have failed at the deploy
step, because the token wasn't set yet. Now that it is, re-run it: repo → **Actions** →
the latest run → **Re-run all jobs**. (Or **Tracker build & deploy** → **Run
workflow**.)

It takes 2–3 minutes. Watch the log: it prints the record it fetched, confirms all 15 AL
clubs reconcile to 162 games, prints the playoff odds, then deploys. When it's green,
reload the site.

That's it. From then on it runs itself.

### How often it updates

It polls **every 30 minutes from 4pm to 2am Eastern** — the window in which games
actually finish, from afternoon starts through West Coast night games that end around
1am. Each poll is cheap: it fetches the two standings endpoints, fingerprints all 30
clubs' records, and compares that to a fingerprint embedded in the page that is
currently published. Nothing changed, nothing rebuilds.

The published page is therefore its own state file — there is no database, nothing
cached between runs, and if a deploy is ever rolled back the next poll notices and
republishes.

There is also one guaranteed full rebuild a day at **3:13am Eastern**, which runs whether
or not anything changed, so the Baseball-Reference comparison stays fresh.

That is twenty polling ticks a day (`7,37 20-23` and `7,37 0-5` UTC) plus the 07:13 UTC
rebuild. The poll runs *before* `setup-python` and before `pip install`, because
`check_changed.py` is standard library only — so a tick that finds nothing new is a
checkout and a couple of seconds of Python, and never installs a toolchain.

The cron times are UTC and assume Eastern Daylight Time (UTC-4). The regular season ends
in early October, well before the November switch back to EST, so the window does not
drift; if you ever run this past that date, shift all three crons an hour later.

**Cost.** GitHub bills each job rounded up to a whole minute, and a private repo gets
2,000 free minutes a month. Roughly ten real rebuilds a day at ~3 minutes, plus eleven
ticks that skip at ~1 minute, works out around **1,200-1,400 minutes a month**, leaving
decent headroom. If you ever get close, the lever is the polling window in
`.github/workflows/nightly.yml` — narrow the hours before you lengthen the interval,
since most games finish late.

Bear in mind GitHub's scheduler is best-effort: **delays of 5 to 30 minutes are common**
at peak times. So "within 30 minutes of a game ending" is realistically 30-60.

---

## What runs each night

| | |
|---|---|
| `src/check_changed.py` | The cheap poll: is anything new since the last publish? Standard library only, no pip install |
| `src/fetch_data.py` | Pulls AL + NL standings and every AL club's remaining schedule from the MLB Stats API, dedupes games that appear in two clubs' feeds, and **refuses to continue unless all 15 AL teams reconcile to exactly 162 games** |
| `src/model.py` | Talent, schedule and the Monte Carlo itself. Imported by the three scripts below, which all read the **same** simulated seasons rather than each running their own |
| `src/sim.py` | Runs the 120,000-season Monte Carlo of the rest of the AL and writes `results.json` |
| `src/ensemble.py` | 10 model specifications, for the sensitivity range |
| `src/analyze.py` | Per-series requirements and leverage |
| `src/export_sim.py` | ~9 KB model bundle for the in-browser simulator |
| `src/build_html.py` | Renders the page |
| `src/build.py` | Runs all of the above, then verifies the output before it can be published |

The build fails — and publishes nothing — if the schedule doesn't reconcile, if the page
comes out suspiciously small, if it somehow references an external URL, or if the
interactive markup is missing.

## The model

Team strength is Pythagenpat expected win% (exponent = runs-per-game<sup>0.287</sup>)
blended 80/20 with actual W–L, then regressed toward .500 with a 68-game prior. Each
remaining game is simulated with a log5 matchup probability plus home-field advantage
(.535). The playoff field is three AL division winners plus the three best remaining
records, ties broken at random.

Every conditional number on the page — series targets, per-game leverage, rival
dependency — is read off the *same* set of simulated seasons, so they're mutually
consistent.

The page also ships the same model as JavaScript (`src/app.js`), so the slider and the
per-series buttons re-run ~14,000 full seasons in the browser on every change. Locking a
Jays win also locks the opponent's loss, which is why a scenario's odds differ slightly
from reading the win-total curve.

## Tests

Everything is offline: the two parts that talk to the outside world are stubbed, and both
tests run against `tests/fixture_data.json` — a committed, synthetic world rather than a
snapshot of a real day. A snapshot rots (the schedule empties, the records stop matching)
and cannot be regenerated without network access; the fixture is built by
`tests/make_fixture.py`, which generates the schedule first and then sets each club's
games-played to 162 minus what it has left, so it reconciles by construction.

```bash
python src/selftest_fetch.py    # the MLB fetch, with the network mocked
python src/selftest_check.py    # the polling decision, all six paths
python tests/test_reconcile.py  # the 162-game check, over- and under-count
python tests/test_endgame.py    # the page still builds once the race is decided
python tests/make_fixture.py    # rebuild the fixture (must be byte-identical; CI checks)
```

`selftest_fetch.py` covers the two quirks that actually bit us: the standings endpoint
returns short team names ("Rays") while the schedule endpoint returns full ones ("Tampa
Bay Rays"), and some games are still in progress when the build runs. `selftest_check.py`
drives the real `live_fingerprint()` over a stubbed HTTP call, so the regex that reads the
meta tag out of the published page is genuinely exercised.

`.github/workflows/tests.yml` runs all of it on every push and pull request — not on the
nightly schedule, so it costs nothing against the polling budget.

## Running it locally

```bash
pip install -r requirements.txt
python src/build.py              # fetch fresh data, then build
python src/build.py --no-fetch   # rebuild from the last build/data.json
open public/index.html
```

No network? Build against the test fixture instead — this is exactly what CI does:

```bash
mkdir -p build && cp tests/fixture_data.json build/data.json
python src/build.py --no-fetch
```

## When something breaks

**"schedule does not reconcile to 162 games"** — the standings and the schedule come
from two MLB endpoints that don't update together, so a club can land either side of 162.
The error names which, and the fix differs:

*A club at 161* is a postponement MLB hasn't rescheduled, leaving two clubs a game short.
Re-run tomorrow, or add the makeup to `SYNTHETIC_GAMES` at the top of `src/fetch_data.py`.

*A club at 163* is a game the standings already count that the schedule still lists as
upcoming. `drop_phantoms()` clears this automatically when it's unambiguous — the game is
dated on or before the last confirmed final, and every AL club in it is over 162 — and
refuses otherwise, so a real future fixture is never silently deleted. If one survives
that, it usually clears within a poll or two; failing that, add it to `IGNORE_GAMES`.

Either way the adjustment is stated in the page's methodology footnote. Remove the entry
once the feed corrects itself.

**Baseball-Reference comparison missing** — that scrape is best-effort. If B-Ref changes
its markup the pill just disappears; the build still succeeds. Fix the regex in
`bref_odds()` if you want it back.

**Deploy step fails with "NETLIFY_AUTH_TOKEN is not set"** — step 3 above.

**"SEASON COMPLETE: no games remain"** — the season is over, so there is nothing left to
simulate. The build stops on purpose rather than crashing partway through. Disable the
workflow in the Actions tab, or bump `SEASON` and `SEASON_END` in
`.github/workflows/nightly.yml` for next year.

**A test fails with "fixture missing"** — regenerate it with `python tests/make_fixture.py`.
If CI says the fixture is *stale*, the generator changed without the committed JSON being
updated; re-run it and commit the result.

## Notes

- Ties are broken at random rather than by head-to-head record.
- The model knows run differential. It does not know about injuries, rotations, or
  September call-ups.
- Not affiliated with or endorsed by the Toronto Blue Jays or MLB.
