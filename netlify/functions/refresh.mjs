/* Manual refresh for the tracker page.
 *
 * The page is a static file that GitHub Actions rebuilds and publishes, so "refresh"
 * cannot mean fetching data in the browser — it means asking Actions to run the
 * pipeline now. A browser cannot hold a GitHub token, so this function holds one
 * for it: the page POSTs here, this dispatches the workflow, and the page polls
 * GET here for the run's progress.
 *
 *   POST /api/refresh   -> 202 dispatched | 200 running | 429 cooldown
 *                          503 unconfigured | 502 GitHub error
 *   GET  /api/refresh   -> 200 { state: "running" | "idle", run: {...} | null }
 *
 * The button is public, and every dispatch spends Actions minutes, so two guards:
 *   * nothing is dispatched while a run is queued or in progress, and
 *   * nothing is dispatched within COOLDOWN_MIN of the previous run, whatever
 *     started it — a fan cannot ask more often than the schedule polls anyway.
 * The dispatch also sets only_if_changed, so a click when nothing has finished is
 * the cheap standings check and no rebuild, exactly like a scheduled tick.
 *
 * Setup: a fine-grained GitHub token with Actions read+write on this repository,
 * stored in the Netlify site as GITHUB_DISPATCH_TOKEN. Without it the function
 * answers 503 and the page says the button is not set up, rather than failing
 * the deploy or the build — the page itself never depends on this.
 */

export const config = { path: "/api/refresh" };

const DEFAULT_REPO = "anoojanv/jays-playoff-tracker";
const WORKFLOW = "nightly.yml";
const COOLDOWN_MIN = 10;
const ACTIVE = new Set(["queued", "in_progress", "waiting", "pending", "requested"]);

function env(name) {
  if (typeof Netlify !== "undefined" && Netlify.env && Netlify.env.get) return Netlify.env.get(name);
  return process.env[name];
}

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

function summary(run) {
  if (!run) return null;
  return {
    id: run.id, status: run.status, conclusion: run.conclusion, event: run.event,
    created_at: run.created_at, updated_at: run.updated_at,
  };
}

async function github(repo, token, path, init = {}) {
  return fetch(`https://api.github.com/repos/${repo}/${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${token}`,
      accept: "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "jays-tracker-refresh",
      ...(init.headers || {}),
    },
  });
}

export default async (req) => {
  if (req.method !== "GET" && req.method !== "POST") {
    return json(405, { state: "error", message: "GET or POST only." });
  }
  const token = env("GITHUB_DISPATCH_TOKEN");
  if (!token) {
    return json(503, {
      state: "unconfigured",
      message: "Manual refresh is not set up on this site: GITHUB_DISPATCH_TOKEN is missing.",
    });
  }
  const repo = env("GITHUB_REPO") || DEFAULT_REPO;
  const ref = env("GITHUB_DISPATCH_REF") || "main";

  const listed = await github(repo, token, `actions/workflows/${WORKFLOW}/runs?per_page=5`);
  if (!listed.ok) {
    return json(502, { state: "error", message: `GitHub would not list runs (HTTP ${listed.status}).` });
  }
  const runs = ((await listed.json()).workflow_runs || []);
  const active = runs.find((r) => ACTIVE.has(r.status));
  const latest = runs[0] || null;

  if (req.method === "GET") {
    return json(200, { state: active ? "running" : "idle", run: summary(active || latest) });
  }

  if (active) {
    return json(200, { state: "running", message: "A refresh is already running.", run: summary(active) });
  }
  if (latest) {
    const ageSec = (Date.now() - Date.parse(latest.created_at)) / 1000;
    const waitSec = COOLDOWN_MIN * 60 - ageSec;
    if (waitSec > 0) {
      return json(429, {
        state: "cooldown",
        message: `Checked ${Math.max(1, Math.round(ageSec / 60))} min ago.`,
        retry_after_sec: Math.ceil(waitSec),
        run: summary(latest),
      });
    }
  }

  const dispatched = await github(repo, token, `actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    // strings, which is what `gh workflow run -f` sends for a boolean input
    body: JSON.stringify({ ref, inputs: { only_if_changed: "true" } }),
  });
  if (dispatched.status !== 204) {
    return json(502, { state: "error", message: `GitHub refused the dispatch (HTTP ${dispatched.status}).` });
  }
  // the run does not exist yet — GitHub creates it a few seconds after the dispatch —
  // so the page needs to know which runs are older than its request
  return json(202, {
    state: "dispatched",
    message: "Asked GitHub to check for new results.",
    after_id: latest ? latest.id : 0,
    cooldown_min: COOLDOWN_MIN,
  });
};
