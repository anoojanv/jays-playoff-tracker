# Maple Leafs playoff tracker

Rebuilds an interactive Toronto Maple Leafs playoff-odds page as games finish and
publishes it to Netlify. Runs entirely on GitHub Actions — nothing on your machine,
nothing to click.

**Live:** https://jays-playoff-tracker.netlify.app

The address still says *jays*: this repository began as a Blue Jays tracker and was
turned into a Leafs one for the 2026–27 NHL season. The Netlify site, the workflow and
the Refresh button all carried over unchanged, so the page lives at the same URL.

---

## Setup — about 10 minutes, once

### 1. Put this on GitHub

```bash
cd jays-playoff-tracker
git init
git add .
git commit -m "Maple Leafs playoff tracker"
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
(`0a3e85c0-7356-4468-9b79-3d97c57dce8c`, the `jays-playoff-tracker` site). To publish
somewhere else instead, add a repository **variable** named `NETLIFY_SITE_ID` and it
takes precedence.

### 4. Watch the first run

Pushing to `main` kicks off a build. Repo → **Actions** → **Tracker build & deploy** to
watch it, or **Run workflow** to start one by hand.

It takes 2–3 minutes. The log prints the alignment it read (32 clubs, 4 divisions),
last season's rates, confirms every club reconciles to the season length, prints the
playoff odds, then deploys. When it's green, reload the site.

### 5. (Optional) The Refresh button

The header has a **Refresh** button that asks GitHub to check the NHL for finished games
right now, instead of waiting for the next scheduled poll. The page is static, so the
button cannot fetch anything itself: it calls a tiny Netlify function
(`netlify/functions/refresh.mjs`) that holds a GitHub token and dispatches the same
workflow the schedule runs. Until the token is set the button simply says it is not set
up — the page never depends on it.

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** →
   **Fine-grained tokens** → **Generate new token**. Repository access: *only this
   repository*. Permissions: **Actions — Read and write**. Set an expiry you will
   remember.
2. Netlify → your site → **Site configuration** → **Environment variables** → add
   `GITHUB_DISPATCH_TOKEN` with that token. (`GITHUB_REPO` and `GITHUB_DISPATCH_REF`
   override the defaults if the site ever publishes a different repo or branch.)
3. The next deploy picks it up.

A click does nothing while a run is already queued or in progress, nothing within ten
minutes of the previous run, and otherwise dispatches with `only_if_changed` set — the
cheap standings check, rebuilding only if a game has actually finished. The page then
polls the run and compares the `data-fingerprint` meta tag when it finishes: new data
reloads the page, unchanged data says so.

### Another team, or next season

`TEAM` and `SEASON` at the top of `.github/workflows/nightly.yml` are the only two
settings: any NHL tricode (`MTL`, `EDM`…) and an NHL season id (`20272028`). The page
takes the club's name, conference and division from the league's own standings. The
brand colours in `src/build_html.py` are the Leafs', and are the one thing you would
change by hand.

### How often it updates

It polls **every 30 minutes from 4pm to 2am Eastern** — weekend matinees end around 4pm,
West Coast games around 1am. Each poll is cheap: it fetches the league standings,
fingerprints all 32 clubs' records, and compares that to the fingerprint embedded in the
page currently published. Nothing changed, nothing rebuilds. The published page is its
own state file — no database, nothing cached between runs, and if a deploy is ever
rolled back the next poll notices and republishes.

The season straddles the clock change (EDT in October, EST from November), so the UTC
window is an hour wider than the Eastern one to cover both. One full rebuild a day at
07:13 UTC runs whether or not anything changed, so the next-game strip and the calendar
roll forward on off days — and, before the season opens, so the preseason page stays
current while every club's record is still zero.

The poll runs *before* `setup-python` and `pip install`, because `check_changed.py` is
standard library only, so a tick that finds nothing new costs a checkout and a couple of
seconds of Python.

GitHub's scheduler is best-effort, and in practice often fires late or not at all. The
page says how old it is and warns once it is more than 30 hours old, and **Refresh** lets
anyone looking at a stale page pull the latest results themselves.

---

## What runs

| | |
|---|---|
| `src/check_changed.py` | The cheap poll: is anything new since the last publish? Standard library only |
| `src/fetch_data.py` | Pulls the alignment, last season's final standings, and every club's schedule from the NHL's public API (`api-web.nhle.com`); **sums every club's record from its own completed games**, and refuses to continue unless every club reconciles to the season length |
| `src/model.py` | Talent, schedule, the Monte Carlo and the playoffs. Imported by the scripts below, which all read the **same** simulated seasons |
| `src/sim.py` | 40,000 simulated seasons of the whole league → `results.json` |
| `src/ensemble.py` | 10 model specifications, for the sensitivity range |
| `src/analyze.py` | What it takes: points needed, pace, what qualifying seasons look like |
| `src/export_sim.py` | ~16 KB model bundle for the in-browser simulator |
| `src/motion.js` | The motion graphics — season machine, forecast cone, reveals — inlined into the page |
| `src/backtest.py` | Not nightly. Replays a finished season through the real model and grades it; writes `data/backtest_<season>.json`, which is committed |
| `src/build_html.py` | Renders the page |
| `src/og_image.py` | The 1200×630 share card `og:image` points at. Best-effort: never fails a build |
| `src/build.py` | Runs all of the above, then verifies the output before it can be published |

The build fails — and publishes nothing — if the schedule doesn't reconcile, if the page
comes out suspiciously small, if it references an external URL, or if the interactive
markup or the tracker id is missing.

**Why standings come from the schedule.** The baseball version read standings and
schedule from two endpoints that updated at different moments, and spent hundreds of
lines reconciling them. Here a club's record *is* its completed games, so games played
plus games left equals the season length by construction. A game still being played
(`LIVE`, `CRIT`) is a game still to play, exactly as the league's standings treat it.
The season length itself is read off the schedule — the NHL went from 82 games to 84 for
2026–27, and a constant would have been wrong the day it shipped.

## The preseason

Before a puck drops every club has zero points, and a model that only knows this season
would rate all 32 identically — the ensemble's "this season only" row lands on 49%, which
is just the share of clubs that make it. So the model pools **last season's** final
record as a prior worth 25 games, and lets this season take over as games are played.
The page says so in the headline ("on last season's form"), drops the division place
from the header (with everyone on zero it would be alphabetical), and orders the race
table by projected points rather than standings.

## The model

Team strength is the probability of beating an average club: goal-based Pythagorean win%
(exponent 2.1) blended 70/30 with actual win%, pooled across last season and this one,
then regressed toward .500 with 70 games' worth of an average club. Each remaining game is
a log5 matchup plus home ice, measured from last season (the home side won 52.2%).

**Strength is uncertain, and the model says so.** Each simulated season draws every club's
strength from a range around its estimate — about 2/√n on the log-odds scale, where n is
everything the estimate stands on, scaled by `SIGMA_SCALE` — and plays the whole season,
playoffs included, with that draw. The range narrows as games are played. Without it the
model treated an estimate as a fact and was overconfident at both ends.

A separate draw decides whether a game went past regulation (24.9% last season), which is
what hands the loser a point: **two for a win of any kind, one for an overtime or
shootout loss**. Standings run on points, then regulation wins — the NHL's first
tiebreaker — then a coin. The field is the top three in each division plus two wild cards
per conference.

## Is it any good? The report card

A model should not mark its own homework, so `src/backtest.py` grades it against seasons
that already happened. It replays a season week by week from opening night through the real
pipeline, knowing only what was known that morning — the season before as the prior, and
the games played so far — and scores all 32 clubs' playoff odds against who actually made
it, by the league's own clinch flag. Two baselines keep it honest: a coin (every club 50%)
and the standings (100% for clubs in a playoff spot that morning, 0% otherwise). The score
is the Brier score — mean squared error of a probability, lower is better, a coin is 0.250.

**What it found.** The first version beat both baselines over 2025–26 (0.169, against 0.243
for the standings) but **lost to a coin over the first seven weeks** (0.267): it leaned on
last season too hard and treated strength as known. The fix was fitted on **2024–25 only** —
last season's weight 40 → 25 games, regression 40 → 70, strength uncertainty on — and then
graded on **2025–26, which the fit never saw**: 0.159 over the season and 0.242 over the
first seven weeks, now better than a coin. Both runs are committed in `data/`, and
`tests/test_motion.py` holds the page's claims to them. The 896 predictions per season are
not independent (the same clubs, week after week), and the page says so.

Re-run it each spring once a season is final: `python src/backtest.py <season>`.

## The motion graphics

Motion here explains something or it isn't there.

- **Every dot is a season.** A canvas of dots — about 500 on a phone, up to 4,000 on a
  desktop — each a batch of simulated
  seasons, poured from a hopper into a histogram of the Leafs' final points, navy if that
  season makes the playoffs. The counter is the share of landed dots that are navy, so the
  estimate visibly wobbles and settles — which is all a Monte Carlo is. *Beat / lose to*
  tonight's opponent re-sorts the same seasons to where they finish if it goes that way;
  every dot glides to its new column.
- **The forecast cone**, borrowed from hurricane forecasting: the season so far as a solid
  line, 48 real simulated paths fanning out, then the 50% and 90% bands and the median.
  Drag across it to read any game. Drawn at the container's real width, so its text is the
  size it says on a phone too.
- **Reveals.** Sections, bars, calibration dots and the report card's lines animate in as
  they scroll into view.

Rules: nothing is hidden unless the script is running, so a failure leaves a complete page;
`prefers-reduced-motion` gets the final state with no movement; everything runs on
`requestAnimationFrame` (steady 60 fps with 4,000 dots in headless Chromium); no network, no
storage. The page has a 350 KB budget that the verifier enforces.

## If they get in

The whole playoff bracket, both conferences and the Stanley Cup Final, as the NHL draws
it: the better division winner plays the second wild card, the other plays the first, and
second hosts third in each division. Every series is best of seven, 2–2–1–1–1, home ice
to the better regular season, played with the same matchup that simulates an October
game. Every game of a series is played rather than stopping at the fourth win, which
gives the identical winner and lets a whole round vectorise over every season at once.

Every number is conditional on Toronto qualifying, and the section says so. The bracket
is drawn as **one picture**: Toronto sits in its likeliest seat opposite the club it most
often meets from there, every other club takes one seat at most (filled greedily,
likeliest first), and each later slot goes to whichever of its two feeders wins that
series more often. Picking each slot on its own used to put one strong club in three
seats at once — in October nearly every seat is a coin flip among the same few clubs.
Above it, four bars give the question a fan is actually asking: how often Toronto wins
round one, round two, the conference, and the Cup.

It is **dynamic**: the browser simulator seeds the Eastern field and plays it out, with
the Western champion sampled from the Python run, so every scenario redraws it.

## Play it out

- **The slider** sets Toronto's rest-of-season points; each simulated season spreads them
  across the remaining games at random (a win is two, an odd point is an overtime loss).
  Presets: the bare minimum, a .550 or .620 points pace, and a slump.
- **The hot/cold toggles** in Scoreboard watching force a rival's finish, calibrated so a
  forced finish lands near that club's 25th/75th-percentile points (a logit shift of
  1.348/√G over G remaining games) — tapping *cold* moves the odds by about what the bar
  beside it promises.

Every change re-runs 5,000 seasons of the Eastern Conference in the browser, with the same
per-season strength draws as the Python model so a scenario stays comparable with the headline (the other
conference cannot move Toronto's odds of qualifying, so it is left out and each re-run
stays fast). The scenario round-trips through the URL hash, so **Share** sends the exact
scenario.

## Around the league

Every remaining game Toronto is *not* playing that touches the Eastern Conference,
scored against Toronto's own odds from the same simulated seasons: P(in | home wins) −
P(in | away wins). The club named is the one to root for and the number is what the game
is worth. Scoring the game itself, rather than each club's finish, gets the head-to-head
right: two rivals cannot both lose, and a game between them is usually worth less than
either against an outsider. Anything inside twice its own Monte Carlo error is shown as a
toss-up with no recommendation.

## The rest of the page

- **Who the race is against** — the clubs projected within 10 points of Toronto, read off
  every build rather than typed in. Scoreboard watching considers every other Eastern
  club and shows the six whose finish moves Toronto's odds most.
- **The next game** — opponent, puck drop in Eastern time, odds after a win and after a
  loss; *tonight*, *tomorrow*, *underway* or *played*, rendered by the browser from UTC.
- **Momentum** — recent results against the model's own expectation, weighted toward the
  latest games. Zero means playing to their own level, which is not .500.
- **Rem SOS** — what an average club would win against each team's remaining opponents.
  It explains the odds rather than adjusting them: every game is already simulated
  against its real opponent.
- **How the odds got here** — a chart of the page's own previous readings, kept in a
  `page-history` meta tag. Each build reads the live page and appends — but only if the
  live page carries this tracker's id (`<meta name="tracker-id">`), so weeks of Blue Jays
  odds never got drawn as Leafs history. Nothing is drawn under four readings.
- **Sharing** — leads with the number ("Toronto Maple Leafs 14.2% to make the playoffs"),
  via the native share sheet where there is one.

## Tests

Everything is offline. The fixture, `tests/fixture_data.json`, is a synthetic season —
32 clubs, an 84-game schedule, 50 rounds played with a seeded coin — built by
`tests/make_fixture.py` through `fetch_data.build_records` itself, so it reconciles by
construction and exercises the same code the live data takes.

```bash
python src/selftest_fetch.py    # the NHL fetch, every endpoint mocked
python src/selftest_check.py    # the polling decision, every path
python tests/test_reconcile.py  # the season-length check, and the clean stop
python tests/test_points.py     # points, overtime, the tiebreak, the field
python tests/test_bracket.py    # seeding, series, and drawing the bracket
python tests/test_spoiler.py    # scoring the games Toronto is not playing
python tests/test_rivals.py     # the rival lists follow the standings
python tests/test_momentum.py   # the momentum rating's semantics
python tests/test_sos.py        # strength of schedule
python tests/test_history.py    # the day-over-day deltas and the page's own history
node   tests/test_refresh.mjs   # the Refresh button's endpoint, GitHub mocked
python tests/test_motion.py     # the data the motion graphics draw, and the backtest's claims
python tests/test_endgame.py    # preseason, mid-season, clinched, eliminated, with history
python tests/make_fixture.py    # rebuild the fixture (must be byte-identical; CI checks)
```

`.github/workflows/tests.yml` runs all of it on every push and pull request.

## Running it locally

```bash
pip install -r requirements.txt
python src/build.py              # fetch fresh data, then build
python src/build.py --no-fetch   # rebuild from the last build/data.json
open public/index.html
```

No network? Build against the fixture — exactly what CI does:

```bash
mkdir -p build && cp tests/fixture_data.json build/data.json
python src/build.py --no-fetch
```

## When something breaks

**"schedule does not reconcile"** or **"clubs have different season lengths"** — the
NHL's schedule feed is missing or duplicating a game for some club. The message names
which. It almost always clears on the next poll; the build refuses rather than publish
odds from a broken schedule.

**"SEASON COMPLETE: no games remain"** — the regular season is over. The build stops on
purpose. Disable the workflow, or bump `SEASON` in `.github/workflows/nightly.yml`.

**Deploy step fails with "NETLIFY_AUTH_TOKEN is not set"** — step 3 above.

**Refresh button says "not set up"** — step 5 above.

**A test fails with "fixture missing"** or CI says the fixture is stale — re-run
`python tests/make_fixture.py` and commit the result.

## Notes

- Ties past regulation wins go to a coin, not the NHL's later tiebreakers
  (regulation-plus-overtime wins, total wins, head-to-head).
- The model knows goals and results. It does not know about injuries, goaltending
  changes or the trade deadline.
- Not affiliated with or endorsed by the Toronto Maple Leafs or the NHL.
