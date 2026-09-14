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

### 5. (Optional) The Refresh button

The header has a **Refresh** button that asks GitHub to check MLB for finished games right
now, instead of waiting for the next scheduled poll. The page is static, so the button
cannot fetch anything itself: it calls a tiny Netlify function (`netlify/functions/refresh.mjs`)
that holds a GitHub token and dispatches the same workflow the schedule runs. Until the
token is set the button simply says it is not set up — the page never depends on it.

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** →
   **Fine-grained tokens** → **Generate new token**. Repository access: *only this
   repository*. Permissions: **Actions — Read and write** (Metadata comes along
   automatically). Set an expiry you will remember.
2. Netlify → your site → **Site configuration** → **Environment variables** → add
   `GITHUB_DISPATCH_TOKEN` with that token. (If the site ever publishes a different
   repo or branch, `GITHUB_REPO` and `GITHUB_DISPATCH_REF` override the defaults.)
3. The next deploy picks it up — or trigger one from the Actions tab.

What a click does: nothing while a run is already queued or in progress, nothing within
ten minutes of the previous run (whoever started it), and otherwise a dispatch with
`only_if_changed` set, so it runs the cheap standings check and rebuilds only if a game
has actually finished — a click when nothing has changed costs seconds, not minutes. The
page then polls the run and, when it finishes, re-reads itself and compares the
`data-fingerprint` meta tag: new data reloads the page, unchanged data says so. The
cooldown is `COOLDOWN_MIN` in the function.

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

Bear in mind GitHub's scheduler is best-effort, and in practice it is a lot worse than
"best-effort" sounds. **Over Sep 1–8, 2026 it fired 4 to 6 of the 21 scheduled ticks a
day**, and the ones it did fire ran hours late. So "within 30 minutes of a game ending"
is really "some time in the next few hours, or when someone re-runs the workflow by
hand". The page says how old it is (top right of the header, in Eastern time) and shows a
warning once it is more than 30 hours old, so at least a stale number is never mistaken
for a fresh one, and the **Refresh** button beside that stamp (step 5 above) lets anyone
looking at a stale page pull the latest results in themselves rather than wait for a tick
that may not come. What is still open is the automatic cadence: a scheduler that actually
fires, or moving the refresh into the browser, which the page is already capable of since
it runs the whole simulation there.

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
| `src/og_image.py` | The 1200×630 share card that `og:image` points at, so a pasted link shows the odds. Best-effort: never fails a build |
| `src/build.py` | Runs all of the above, then verifies the output before it can be published |

The build fails — and publishes nothing — if the schedule doesn't reconcile, if the page
comes out suspiciously small, if it somehow references an external URL, or if the
interactive markup is missing.

## Day-over-day change

The odds carry a delta against roughly 24 hours ago, and the momentum badge carries one
too. There is still no database: the page keeps a short history in a `page-history` meta
tag, and each build reads the live page, appends today's reading, and republishes it —
the same "the published page is its own state file" trick `check_changed.py` uses for the
fingerprint.

It has to be a history rather than just the previous value, because the site rebuilds
every time a game finishes — up to twenty times a day. A "since last publish" delta would
be one game's noise rather than a day's movement.

When nothing in the history is far enough back, **no delta is shown at all**. A point three
hours old is not passed off as "since yesterday", and a fresh page shows nothing rather
than a fabricated zero. Readings closer together than half an hour collapse into one, so
the tag cannot grow without bound and a rebuild of unchanged data is idempotent.

If the live page cannot be read there is no history — that costs a delta and nothing
else; it can never fail a build.

## Who the race is against

The clubs the page calls the cluster — the "Rivals beaten out" figure, the must-see
reasons, the `is_rival` flag on each series — are read off the standings on every build:
every club that is not leading a division and sits within `CLUSTER_GB` games (six) of
Toronto in either direction. This used to be a list typed into `src/model.py` in August,
and by September it was still naming two clubs that were out of it while missing the one
holding the last spot. Scoreboard Watching considers every other AL club and shows the six
whose finish moves Toronto's odds the most, so an irrelevant club falls out on its own.

## The next game, and how old the page is

The header carries the next game — opponent, first pitch in Eastern time, and the odds
after a win and after a loss — and a stamp saying how long ago the page was rebuilt. Both
are rendered by the browser from UTC timestamps in the page, so the build stays
self-contained and nothing is fetched. The strip says *tonight*, *tomorrow*, *underway*
(when the feed marked the game in progress, or first pitch was less than four hours ago)
or *played · odds update after the next rebuild*, and a warning appears above it once the
page is more than 30 hours old.

Magic and tragic numbers are the ones fans actually quote — 163 minus one club's wins
minus the other's losses — against the specific club on the other side of the line: the
division runner-up when Toronto leads, the first club out when Toronto holds a wild card,
the club holding the last wild card otherwise. They come from the standings, not the
simulation, so they agree with every broadcast.

## Around the league

Scoreboard watching, at the level a fan can act on. Every remaining game Toronto is *not*
playing is scored against Toronto's own odds from the same simulated seasons as the rest
of the page: P(in | home wins) − P(in | away wins). The club named is the one to root for
and the number is what the game is worth.

This exists because ranking clubs by how much their *finish* matters falls apart the
moment two of them play each other. In September 2026 the page told fans to root against
Cleveland (29.4 points of swing) and against Chicago (11.7) while those two were playing
a three-game set for the AL Central. Both cannot lose. Scoring the game itself resolves
it — root for Chicago, worth about 3.3 points a game — and it prices in the structure the
standings hide: the loser of a division race drops into the wild-card pool Toronto is
fighting over, so beating a rival can help them.

The same run showed the more useful thing: Cleveland's games against the Athletics and
Royals were worth 8 to 9 points each, nearly three times the head-to-head, precisely
because the head-to-head partly cancels itself out.

**Toss-ups.** Most games in a league are worth almost nothing to Toronto, and below a
couple of standard errors the *sign* of the difference is Monte Carlo noise rather than
baseball. In the fixture, games worth under half a point disagreed with "root against the
club you are chasing" about a quarter of the time; above one point they agreed 37 times
out of 37. So each game carries its own standard error and anything that does not clear
twice it is shown as a toss-up with no recommendation, rather than sending people to
cheer on the strength of a coin flip in the random number generator.

## Strength of schedule

It is already in every probability on the page, and not as an adjustment: each remaining
game is simulated against that specific opponent, with home field applied, so a hard
run-in shows up as lower win probabilities game by game. Adding a schedule factor on top
of that would double-count it.

What the page was missing was any way to *see* it. The **Rem SOS** column in the wild-card
table is what a league-average club would win against that team's remaining opponents.
Holding talent constant is the point — it isolates the schedule, so two clubs can be
compared without their own quality leaking into the number. Darker is harder.

The column explains the odds rather than changing them.

## Momentum

The badge beside the record is recent form measured against the model's own expectation,
not a last-ten record. Every completed game is scored against the probability the model
gave it — the same log5 matchup plus home-field edge that simulates the rest of the
season — and the difference is weighted by recency, halving about every seven games.

So **0 means playing exactly to their own level, which is not .500**: splitting ten games
with the Angels reads as cold, while splitting ten with the Rays reads as steady. The
badge also prints the raw last-ten record and what the model expected from it, so the
rating can always be checked against something concrete.

It comes from a separate, wider, best-effort request for the Blue Jays' completed games.
If that request fails the badge simply disappears; it cannot fail a build.

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

## Scenario controls

Three controls drive one scenario, and every change re-runs the browser simulation:

- **The slider** sets a rest-of-season win total, spread across the remaining series in
  proportion to what qualifying seasons take from each.
- **The road-map buttons** lock an individual series result; the slider moves to match.
- **The hot/cold toggles** in Scoreboard watching force a rival's finish. The shift is
  calibrated per club so a forced finish lands near the 25th/75th-percentile win totals
  the dependency bars already describe (a logit shift of 1.348/√G over G remaining
  games), rather than some arbitrary collapse — so tapping *cold* moves the odds by
  about what the bar next to it promises.

The whole scenario — series results and rival biases — round-trips through the URL
hash, so a **Copy link** button appears whenever something is set and the link restores
the exact scenario on load. Nothing is stored anywhere else; the page stays
self-contained and `build.py`'s verifier still enforces that.

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
python tests/test_momentum.py   # the momentum rating's semantics
python tests/test_rivals.py     # the rival lists follow the standings
python tests/test_spoiler.py    # scoring the games Toronto is not playing
python tests/test_sos.py        # strength of schedule, and that it matches the sim
python tests/test_history.py    # the day-over-day deltas and the page's own history
python tests/test_reconcile.py  # the 162-game check, over- and under-count
python tests/test_gameover.py   # a game still in "Game Over", both sides of the race
node   tests/test_refresh.mjs   # the Refresh button's endpoint: every guard, GitHub mocked
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

The common case is a game MLB has marked **"Game Over"** but not yet **"Final"** — the
official scorer signs off some minutes later, and the standings count the game the moment
it is over. Both states count as a played date, so `as_of` keeps up and `drop_phantoms()`
can act on it. The game itself is only removed once the standings prove they have counted
it, so a game that is merely over is still a game to play, and the club stays at 162
either way.

Either way the adjustment is stated in the page's methodology footnote. Remove the entry
once the feed corrects itself.

**Baseball-Reference comparison missing** — that scrape is best-effort. If B-Ref changes
its markup the pill just disappears; the build still succeeds. Fix the regex in
`bref_odds()` if you want it back.

**Deploy step fails with "NETLIFY_AUTH_TOKEN is not set"** — step 3 above.

**Refresh button says "not set up"** — step 5 above: the Netlify site has no
`GITHUB_DISPATCH_TOKEN`. **"Could not start a refresh"** with a GitHub HTTP code means the
token expired or lost its Actions permission; mint a new one.

**"SEASON COMPLETE: no games remain"** — the season is over, so there is nothing left to
simulate. The build stops on purpose rather than crashing partway through. Disable the
workflow in the Actions tab, or bump `SEASON` and `SEASON_END` in
`.github/workflows/nightly.yml` for next year.

**A test fails with "fixture missing"** — regenerate it with `python tests/make_fixture.py`.
If CI says the fixture is *stale*, the generator changed without the committed JSON being
updated; re-run it and commit the result.

## Notes

- Ties are broken at random rather than by head-to-head record. With a handful of games
  left that is a real limitation, not a footnote.
- The model knows run differential. It does not know about injuries, rotations, or
  September call-ups.
- Not affiliated with or endorsed by the Toronto Blue Jays or MLB.
