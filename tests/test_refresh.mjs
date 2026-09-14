/*
 * The manual-refresh function, with GitHub mocked out.
 *
 * netlify/functions/refresh.mjs is the only part of the tracker that can spend
 * Actions minutes on a stranger's click, so its guards are what this checks:
 * nothing dispatched while a run is active, nothing dispatched inside the
 * cooldown, and a clear answer (never a dispatch) when the token is missing or
 * GitHub errors. Drives the real handler with real Request objects over a fake
 * fetch, so the routing, the JSON shapes the page relies on, and the exact
 * dispatch body are all exercised.
 *
 * Run:  node tests/test_refresh.mjs
 */
import { pathToFileURL } from "node:url";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const mod = await import(pathToFileURL(path.join(HERE, "..", "netlify", "functions", "refresh.mjs")).href);
const handler = mod.default;

const fails = [];
function check(cond, msg) { if (!cond) fails.push(msg); }

// ---- a fake GitHub ---------------------------------------------------------
let runs = [];
let dispatches = [];
let listStatus = 200;
globalThis.fetch = async (url, init = {}) => {
  const u = String(url);
  if (u.endsWith("/dispatches")) {
    dispatches.push({ url: u, headers: init.headers, body: JSON.parse(init.body) });
    return new Response(null, { status: 204 });
  }
  if (u.includes("/runs?")) {
    return new Response(JSON.stringify({ workflow_runs: runs }), {
      status: listStatus, headers: { "content-type": "application/json" },
    });
  }
  throw new Error("unexpected URL " + u);
};
globalThis.Netlify = { env: { get: (k) => process.env[k] } };

const minutesAgo = (m) => new Date(Date.now() - m * 60000).toISOString();
const run = (id, status, conclusion, mins, event = "schedule") =>
  ({ id, status, conclusion, event, created_at: minutesAgo(mins), updated_at: minutesAgo(mins) });
const call = async (method) => {
  const res = await handler(new Request("https://example.test/api/refresh", { method }));
  return { status: res.status, body: await res.json() };
};

// ---- 1. no token: says so, never touches GitHub --------------------------------
delete process.env.GITHUB_DISPATCH_TOKEN;
let r = await call("POST");
check(r.status === 503 && r.body.state === "unconfigured", `no token -> 503 unconfigured, got ${r.status} ${r.body.state}`);
check(dispatches.length === 0, "no token must not dispatch");

process.env.GITHUB_DISPATCH_TOKEN = "ghp_test";
process.env.GITHUB_REPO = "someone/tracker";

// ---- 2. a run is in progress: report it, don't stack another ------------------
runs = [run(11, "in_progress", null, 1, "workflow_dispatch"), run(10, "completed", "success", 40)];
r = await call("POST");
check(r.status === 200 && r.body.state === "running" && r.body.run.id === 11, `active run -> 200 running #11, got ${r.status} ${JSON.stringify(r.body)}`);
check(dispatches.length === 0, "active run must not dispatch");
r = await call("GET");
check(r.body.state === "running" && r.body.run.id === 11, "GET reports the active run");

// ---- 3. inside the cooldown: 429 with a wait, no dispatch -----------------------
runs = [run(12, "completed", "success", 3)];
r = await call("POST");
check(r.status === 429 && r.body.state === "cooldown", `recent run -> 429 cooldown, got ${r.status} ${r.body.state}`);
check(r.body.retry_after_sec > 0 && r.body.retry_after_sec <= 7 * 60, `retry_after_sec should be about 7 min, got ${r.body.retry_after_sec}`);
check(dispatches.length === 0, "cooldown must not dispatch");
r = await call("GET");
check(r.body.state === "idle" && r.body.run.id === 12, "GET during cooldown is idle, reporting the latest run");

// ---- 4. idle and cold: dispatch, with the cheap-check input -------------------
runs = [run(12, "completed", "success", 25)];
r = await call("POST");
check(r.status === 202 && r.body.state === "dispatched", `idle -> 202 dispatched, got ${r.status} ${r.body.state}`);
check(r.body.after_id === 12, `after_id should be the latest run id (12), got ${r.body.after_id}`);
check(dispatches.length === 1, `exactly one dispatch, got ${dispatches.length}`);
if (dispatches.length === 1) {
  const d = dispatches[0];
  check(d.url === "https://api.github.com/repos/someone/tracker/actions/workflows/nightly.yml/dispatches", `dispatch URL wrong: ${d.url}`);
  check(d.body.ref === "main", `dispatch ref should default to main, got ${d.body.ref}`);
  check(d.body.inputs && d.body.inputs.only_if_changed === "true", `dispatch must set only_if_changed="true", got ${JSON.stringify(d.body.inputs)}`);
  check(d.headers.authorization === "Bearer ghp_test", "dispatch must carry the token");
}

// ---- 5. no runs at all yet (fresh repo): still dispatches ----------------------
runs = [];
r = await call("POST");
check(r.status === 202 && r.body.after_id === 0, `no history -> 202 with after_id 0, got ${r.status} ${r.body.after_id}`);

// ---- 6. GitHub down: a 502, never a dispatch ------------------------------------
dispatches = [];
listStatus = 500;
r = await call("POST");
check(r.status === 502 && r.body.state === "error", `GitHub 500 -> 502 error, got ${r.status} ${r.body.state}`);
check(dispatches.length === 0, "GitHub error must not dispatch");
listStatus = 200;

// ---- 7. anything else is refused ----------------------------------------------
r = await call("DELETE");
check(r.status === 405, `DELETE -> 405, got ${r.status}`);

// ---- 8. routing: the page calls /api/refresh ----------------------------------
check(mod.config && mod.config.path === "/api/refresh", "config.path must be /api/refresh");

console.log("=".repeat(62));
if (fails.length) {
  console.log("REFRESH TEST FAILED");
  for (const f of fails) console.log("  -", f);
  process.exit(1);
}
console.log("REFRESH TEST PASSED");
console.log("  unconfigured, running, cooldown and GitHub-error all refuse to dispatch");
console.log("  an idle site dispatches once, on main, with only_if_changed set");
