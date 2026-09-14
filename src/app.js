/* Blue Jays playoff tracker — in-browser Monte Carlo.
   Same model as the Python build: log5 matchup probability + home-field advantage,
   full AL field, 3 division winners + 3 wild cards, random tiebreak.
   Locking a series forces those game results (for BOTH clubs) and re-simulates the rest,
   so a scenario's odds are exact rather than read off a baseline curve.

   Three controls drive the SAME scenario, and stay in sync:
     - the hero slider sets a rest-of-season win total, distributed across the series
     - the road-map buttons set an individual series, which moves the slider to match
     - the scoreboard hot/cold toggles bias a rival's remaining games
   The whole scenario round-trips through the URL hash, so it can be shared. */

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
        say("Checking MLB for new results…", "");
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

  var NT = D.teams.length, NG = D.gH.length, J = D.jaysIdx, NS = D.series.length;
  var gH = D.gH, gA = D.gA, gP = D.gP, gJ = D.gJ;
  var NSIM_FULL = 14000, NSIM_DRAG = 4000;    // fewer sims while a drag is in flight
  var TOTAL_GAMES = 0;
  for (var q = 0; q < NS; q++) TOTAL_GAMES += D.series[q].n;

  // scratch buffers reused across every simulation
  var wins = new Int32Array(NT), score = new Float64Array(NT), isDW = new Uint8Array(NT);
  /* Seeding scratch. MLB's format: the three division winners take seeds 1-3 by record,
     the three wild cards 4-6 — a 100-win wild card still seeds behind an 85-win division
     winner. Seeds 1 and 2 sit out the Wild Card round; 3 hosts 6 and 4 hosts 5. */
  var seat = new Int32Array(6), dwList = new Int32Array(3);
  var seedCt = new Float64Array(7), oppCt = new Float64Array(NT + 1);
  var slotCt = new Float64Array(6 * NT);
  var WC_OPP_ROW = [-1, -1, 5, 4, 3, 2];       // seed index -> opponent's seed index
  var teamIn = new Float64Array(NT), locked = new Int8Array(D.nJaysGames);
  var pick = new Int8Array(8);

  /* Rival hot/cold: a per-team shift in logit space, applied to every remaining game
     that team plays. The magnitude is calibrated so the forced finish lands near the
     25th/75th-percentile win totals the dependency bars describe, not some arbitrary
     collapse: over G games the quartile sits ~0.674·√G/2 wins from the mean, and a
     logit shift of s moves a near-coin-flip game by ~s/4, so s = 1.348/√G moves the
     mean by exactly that. The shifted probabilities are rebuilt once per recompute,
     not once per game per season, so 14,000 seasons stay as fast as before. */
  var rivalMode = new Int8Array(NT);            // -1 cold, 0 model, +1 hot
  var teamG = new Int32Array(NT);               // remaining games per team
  for (var _g = 0; _g < NG; _g++) {
    if (gH[_g] >= 0) teamG[gH[_g]]++;
    if (gA[_g] >= 0) teamG[gA[_g]]++;
  }
  function biasFor(t) { return 1.348 / Math.sqrt(Math.max(4, teamG[t])); }

  var gPeff = Float64Array.from(gP);

  function rebuildEff() {
    for (var g = 0; g < NG; g++) {
      var p = gP[g];
      var sh = (gH[g] >= 0 ? rivalMode[gH[g]] * biasFor(gH[g]) : 0)
             - (gA[g] >= 0 ? rivalMode[gA[g]] * biasFor(gA[g]) : 0);
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

  function simulate(scen, nsim, seed) {
    var rand = mulberry32(seed >>> 0);
    var lockedSeries = [], s, i, g, t;
    for (s = 0; s < NS; s++) if (scen[s] !== null) lockedSeries.push(s);

    var inCount = 0, jaysWinSum = 0, cutSum = 0;
    for (t = 0; t < NT; t++) teamIn[t] = 0;
    seedCt.fill(0); oppCt.fill(0); slotCt.fill(0);

    for (var it = 0; it < nsim; it++) {
      for (i = 0; i < locked.length; i++) locked[i] = -1;
      for (var li = 0; li < lockedSeries.length; li++) {
        var ser = D.series[lockedSeries[li]], k = scen[lockedSeries[li]], n = ser.n;
        for (i = 0; i < n; i++) pick[i] = i < k ? 1 : 0;
        for (i = n - 1; i > 0; i--) {           // Fisher-Yates: which games are won
          var j = (rand() * (i + 1)) | 0, tmp = pick[i]; pick[i] = pick[j]; pick[j] = tmp;
        }
        for (i = 0; i < n; i++) locked[ser.slots[i]] = pick[i];
      }

      for (t = 0; t < NT; t++) wins[t] = D.baseW[t];

      for (g = 0; g < NG; g++) {
        var h = gH[g], a = gA[g], slot = gJ[g], homeWin;
        if (slot >= 0 && locked[slot] >= 0) {
          var jaysWon = locked[slot] === 1;
          homeWin = (h === J) ? jaysWon : !jaysWon;
        } else {
          homeWin = rand() < gPeff[g];
        }
        if (homeWin) { if (h >= 0) wins[h]++; } else { if (a >= 0) wins[a]++; }
      }

      for (t = 0; t < NT; t++) { score[t] = wins[t] + rand() * 0.5; isDW[t] = 0; }
      for (var d = 0; d < D.divs.length; d++) {
        var dv = D.divs[d], best = dv[0];
        for (i = 1; i < dv.length; i++) if (score[dv[i]] > score[best]) best = dv[i];
        isDW[best] = 1;
      }
      var w1 = -1, w2 = -1, w3 = -1;
      for (t = 0; t < NT; t++) {
        if (isDW[t]) continue;
        if (w1 < 0 || score[t] > score[w1]) { w3 = w2; w2 = w1; w1 = t; }
        else if (w2 < 0 || score[t] > score[w2]) { w3 = w2; w2 = t; }
        else if (w3 < 0 || score[t] > score[w3]) { w3 = t; }
      }
      for (t = 0; t < NT; t++) if (isDW[t] || t === w1 || t === w2 || t === w3) teamIn[t]++;
      if (w3 >= 0) cutSum += wins[w3];
      var jaysIn = isDW[J] || J === w1 || J === w2 || J === w3;
      if (jaysIn) inCount++;
      jaysWinSum += wins[J];

      /* Seed the field, but only when Toronto is in it — the bracket is conditional on
         qualifying and there is nothing to show in the seasons where they miss. */
      if (jaysIn) {
        var nd = 0;
        for (t = 0; t < NT && nd < 3; t++) if (isDW[t]) dwList[nd++] = t;
        // three elements: an insertion sort by score, descending
        for (i = 1; i < 3; i++) {
          var key = dwList[i], jj = i - 1;
          while (jj >= 0 && score[dwList[jj]] < score[key]) { dwList[jj + 1] = dwList[jj]; jj--; }
          dwList[jj + 1] = key;
        }
        seat[0] = dwList[0]; seat[1] = dwList[1]; seat[2] = dwList[2];
        seat[3] = w1; seat[4] = w2; seat[5] = w3;     // already ordered by score
        var js = 0;
        for (i = 0; i < 6; i++) {
          slotCt[i * NT + seat[i]]++;
          if (seat[i] === J) js = i;
        }
        seedCt[js + 1]++;
        var orow = WC_OPP_ROW[js];
        oppCt[orow < 0 ? NT : seat[orow]]++;          // index NT means a bye
      }
    }

    var odds = new Float64Array(NT);
    for (t = 0; t < NT; t++) odds[t] = teamIn[t] / nsim;
    return { odds: inCount / nsim, teamOdds: odds, meanWins: jaysWinSum / nsim,
             cut: cutSum / nsim, nsim: nsim,
             bracket: inCount ? readBracket(inCount) : null };
  }

  /* Turn the seeding tallies into the shape the bracket renders from. Everything is a
     share of the seasons Toronto QUALIFIED in, not of all seasons. */
  function readBracket(nIn) {
    var k, t, best = 1;
    var seed = new Array(7).fill(0);
    for (k = 1; k <= 6; k++) {
      seed[k] = seedCt[k] / nIn;
      if (seedCt[k] > seedCt[best]) best = k;
    }
    var opp = [], oi;
    for (oi = 0; oi <= NT; oi++) {
      if (oppCt[oi]) opp.push({ team: oi === NT ? null : oi, p: oppCt[oi] / nIn });
    }
    opp.sort(function (a, b) { return b.p - a.p; });

    // Toronto is pinned to its likeliest seed; every other slot shows the likeliest club
    // that is NOT Toronto, so the six slots read as one coherent bracket.
    var slots = {};
    for (k = 1; k <= 6; k++) {
      var rows = [];
      for (t = 0; t < NT; t++) {
        var c = slotCt[(k - 1) * NT + t];
        if (c) rows.push({ team: t, p: c / nIn });
      }
      rows.sort(function (a, b) { return b.p - a.p; });
      if (k === best) {
        var mine = rows.filter(function (r) { return r.team === J; });
        rows = (mine.length ? mine : [{ team: J, p: 0 }])
          .concat(rows.filter(function (r) { return r.team !== J; }));
      } else {
        rows = rows.filter(function (r) { return r.team !== J; });
      }
      slots[k] = rows;
    }
    var bye = seed[1] + seed[2];
    return { seed: seed, bestSeed: best, opponent: opp, slots: slots,
             pBye: bye, pHost: seed[3] + seed[4] };
  }

  /* ---------------------------------------------------------------- state ---- */
  var scen = new Array(NS).fill(null);      // null = let the model simulate it
  var baseline = D.baselineOdds;
  var el = function (id) { return document.getElementById(id); };
  var lastOdds = baseline, tween = null, dragging = false;

  /* Spread `total` wins across the 13 series: repeatedly hand the next win to
     whichever series is furthest below the share it takes in qualifying seasons. */
  function allocate(total) {
    var out = new Array(NS).fill(0), given = 0;
    while (given < total) {
      var best = -1, bestScore = -1e9;
      for (var i = 0; i < NS; i++) {
        if (out[i] >= D.series[i].n) continue;
        var sc = D.series[i].need - out[i];
        if (sc > bestScore) { bestScore = sc; best = i; }
      }
      if (best < 0) break;
      out[best]++; given++;
    }
    return out;
  }

  function lockedTotal() {
    var w = 0, any = false;
    for (var s = 0; s < NS; s++) if (scen[s] !== null) { w += scen[s]; any = true; }
    return any ? w : null;
  }

  function syncRows() {
    for (var s = 0; s < NS; s++) {
      var row = document.querySelector('[data-series="' + s + '"]');
      if (!row) continue;
      row.classList.toggle("locked", scen[s] !== null);
      var btns = row.querySelectorAll("[data-w]");
      for (var b = 0; b < btns.length; b++) {
        var on = scen[s] !== null && +btns[b].dataset.w === scen[s];
        btns[b].classList.toggle("on", on);
        btns[b].setAttribute("aria-pressed", on ? "true" : "false");
      }
    }
  }

  function animateOdds(from, to, instant) {
    if (tween) cancelAnimationFrame(tween);
    var node = el("liveOdds"), bar = el("liveBar");
    if (instant) {
      node.textContent = (to * 100).toFixed(1);
      if (bar) bar.style.width = Math.min(100, to * 100 * 3.2) + "%";
      return;
    }
    var t0 = performance.now(), dur = 400;
    (function step(now) {
      var p = Math.min(1, (now - t0) / dur);
      var e = 1 - Math.pow(1 - p, 3);
      var v = from + (to - from) * e;
      node.textContent = (v * 100).toFixed(1);
      if (bar) bar.style.width = Math.min(100, v * 100 * 3.2) + "%";
      if (p < 1) tween = requestAnimationFrame(step);
    })(t0);
  }

  var pending = null;
  function recompute(opts) {
    opts = opts || {};
    if (pending) cancelAnimationFrame(pending);
    pending = requestAnimationFrame(function () {   // paint the click first
      pending = null;
      recomputeNow(opts);
    });
  }

  function recomputeNow(opts) {
    var t0 = performance.now();
    var r = simulate(scen, opts.fast ? NSIM_DRAG : NSIM_FULL, 12345);
    var ms = performance.now() - t0;

    animateOdds(lastOdds, r.odds, !!opts.fast);
    lastOdds = r.odds;

    var nLocked = 0, lw = 0, lg = 0, lseries = 0;
    for (var s = 0; s < NS; s++) {
      if (scen[s] === null) continue;
      nLocked++; lw += scen[s]; lg += D.series[s].n;
      if (scen[s] > D.series[s].n / 2) lseries++;
    }

    var anySet = nLocked > 0 || anyBias();
    var dEl = el("liveDelta"), diff = r.odds - baseline;
    if (!anySet) {
      dEl.textContent = "model baseline — nothing set yet";
      dEl.className = "livedelta";
    } else {
      dEl.textContent = (diff >= 0 ? "+" : "−") + Math.abs(diff * 100).toFixed(1)
        + " pts vs baseline (" + (baseline * 100).toFixed(1) + "%)";
      dEl.className = "livedelta " + (diff >= 0.001 ? "up" : diff <= -0.001 ? "down" : "");
    }

    el("liveRec").textContent = nLocked ? (lseries + " of " + NS) : "—";
    el("liveRecSub").textContent = nLocked
      ? (nLocked === NS ? "series won · needs " + D.seriesNeeded
                        : "series won so far · " + nLocked + "/" + NS + " set")
      : "drag the slider, or tap a series below";
    el("liveProj").textContent = r.meanWins.toFixed(1);
    el("liveCut").textContent = r.cut.toFixed(1);

    for (var t = 0; t < NT; t++) {
      var f = document.querySelector('[data-oddsbar="' + t + '"]');
      var n2 = document.querySelector('[data-oddsnum="' + t + '"]');
      if (f) f.style.width = (r.teamOdds[t] * 100).toFixed(0) + "%";
      if (n2) n2.textContent = (r.teamOdds[t] * 100).toFixed(0) + "%";
    }

    var mk = el("scenMark"), lab = el("scenMarkLab");
    if (mk && !anySet) {
      mk.style.opacity = 0; lab.style.opacity = 0;
    } else if (mk) {
      var x = D.curveX0 + (r.meanWins - D.curveW0) / (D.curveW1 - D.curveW0) * (D.curveX1 - D.curveX0);
      x = Math.max(D.curveX0, Math.min(D.curveX1, x));
      mk.setAttribute("x1", x); mk.setAttribute("x2", x);
      mk.style.opacity = 1;
      lab.setAttribute("x", x);
      lab.setAttribute("text-anchor", x > (D.curveX0 + D.curveX1) / 2 ? "end" : "start");
      lab.setAttribute("dx", x > (D.curveX0 + D.curveX1) / 2 ? -5 : 5);
      lab.textContent = "YOUR SCENARIO " + r.meanWins.toFixed(1) + "W";
      lab.style.opacity = 1;
    }

    // keep the slider in step when the change came from somewhere else
    var sl = el("winSlider");
    if (sl && !dragging && !opts.fromSlider) {
      var lt = lockedTotal();
      sl.value = lt === null ? Math.round(r.meanWins - D.baseW[J]) : lt;
      paintSlider();
    }

    if (!opts.fast) paintBracket(r.bracket);

    var perf = el("perfNote");
    if (perf) perf.textContent = r.nsim.toLocaleString() + " seasons · " + ms.toFixed(0) + " ms";

    if (!opts.fast) writeHash();
  }

  /* ---------------------------------------------------------------- bracket ----
     Re-drawn on every recompute, so locking a series or forcing a rival cold changes who
     Toronto would meet in October, not just whether they get there. */
  function ordinal(n) {
    var s = ["th", "st", "nd", "rd"], v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  }

  function paintBracket(bk) {
    var head = el("bkHead");
    if (!head) return;
    var seats = document.querySelectorAll("[data-slot]");
    if (!bk) {                       // eliminated in every simulated season
      head.textContent = "No qualifying seasons left to draw a bracket from.";
      for (var z = 0; z < seats.length; z++) {
        seats[z].classList.remove("you");
        seats[z].querySelector("[data-bk-team]").textContent = "—";
        seats[z].querySelector("[data-bk-p]").textContent = "";
      }
      return;
    }
    for (var i = 0; i < seats.length; i++) {
      var k = +seats[i].dataset.slot, rows = bk.slots[k] || [];
      var top = rows[0];
      seats[i].classList.toggle("you", !!top && top.team === J);
      seats[i].querySelector("[data-bk-team]").textContent =
        top ? D.abbr[top.team] : "—";
      seats[i].querySelector("[data-bk-p]").textContent =
        top ? Math.round(top.p * 100) + "%" : "";
    }
    var best = bk.bestSeed, opp = bk.opponent[0];
    if (opp && opp.team === null) {
      head.innerHTML = "Most likely the <b>" + ordinal(best) +
        " seed</b> — <b>a bye</b> straight to the Division Series";
    } else if (opp) {
      head.innerHTML = "Most likely the <b>" + ordinal(best) + " seed</b>, " +
        (best >= 5 ? "at" : "hosting") + " <b>the " + D.teams[opp.team] +
        "</b> in the Wild Card round";
    } else {
      head.textContent = "Seeding is still wide open";
    }
  }

  /* ------------------------------------------------------------ share the scenario ----
     The whole scenario lives in the URL hash — series results as a dotted list (x =
     left to the model), rival biases as teamIndex+h/c — so a fan can send "here's the
     path" as a link. replaceState, not assignment, so dragging never scrolls the page
     or pollutes history. */
  var lastHash = null;
  function writeHash() {
    var parts = [], ss = [], anyS = false, s, t;
    for (s = 0; s < NS; s++) {
      ss.push(scen[s] === null ? "x" : scen[s]);
      if (scen[s] !== null) anyS = true;
    }
    if (anyS) parts.push("s=" + ss.join("."));
    var bs = [];
    for (t = 0; t < NT; t++) if (rivalMode[t]) bs.push(t + (rivalMode[t] > 0 ? "h" : "c"));
    if (bs.length) parts.push("r=" + bs.join("."));
    var h = parts.join("&");
    if (h === lastHash) return;
    lastHash = h;
    if (history.replaceState) {
      history.replaceState(null, "", h ? "#" + h
                                       : location.pathname + location.search);
    }
  }

  function readHash() {
    var h = location.hash.slice(1);
    if (!h) return false;
    var got = false;
    h.split("&").forEach(function (kv) {
      var i = kv.indexOf("=");
      if (i < 0) return;
      var k = kv.slice(0, i), v = kv.slice(i + 1);
      if (k === "s") {
        var ps = v.split(".");
        for (var s = 0; s < NS && s < ps.length; s++) {
          if (ps[s] === "x") continue;
          var w = parseInt(ps[s], 10);
          if (w >= 0 && w <= D.series[s].n) { scen[s] = w; got = true; }
        }
      } else if (k === "r") {
        v.split(".").forEach(function (tok) {
          var m = /^(\d+)([hc])$/.exec(tok);
          if (m && +m[1] < NT && +m[1] !== J) {
            rivalMode[+m[1]] = m[2] === "h" ? 1 : -1;
            got = true;
          }
        });
      }
    });
    return got;
  }

  /* ---------------------------------------------------------------- slider ---- */
  var sl = el("winSlider");

  function paintSlider() {
    if (!sl) return;
    var w = +sl.value, pctv = (w / TOTAL_GAMES) * 100;
    sl.style.setProperty("--fill", pctv + "%");
    var lab = el("sliderVal");
    if (lab) lab.textContent = w + "–" + (TOTAL_GAMES - w);
    var pace = el("sliderPace");
    if (pace) {
      var wp = w / TOTAL_GAMES;
      pace.textContent = "." + Math.round(wp * 1000) + " pace over the last "
        + TOTAL_GAMES + " games";
    }
  }

  if (sl) {
    sl.max = TOTAL_GAMES;
    sl.value = Math.round(D.projWins - D.baseW[J]);
    paintSlider();

    var applyFromSlider = function (fast) {
      var target = +sl.value;
      var alloc = allocate(target);
      for (var s = 0; s < NS; s++) scen[s] = alloc[s];
      syncRows();
      paintSlider();
      recompute({ fast: fast, fromSlider: true });
    };
    sl.addEventListener("pointerdown", function () { dragging = true; });
    sl.addEventListener("input", function () { applyFromSlider(true); });
    sl.addEventListener("change", function () { dragging = false; applyFromSlider(false); });
    sl.addEventListener("pointerup", function () { dragging = false; });
    sl.addEventListener("keyup", function () { dragging = false; applyFromSlider(false); });
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
      rivalMode[t] = (rivalMode[t] === m) ? 0 : m;         // click again to release
      syncRivalBtns();
      rebuildEff();
      recompute({});
    });
  });

  /* ---------------------------------------------------------------- share ---- */
  /* One control, not two. It shares the scenario when one is set and the page otherwise,
     and it leads with the NUMBER rather than a bare link — Slack and SMS often do not
     render the preview card, and a naked URL is not a reason to tap. Uses the native
     share sheet where there is one, which on a phone is the difference between one tap to
     iMessage and a string somebody has to paste. */
  var shareBtn = el("shareBtn");
  if (shareBtn) {
    var shareHTML = shareBtn.innerHTML;
    var flash = function (text) {
      shareBtn.textContent = text;
      shareBtn.disabled = true;
      setTimeout(function () {
        shareBtn.innerHTML = shareHTML;
        shareBtn.disabled = false;
      }, 1700);
    };
    shareBtn.addEventListener("click", function () {
      var url = location.href;
      var pct = (lastOdds * 100).toFixed(1);
      var scen = location.hash.length > 1;
      var text = scen
        ? "Blue Jays " + pct + "% to make the playoffs in this scenario ("
          + (baseline * 100).toFixed(1) + "% as things stand)"
        : "Blue Jays " + pct + "% to make the playoffs";
      if (navigator.share) {
        navigator.share({ title: "Blue Jays Playoff Tracker", text: text, url: url })
          .then(function () { flash("Shared ✓"); },
                function () { /* the sheet was dismissed: say nothing */ });
        return;
      }
      var copy = text + " — " + url;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(copy).then(
          function () { flash("Copied ✓"); },
          function () { window.prompt("Copy this:", copy); });
      } else {
        window.prompt("Copy this:", copy);
      }
    });
  }

  /* ---------------------------------------------------------------- buttons ---- */
  document.querySelectorAll("[data-w]").forEach(function (b) {
    b.addEventListener("click", function () {
      var s = +b.closest("[data-series]").dataset.series, v = +b.dataset.w;
      scen[s] = (scen[s] === v) ? null : v;      // click again to release
      syncRows();
      recompute({});
    });
  });

  document.querySelectorAll("[data-preset]").forEach(function (b) {
    b.addEventListener("click", function () {
      var p = b.dataset.preset, s, alloc;
      if (p === "reset") {
        for (s = 0; s < NS; s++) scen[s] = null;
        for (var t = 0; t < NT; t++) rivalMode[t] = 0;
        syncRivalBtns();
        rebuildEff();
        if (sl) { sl.value = Math.round(D.projWins - D.baseW[J]); paintSlider(); }
      } else if (p === "min") {
        alloc = allocate(D.rosNeededW);
        for (s = 0; s < NS; s++) scen[s] = alloc[s];
      } else if (p === "twoone") {
        // "2-1 every series", generalised to series that aren't 3 games:
        // win two thirds of each, so a 2-game set is a sweep and a 4-game set is 3-1
        for (s = 0; s < NS; s++) scen[s] = Math.max(1, Math.ceil(D.series[s].n * 2 / 3));
      } else if (p === "sweep") {
        for (s = 0; s < NS; s++) scen[s] = D.series[s].n;
      } else if (p === "cold") {
        // the slump mirrors it: one third of each series, floor of one loss
        for (s = 0; s < NS; s++) scen[s] = Math.min(D.series[s].n - 1,
                                                    Math.floor(D.series[s].n / 3));
      }
      syncRows();
      recompute({});
    });
  });

  // restore a shared scenario from the URL before the first simulation runs
  if (readHash()) {
    syncRows();
    syncRivalBtns();
    rebuildEff();
  }
  recompute({});
})();
