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

That's it. From then on it runs itself at **10:07pm Eastern** every night.

---

## What runs each night

| | |
|---|---|
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
