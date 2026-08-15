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
the latest run → **Re-run all jobs**. (Or **Nightly tracker build & deploy** → **Run
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

**Cost.** GitHub bills each job rounded up to a whole minute, and a private repo gets
2,000 free minutes a month. Twenty cheap polls a day plus roughly ten real rebuilds works
out around **1,300 minutes a month**, leaving decent headroom. If you ever get close, the
lever is the polling window in `.github/workflows/nightly.yml` — narrow the hours before
you lengthen the interval, since most games finish late.

Bear in mind GitHub's scheduler is best-effort: **delays of 5 to 30 minutes are common**
at peak times. So "within 30 minutes of a game ending" is realistically 30-60.

---

## What runs each night

| | |
|---|---|
| `src/check_changed.py` | The cheap poll: is anything new since the last publish? Standard library only, no pip install |
| `src/fetch_data.py` | Pulls AL + NL standings and every AL club's remaining schedule from the MLB Stats API, dedupes games that appear in two clubs' feeds, and **refuses to continue unless all 15 AL teams reconcile to exactly 162 games** |
| `src/sim.py` | 120,000-season Monte Carlo of the rest of the AL |
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

## Testing the fetch layer

`src/fetch_data.py` is the part that talks to the outside world, so it has an offline
integration test that mocks the API with responses in the real shapes — including the
quirk that the standings endpoint returns short team names ("Rays") while the schedule
endpoint returns full ones ("Tampa Bay Rays"), and that some games are still in progress
when the nightly build runs.

```bash
python src/selftest_fetch.py    # the MLB fetch, with the network mocked
python src/selftest_check.py    # the polling decision, all five paths
```

## Running it locally

```bash
pip install -r requirements.txt
python src/build.py              # fetch fresh data, then build
python src/build.py --no-fetch   # rebuild from the last build/data.json
open public/index.html
```

## When something breaks

**"schedule does not reconcile to 162 games"** — almost always a postponement MLB hasn't
rescheduled yet, which leaves two clubs a game short. Either re-run tomorrow, or add the
makeup to `SYNTHETIC_GAMES` at the top of `src/fetch_data.py`; anything listed there is
disclosed in the page footnote. Remove it once the real game appears.

**Baseball-Reference comparison missing** — that scrape is best-effort. If B-Ref changes
its markup the pill just disappears; the build still succeeds. Fix the regex in
`bref_odds()` if you want it back.

**Deploy step fails with "NETLIFY_AUTH_TOKEN is not set"** — step 3 above.

**Season's over** — the workflow keeps running and will start failing once the schedule
is empty. Disable it in the Actions tab, or delete the repo.

## Notes

- Ties are broken at random rather than by head-to-head record.
- The model knows run differential. It does not know about injuries, rotations, or
  September call-ups.
- Not affiliated with or endorsed by the Toronto Blue Jays or MLB.
