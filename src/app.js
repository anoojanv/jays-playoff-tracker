/* Maple Leafs playoff tracker — in-browser Monte Carlo.
   Same model as the Python build: log5 matchup plus home ice, a separate draw for whether
   a game goes past regulation (which decides the loser point), points then regulation
   wins then a coin, three per division plus two wild cards per conference.

   It re-simulates the focus conference only. Nothing on the page can move a game between
   two clubs of the other conference, so those are left out and a re-run stays fast; the
   other conference's champion, needed for the Final, is sampled from the Python run.

   Two controls drive one scenario: the slider fixes Toronto's rest-of-season points, and
   the scoreboard hot/cold toggles bias a rival's remaining games. Both round-trip
   through the URL hash, so a scenario can be shared. */

/* Manual refresh. The page is static, so "refresh" means asking GitHub Actions to run
   the pipeline now: POST /api/refresh (a Netlify function holding the token — see
   netlify/functions/refresh.mjs) dispatches it, GET polls the run, and when the run
   finishes the page re-reads ITSELF and compares the data-fingerprint meta — the same
   "the published page is its own state file" trick the nightly poll uses — so it
   reloads only when the data actually changed, and says so plainly when it did not.
   Same-origin, no token in the browser, and nothing stored on the client. */
(function () {
  "use strict";
  var btn = document.getElementById("refreshBtn"), msg = document.getElementById("refreshMsg");
  if (!btn || !msg) return;
  var POLL_MS = 8000, START_GRACE_MS = 90000, RUN_TIMEOUT_MS = 6 * 60000;
  var mine = document.querySelector('meta[name="data-fingerprint"]');
  var myFp = mine ? mine.getAttribute("content") : "";
  var timer = null;

  function say(text, tone) {
    msg.textContent = text;
    msg.className = "rfmsg" + (tone ? " " + tone : "");
  }
  function busy(on) {
    btn.disabled = on;
    btn.classList.toggle("spin", on);
  }
  function minutes(sec) { return Math.max(1, Math.ceil(sec / 60)); }

  function api(method) {
    return fetch("/api/refresh", { method: method, cache: "no-store",
                                   headers: { accept: "application/json" } })
      .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); });
  }

  // did the rebuild publish something new? read the live page and compare fingerprints
  function settle() {
    return fetch(location.pathname + "?r=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var m = /<meta name="data-fingerprint" content="([^"]*)"/.exec(html);
        if (m && m[1] && m[1] !== myFp) {
          say("New results are in — reloading…", "ok");
          setTimeout(function () { location.reload(); }, 600);
        } else {
          say("Already up to date — nothing has finished since the last publish.", "ok");
          busy(false);
        }
      }, function () {
        say("Rebuilt — reload the page to see it.", "ok");
        busy(false);
      });
  }

  function watch(afterId, t0) {
    timer = setInterval(function () {
      var elapsed = Date.now() - t0;
      api("GET").then(function (r) {
        var run = r.body && r.body.run;
        var ours = run && run.id > afterId;
        if (!ours) {
          if (elapsed > START_GRACE_MS) {
            stop(); say("GitHub has not picked it up yet — check back in a minute.", "");
          }
          return;
        }
        if (run.status !== "completed") {
          if (elapsed > RUN_TIMEOUT_MS) {
            stop(); say("Still running — the page will update on its own when it finishes.", "");
          } else {
            say("Rebuilding… (usually 1–3 minutes)", "");
          }
          return;
        }
        stop();
        if (run.conclusion === "success") settle();
        else { say("The rebuild failed — the last good page stays up.", "bad"); busy(false); }
      }, function () { /* one bad poll is not a verdict; try again next tick */ });
    }, POLL_MS);
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
    busy(false);
  }

  btn.addEventListener("click", function () {
    if (btn.disabled) return;
    busy(true);
    say("Asking GitHub to check for new results…", "");
    api("POST").then(function (r) {
      var b = r.body || {};
      if (r.status === 202) {
        busy(true);
        say("Checking the NHL for new results…", "");
        watch(b.after_id || 0, Date.now());
      } else if (r.status === 200 && b.state === "running") {
        busy(true);
        say("A refresh is already running — waiting for it…", "");
        watch((b.run && b.run.id - 1) || 0, Date.now());
      } else if (r.status === 429) {
        busy(false);
        say((b.message || "Checked recently.") + " Try again in " + minutes(b.retry_after_sec || 60) + " min.", "");
      } else if (r.status === 503) {
        busy(false);
        say("Manual refresh is not set up on this site yet.", "bad");
      } else {
        busy(false);
        say(b.message || "Could not start a refresh.", "bad");
      }
    }, function () {
      busy(false);
      say("Refresh needs the live site — it cannot run from a local copy.", "bad");
    });
  });
})();

/* Sticky-nav scrollspy: highlight the section currently on screen. Independent of the
   simulator so it still runs if the sim data is ever missing. */
(function () {
  "use strict";
  var nav = document.querySelector(".snav");
  if (!nav || !("IntersectionObserver" in window)) return;
  var byId = {}, current = null;
  var links = [].slice.call(nav.querySelectorAll("a[href^='#']"));
  links.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      var a = byId[e.target.id];
      if (!a || a === current) return;
      if (current) current.classList.remove("act");
      current = a;
      a.classList.add("act");
    });
  }, { rootMargin: "-15% 0px -65% 0px" });
  links.forEach(function (a) {
    var t = document.getElementById(a.getAttribute("href").slice(1));
    if (t) obs.observe(t);
  });
})();

(function () {
  "use strict";
  var D = window.__SIM__;
  if (!D) return;

  var NT = D.teams.length, NG = D.gH.length, J = D.focusIdx, NF = D.nFocusGames;
  var gH = D.gH, gA = D.gA, gP = D.gP, gJ = D.gJ;
  var NSIM_FULL = 5000, NSIM_DRAG = 1200;          // fewer seasons while a drag is live
  var P_OT = D.pOt, HFA = D.hfa, TAL = D.talent, SER = D.series;
  var CONF = D.confIdx, DIVS = D.divs, DIVN = D.divNames, P = D.confPrefix;
  var inConf = new Uint8Array(NT);
  for (var ci = 0; ci < CONF.length; ci++) inConf[CONF[ci]] = 1;
  var GL = NF, TOTAL_PTS = 2 * NF;

  // scratch buffers reused across every simulation
  var pts = new Int32Array(NT), rw = new Int32Array(NT), score = new Float64Array(NT);
  var divRank = new Int8Array(NT), wcRank = new Int8Array(NT), teamIn = new Float64Array(NT);
  var focusRes = new Int8Array(NF);                 // 2 win, 1 overtime loss, 0 reg. loss
  var order = [];

  /* Rival hot/cold: a shift in logit space on every game that club plays, sized so the
     forced finish lands near the 25th/75th-percentile points the bars describe: over G
     games the quartile sits ~0.674·√G/2 wins from the mean, and a logit shift of s moves a
     near-even game by ~s/4, so s = 1.348/√G moves the mean by that much. */
  var rivalMode = new Int8Array(NT);
  var teamG = new Int32Array(NT);
  for (var g0 = 0; g0 < NG; g0++) { teamG[gH[g0]]++; teamG[gA[g0]]++; }
  function biasFor(t) { return 1.348 / Math.sqrt(Math.max(4, teamG[t])); }
  var gPeff = Float64Array.from(gP);
  function rebuildEff() {
    for (var g = 0; g < NG; g++) {
      var p = gP[g];
      var sh = rivalMode[gH[g]] * biasFor(gH[g]) - rivalMode[gA[g]] * biasFor(gA[g]);
      if (sh) {
        p = Math.min(0.999, Math.max(0.001, p));
        p = 1 / (1 + Math.exp(-(Math.log(p / (1 - p)) + sh)));
      }
      gPeff[g] = p;
    }
  }
  function anyBias() {
    for (var t = 0; t < NT; t++) if (rivalMode[t]) return true;
    return false;
  }

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  /* The playoffs. Every round best of seven, 2-2-1-1-1, home ice to the better regular
     season. Playing all seven rather than stopping at four gives the identical winner —
     whoever gets there first holds the majority — and keeps the loop branchless. */
  function pGame(ta, tb, aHome) {
    var p = (ta - ta * tb) / (ta + tb - 2 * ta * tb), o;
    if (aHome) { o = p / (1 - p) * HFA; return o / (1 + o); }
    o = (1 - p) / p * HFA;
    return 1 / (1 + o);
  }
  function series(a, b, sa, sb, rand) {
    var hi = sa >= sb ? a : b, lo = sa >= sb ? b : a, w = 0;
    for (var i = 0; i < SER.length; i++) if (rand() < pGame(TAL[hi], TAL[lo], !!SER[i])) w++;
    return w > (SER.length >> 1) ? hi : lo;
  }
  // the other conference's champion, sampled from the Python run (nothing on this page
  // can change a game between two clubs of the other conference)
  var OC = D.otherChamps || [], ocTot = 0;
  for (var oi = 0; oi < OC.length; oi++) ocTot += OC[oi].p;
  function otherChamp(rand) {
    var u = rand() * ocTot;
    for (var i = 0; i < OC.length; i++) { u -= OC[i].p; if (u <= 0) return OC[i]; }
    return OC[OC.length - 1];
  }

  var NODES = [P + "1", P + "2", P + "3", P + "4", P + "5", P + "6", P + "7", P + "8",
               P + "r1a", P + "r1b", P + "r1c", P + "r1d", P + "r2a", P + "r2b",
               P + "cf", "cup"];
  var NN = NODES.length;
  var nodeCt = new Float64Array(NN * NT), roadCt = new Float64Array(4);
  var seatCt = new Float64Array(9), seatOpp = new Float64Array(9 * NT);
  var seatHost = new Float64Array(9), seat = new Int32Array(8);
  var PARTNER = [1, 0, 3, 2, 5, 4, 7, 6];

  function rankConference(rand) {
    var t, d, k;
    for (t = 0; t < CONF.length; t++) {
      var c = CONF[t];
      score[c] = pts[c] + rw[c] * 1e-3 + rand() * 1e-5;
      divRank[c] = 0; wcRank[c] = 0;
    }
    for (d = 0; d < DIVS.length; d++) {
      order = DIVS[d].slice();
      order.sort(function (x, y) { return score[y] - score[x]; });
      for (k = 0; k < order.length; k++) divRank[order[k]] = k + 1;
    }
    order = [];
    for (t = 0; t < CONF.length; t++) if (divRank[CONF[t]] > 3) order.push(CONF[t]);
    order.sort(function (x, y) { return score[y] - score[x]; });
    if (order.length > 0) wcRank[order[0]] = 1;
    if (order.length > 1) wcRank[order[1]] = 2;
  }

  function divSeat(d, rank) {
    for (var i = 0; i < DIVS[d].length; i++) if (divRank[DIVS[d][i]] === rank) return DIVS[d][i];
    return -1;
  }

  function simulate(target, nsim, seed) {
    var rand = mulberry32(seed >>> 0);
    var inCount = 0, ptsSum = 0, cutSum = 0, t, g, i, k;
    for (t = 0; t < NT; t++) teamIn[t] = 0;
    nodeCt.fill(0); roadCt.fill(0); seatCt.fill(0); seatOpp.fill(0); seatHost.fill(0);
    var w = target === null ? 0 : target >> 1, o = target === null ? 0 : target & 1;

    for (var it = 0; it < nsim; it++) {
      // the slider fixes Toronto's points; which games they come from is spread at random
      if (target !== null) {
        for (i = 0; i < NF; i++) focusRes[i] = i < w ? 2 : (i < w + o ? 1 : 0);
        for (i = NF - 1; i > 0; i--) {
          var j = (rand() * (i + 1)) | 0, tmp = focusRes[i];
          focusRes[i] = focusRes[j]; focusRes[j] = tmp;
        }
      }
      for (t = 0; t < CONF.length; t++) { pts[CONF[t]] = D.basePts[CONF[t]]; rw[CONF[t]] = D.baseRw[CONF[t]]; }

      for (g = 0; g < NG; g++) {
        var h = gH[g], a = gA[g], s = gJ[g], hw, ot;
        if (s >= 0 && target !== null) {
          var fw = focusRes[s] === 2;
          hw = (h === J) ? fw : !fw;
          ot = focusRes[s] === 1 ? true : (fw ? rand() < P_OT : false);
        } else {
          hw = rand() < gPeff[g];
          ot = rand() < P_OT;
        }
        if (hw) {
          if (inConf[h]) { pts[h] += 2; if (!ot) rw[h]++; }
          if (ot && inConf[a]) pts[a] += 1;
        } else {
          if (inConf[a]) { pts[a] += 2; if (!ot) rw[a]++; }
          if (ot && inConf[h]) pts[h] += 1;
        }
      }

      rankConference(rand);
      for (t = 0; t < CONF.length; t++) {
        var c = CONF[t];
        if (divRank[c] <= 3 || wcRank[c] > 0) teamIn[c]++;
        if (wcRank[c] === 2) cutSum += pts[c];
      }
      ptsSum += pts[J];
      if (!(divRank[J] <= 3 || wcRank[J] > 0)) continue;
      inCount++;

      // seat the conference: the better division winner draws the second wild card
      var w1 = divSeat(0, 1), w2 = divSeat(1, 1), wc1 = -1, wc2 = -1;
      for (t = 0; t < CONF.length; t++) {
        if (wcRank[CONF[t]] === 1) wc1 = CONF[t];
        if (wcRank[CONF[t]] === 2) wc2 = CONF[t];
      }
      var top1 = score[w1] > score[w2];
      seat[0] = w1; seat[1] = top1 ? wc2 : wc1; seat[2] = divSeat(0, 2); seat[3] = divSeat(0, 3);
      seat[4] = w2; seat[5] = top1 ? wc1 : wc2; seat[6] = divSeat(1, 2); seat[7] = divSeat(1, 3);
      var js = 0;
      for (k = 0; k < 8; k++) { nodeCt[k * NT + seat[k]]++; if (seat[k] === J) js = k; }
      seatCt[js + 1]++;
      var opp = seat[PARTNER[js]];
      seatOpp[(js + 1) * NT + opp]++;
      if (score[J] > score[opp]) seatHost[js + 1]++;

      var r1 = [series(seat[0], seat[1], score[seat[0]], score[seat[1]], rand),
                series(seat[2], seat[3], score[seat[2]], score[seat[3]], rand),
                series(seat[4], seat[5], score[seat[4]], score[seat[5]], rand),
                series(seat[6], seat[7], score[seat[6]], score[seat[7]], rand)];
      for (k = 0; k < 4; k++) nodeCt[(8 + k) * NT + r1[k]]++;
      var r2a = series(r1[0], r1[1], score[r1[0]], score[r1[1]], rand);
      var r2b = series(r1[2], r1[3], score[r1[2]], score[r1[3]], rand);
      nodeCt[12 * NT + r2a]++; nodeCt[13 * NT + r2b]++;
      var cf = series(r2a, r2b, score[r2a], score[r2b], rand);
      nodeCt[14 * NT + cf]++;
      var cup = cf;
      if (OC.length) {
        var oc = otherChamp(rand);
        cup = series(cf, oc.t, score[cf], oc.pts, rand);
      }
      nodeCt[15 * NT + cup]++;
      if (r1[0] === J || r1[1] === J || r1[2] === J || r1[3] === J) roadCt[0]++;
      if (r2a === J || r2b === J) roadCt[1]++;
      if (cf === J) roadCt[2]++;
      if (cup === J) roadCt[3]++;
    }

    var odds = new Float64Array(NT);
    for (t = 0; t < NT; t++) odds[t] = teamIn[t] / nsim;
    return { odds: inCount / nsim, teamOdds: odds, meanPts: ptsSum / nsim,
             cut: cutSum / nsim, nsim: nsim,
             bracket: inCount ? readBracket(inCount) : null };
  }

  /* Tallies into the shape the bracket renders from, as shares of the seasons Toronto
     QUALIFIED in. One club per slot so the bracket reads as one picture — the same rule
     as model.coherent_picks: Toronto pinned to its likeliest seat and its likeliest
     opponent from there across from it, the other seats filled greedily with each club
     used once, then every later slot taking whichever of its two feeders wins it more. */
  var FEED = [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9], [10, 11], [12, 13]];   // nodes 8..14
  function readBracket(nIn) {
    var k, t, n, best = 1;
    for (k = 1; k <= 8; k++) if (seatCt[k] > seatCt[best]) best = k;
    var bo = -1, bc = 0;
    for (t = 0; t < NT; t++) if (seatOpp[best * NT + t] > bc) { bc = seatOpp[best * NT + t]; bo = t; }

    var pick = new Int32Array(NN).fill(-1), used = {};
    pick[best - 1] = J; used[J] = 1;
    if (bo >= 0) { pick[PARTNER[best - 1]] = bo; used[bo] = 1; }
    var cand = [];
    for (n = 0; n < 8; n++) {
      if (pick[n] >= 0) continue;
      for (t = 0; t < NT; t++) if (nodeCt[n * NT + t]) cand.push([nodeCt[n * NT + t], n, t]);
    }
    cand.sort(function (x, y) { return y[0] - x[0] || x[1] - y[1] || x[2] - y[2]; });
    for (k = 0; k < cand.length; k++) {
      n = cand[k][1]; t = cand[k][2];
      if (pick[n] < 0 && !used[t]) { pick[n] = t; used[t] = 1; }
    }
    function better(node, a, b) {
      if (a < 0) return b;
      if (b < 0) return a;
      return nodeCt[node * NT + b] > nodeCt[node * NT + a] ? b : a;
    }
    for (n = 8; n < 15; n++) pick[n] = better(n, pick[FEED[n - 8][0]], pick[FEED[n - 8][1]]);
    pick[15] = better(15, pick[14], OC.length ? OC[0].t : -1);

    var nodes = {};
    for (n = 0; n < NN; n++) {
      var rows = [];
      for (t = 0; t < NT; t++) {
        var c = nodeCt[n * NT + t];
        if (c) rows.push({ team: t, p: c / nIn });
      }
      rows.sort(function (x, y) { return y.p - x.p; });
      if (pick[n] >= 0) {
        var pk = pick[n], mine = rows.filter(function (r) { return r.team === pk; });
        rows = (mine.length ? mine : [{ team: pk, p: 0 }])
          .concat(rows.filter(function (r) { return r.team !== pk; }));
      }
      nodes[NODES[n]] = rows;
    }
    return { nodes: nodes, bestSeat: best, bestSeatP: seatCt[best] / nIn,
             bestOpp: bo, hosts: seatCt[best] ? seatHost[best] / seatCt[best] : 0,
             road: { r1: roadCt[0] / nIn, r2: roadCt[1] / nIn, cf: roadCt[2] / nIn,
                     cup: roadCt[3] / nIn } };
  }

  /* ---------------------------------------------------------------- state ---- */
  var target = null;                         // null = let the model play it out
  var baseline = D.baselineOdds;
  var el = function (id) { return document.getElementById(id); };
  var lastOdds = baseline, tween = null, dragging = false;

  function animateOdds(from, to, instant) {
    if (tween) cancelAnimationFrame(tween);
    var node = el("liveOdds"), bar = el("liveBar");
    function paint(v) {
      node.textContent = (v * 100).toFixed(1);
      if (bar) bar.style.width = Math.min(100, v * 100) + "%";
    }
    if (instant) { paint(to); return; }
    var t0 = performance.now(), dur = 400;
    (function step(now) {
      var p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      paint(from + (to - from) * e);
      if (p < 1) tween = requestAnimationFrame(step);
    })(t0);
  }

  var pending = null;
  function recompute(opts) {
    opts = opts || {};
    if (pending) cancelAnimationFrame(pending);
    pending = requestAnimationFrame(function () { pending = null; recomputeNow(opts); });
  }

  function recomputeNow(opts) {
    var t0 = performance.now();
    var r = simulate(target, opts.fast ? NSIM_DRAG : NSIM_FULL, 12345);
    var ms = performance.now() - t0;
    animateOdds(lastOdds, r.odds, !!opts.fast);
    lastOdds = r.odds;

    var anySet = target !== null || anyBias();
    var dEl = el("liveDelta"), diff = r.odds - baseline;
    if (!anySet) {
      dEl.textContent = "model baseline — nothing set yet";
      dEl.className = "livedelta";
    } else {
      dEl.textContent = (diff >= 0 ? "+" : "−") + Math.abs(diff * 100).toFixed(1) +
        " pts vs baseline (" + (baseline * 100).toFixed(1) + "%)";
      dEl.className = "livedelta " + (diff >= 0.001 ? "up" : diff <= -0.001 ? "down" : "");
    }
    el("liveProj").textContent = r.meanPts.toFixed(1);
    el("liveCut").textContent = r.cut.toFixed(1);
    var cupEl = el("liveCup");
    if (cupEl) cupEl.textContent = r.bracket ? (r.odds * r.bracket.road.cup * 100).toFixed(1) + "%" : "0.0%";

    for (var t = 0; t < NT; t++) {
      if (!inConf[t]) continue;
      var f = document.querySelector('[data-oddsbar="' + t + '"]');
      var n2 = document.querySelector('[data-oddsnum="' + t + '"]');
      if (f) f.style.width = (r.teamOdds[t] * 100).toFixed(0) + "%";
      if (n2) n2.textContent = (r.teamOdds[t] * 100).toFixed(0) + "%";
    }

    var mk = el("scenMark"), lab = el("scenMarkLab");
    if (mk && !anySet) {
      mk.style.opacity = 0; lab.style.opacity = 0;
    } else if (mk) {
      var x = D.curveX0 + (r.meanPts - D.curveP0) / (D.curveP1 - D.curveP0) * (D.curveX1 - D.curveX0);
      x = Math.max(D.curveX0, Math.min(D.curveX1, x));
      mk.setAttribute("x1", x); mk.setAttribute("x2", x); mk.style.opacity = 1;
      var right = x > (D.curveX0 + D.curveX1) / 2;
      lab.setAttribute("x", x); lab.setAttribute("text-anchor", right ? "end" : "start");
      lab.setAttribute("dx", right ? -5 : 5);
      lab.textContent = "YOUR SCENARIO " + r.meanPts.toFixed(1) + " PTS";
      lab.style.opacity = 1;
    }

    var sl = el("ptsSlider");
    if (sl && !dragging && !opts.fromSlider) {
      sl.value = target === null ? Math.round(D.projPts - D.basePts[J]) : target;
      paintSlider();
    }
    if (!opts.fast) paintBracket(r.bracket);
    var perf = el("perfNote");
    if (perf) perf.textContent = r.nsim.toLocaleString() + " seasons · " + ms.toFixed(0) + " ms";
    if (!opts.fast) writeHash();
  }

  /* ---------------------------------------------------------------- bracket ---- */
  function ordinal(n) {
    var s = ["th", "st", "nd", "rd"], v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  }
  function roleOf(seatNo) {
    var d = DIVN[seatNo <= 4 ? 0 : 1];
    return ["winning the " + d, "a wild card", "2nd in the " + d, "3rd in the " + d][(seatNo - 1) % 4];
  }
  function paintBracket(bk) {
    var head = el("bkHead");
    if (!head) return;
    var nodesEl = document.querySelectorAll("[data-node]");
    for (var i = 0; i < nodesEl.length; i++) {
      var key = nodesEl[i].dataset.node;
      if (key !== "cup" && key.charAt(0) !== P) continue;     // the other conference is fixed
      var rows = bk ? (bk.nodes[key] || []) : [], top = rows[0];
      nodesEl[i].classList.toggle("you", !!top && top.team === J);
      nodesEl[i].querySelector("[data-bk-team]").textContent = top ? D.teams[top.team] : "—";
      nodesEl[i].querySelector("[data-bk-p]").textContent = top ? Math.round(top.p * 100) + "%" : "";
      var fill = nodesEl[i].querySelector("[data-bk-fill]");
      if (fill) fill.style.width = (top ? top.p * 100 : 0) + "%";
      nodesEl[i].title = rows.slice(0, 3).map(function (r) {
        return D.teams[r.team] + " " + Math.round(r.p * 100) + "%";
      }).join(", ");
    }
    if (!bk) { head.textContent = "No qualifying seasons left to draw a bracket from."; return; }
    ["r1", "r2", "cf", "cup"].forEach(function (k) {
      var bar = document.querySelector('[data-road="' + k + '"]');
      var val = document.querySelector('[data-road-v="' + k + '"]');
      if (bar) bar.style.width = (bk.road[k] * 100).toFixed(0) + "%";
      if (val) val.textContent = (bk.road[k] * 100).toFixed(k === "cup" ? 1 : 0) + "%";
    });
    var opp = bk.bestOpp >= 0 ? D.names[bk.bestOpp] : null;
    head.innerHTML = "Most likely <b>" + roleOf(bk.bestSeat) + "</b> (" +
      Math.round(bk.bestSeatP * 100) + "% of qualifying seasons)" +
      (opp ? ", " + (bk.hosts >= 0.5 ? "hosting" : "at") + " <b>the " + opp +
             "</b> in the first round" : "");
  }

  /* ------------------------------------------------------------ share the scenario ----
     The scenario lives in the URL hash — Toronto's points as s=, rival biases as
     teamIndex+h/c — so a fan can send the exact path as a link. replaceState, not
     assignment, so dragging never scrolls the page or pollutes history. */
  var lastHash = null;
  function writeHash() {
    var parts = [];
    if (target !== null) parts.push("s=" + target);
    var bs = [];
    for (var t = 0; t < NT; t++) if (rivalMode[t]) bs.push(t + (rivalMode[t] > 0 ? "h" : "c"));
    if (bs.length) parts.push("r=" + bs.join("."));
    var h = parts.join("&");
    if (h === lastHash) return;
    lastHash = h;
    if (history.replaceState) history.replaceState(null, "", h ? "#" + h : location.pathname + location.search);
  }
  function readHash() {
    var h = location.hash.slice(1), got = false;
    if (!h) return false;
    h.split("&").forEach(function (kv) {
      var i = kv.indexOf("=");
      if (i < 0) return;
      var k = kv.slice(0, i), v = kv.slice(i + 1);
      if (k === "s") {
        var n = parseInt(v, 10);
        if (n >= 0 && n <= TOTAL_PTS) { target = n; got = true; }
      } else if (k === "r") {
        v.split(".").forEach(function (tok) {
          var m = /^(\d+)([hc])$/.exec(tok);
          if (m && +m[1] < NT && +m[1] !== J && inConf[+m[1]]) {
            rivalMode[+m[1]] = m[2] === "h" ? 1 : -1; got = true;
          }
        });
      }
    });
    return got;
  }

  /* ---------------------------------------------------------------- slider ---- */
  var sl = el("ptsSlider");
  function paintSlider() {
    if (!sl) return;
    var v = +sl.value;
    sl.style.setProperty("--fill", (v / TOTAL_PTS * 100) + "%");
    var lab = el("sliderVal");
    if (lab) lab.textContent = v + " pts";
    var pace = el("sliderPace");
    if (pace) pace.textContent = (v / TOTAL_PTS).toFixed(3).replace(/^0/, "") +
      " points pace over the last " + GL + " games";
  }
  if (sl) {
    sl.max = TOTAL_PTS;
    sl.value = Math.round(D.projPts - D.basePts[J]);
    paintSlider();
    var fromSlider = function (fast) {
      target = +sl.value;
      paintSlider();
      recompute({ fast: fast, fromSlider: true });
    };
    sl.addEventListener("pointerdown", function () { dragging = true; });
    sl.addEventListener("input", function () { fromSlider(true); });
    sl.addEventListener("change", function () { dragging = false; fromSlider(false); });
    sl.addEventListener("pointerup", function () { dragging = false; });
    sl.addEventListener("keyup", function () { dragging = false; fromSlider(false); });
  }

  /* ---------------------------------------------------------------- rivals ---- */
  function syncRivalBtns() {
    document.querySelectorAll("[data-rival]").forEach(function (b) {
      var on = rivalMode[+b.dataset.rival] === +b.dataset.mode;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  document.querySelectorAll("[data-rival]").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = +b.dataset.rival, m = +b.dataset.mode;
      rivalMode[t] = (rivalMode[t] === m) ? 0 : m;        // click again to release
      syncRivalBtns(); rebuildEff(); recompute({});
    });
  });

  /* ---------------------------------------------------------------- presets ---- */
  document.querySelectorAll("[data-preset]").forEach(function (b) {
    b.addEventListener("click", function () {
      var p = b.dataset.preset;
      if (p === "reset") {
        target = null;
        for (var t = 0; t < NT; t++) rivalMode[t] = 0;
        syncRivalBtns(); rebuildEff();
      } else if (p === "min") {
        target = Math.min(TOTAL_PTS, D.rosNeeded);
      } else {
        target = Math.round(TOTAL_PTS * parseFloat(p));    // a points-percentage pace
      }
      recompute({});
    });
  });

  /* ---------------------------------------------------------------- share ---- */
  var shareBtn = el("shareBtn");
  if (shareBtn) {
    var shareHTML = shareBtn.innerHTML;
    var flash = function (text) {
      shareBtn.textContent = text; shareBtn.disabled = true;
      setTimeout(function () { shareBtn.innerHTML = shareHTML; shareBtn.disabled = false; }, 1700);
    };
    shareBtn.addEventListener("click", function () {
      var url = location.href, pct = (lastOdds * 100).toFixed(1);
      var text = location.hash.length > 1
        ? D.shareName + " " + pct + "% to make the playoffs in this scenario (" +
          (baseline * 100).toFixed(1) + "% as things stand)"
        : D.shareName + " " + pct + "% to make the playoffs";
      if (navigator.share) {
        navigator.share({ title: D.shareTitle, text: text, url: url })
          .then(function () { flash("Shared ✓"); }, function () {});
        return;
      }
      var copy = text + " — " + url;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(copy).then(function () { flash("Copied ✓"); },
          function () { window.prompt("Copy this:", copy); });
      } else {
        window.prompt("Copy this:", copy);
      }
    });
  }

  if (readHash()) { syncRivalBtns(); rebuildEff(); }
  recompute({});
})();
