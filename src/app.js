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
      if (isDW[J] || J === w1 || J === w2 || J === w3) inCount++;
      jaysWinSum += wins[J];
    }

    var odds = new Float64Array(NT);
    for (t = 0; t < NT; t++) odds[t] = teamIn[t] / nsim;
    return { odds: inCount / nsim, teamOdds: odds, meanWins: jaysWinSum / nsim,
             cut: cutSum / nsim, nsim: nsim };
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

    var perf = el("perfNote");
    if (perf) perf.textContent = r.nsim.toLocaleString() + " seasons · " + ms.toFixed(0) + " ms";

    if (!opts.fast) writeHash();
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
    var sb = el("shareBtn");
    if (sb) sb.hidden = !h;
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
  var shareBtn = el("shareBtn");
  if (shareBtn) {
    shareBtn.addEventListener("click", function () {
      var url = location.href;
      var done = function () {
        shareBtn.textContent = "Link copied ✓";
        shareBtn.disabled = true;
        setTimeout(function () {
          shareBtn.textContent = "Copy link to this scenario";
          shareBtn.disabled = false;
        }, 1600);
      };
      var fallback = function () { window.prompt("Copy this link:", url); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, fallback);
      } else {
        fallback();
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
