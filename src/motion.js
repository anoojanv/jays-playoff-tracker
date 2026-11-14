/* Motion graphics for the Leafs tracker — the simulation, animated.

   Three pieces, each reading window.__VIZ__ (written by build_html.py from the same
   simulated seasons as every other number on the page):

     1. The season machine. Each dot is a batch of simulated seasons, poured into a
        histogram of the Leafs' final points. The counter is the share of landed dots
        that make the playoffs, so the estimate visibly settles as seasons accumulate,
        which is the whole idea of a Monte Carlo. "If they win / lose tonight" re-flows
        every dot to where those seasons end up.
     2. The forecast cone, borrowed from hurricane forecasting: the season so far as a
        solid line, then real simulated paths fanning out, then the bands that summarise
        them. Scrub to read any game.
     3. A reveal system: sections, bars and numbers animate as they scroll into view.

   Rules it keeps: nothing is hidden unless this script is running (a failure leaves a
   complete static page), prefers-reduced-motion gets the final state with no movement,
   no network and no storage (build.py's verifier enforces both), and every animation
   runs on requestAnimationFrame so it costs nothing off-screen. */
(function () {
  "use strict";
  var V = window.__VIZ__;
  if (!V) return;
  var RM = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var C = V.colors;
  var IO = "IntersectionObserver" in window;

  function onView(el, fn, margin) {
    if (!el) return;
    if (!IO) { fn(); return; }
    var io = new IntersectionObserver(function (es) {
      for (var i = 0; i < es.length; i++) if (es[i].isIntersecting) { io.disconnect(); fn(); return; }
    }, { rootMargin: margin || "0px 0px -12% 0px" });
    io.observe(el);
  }
  var easeOut = function (t) { return 1 - Math.pow(1 - t, 3); };
  var easeInOut = function (t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
  function mulberry(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function pct(v, d) { return (v * 100).toFixed(d === undefined ? 1 : d); }

  /* ================================================================ 1. machine ==== */
  (function machine() {
    var M = V.machine, cv = document.getElementById("machine");
    if (!M || !cv || !cv.getContext) return;
    var box = cv.parentNode, ctx = cv.getContext("2d");
    var oddsEl = document.getElementById("mxOdds"), capEl = document.getElementById("mxCap");
    var kEl = document.getElementById("mxK"), btns = document.querySelectorAll("[data-mx]");
    var NB = M.hi - M.lo + 1;
    var W, H, dpr, pad = { l: 10, r: 10, t: 18, b: 30 }, pitch, rad, perRow, binW;
    var K, N, dots = [], state = "model", raf = 0, landed = 0, landedIn = 0, dropping = false;

    function layoutScale() {
      W = box.clientWidth; H = Math.max(250, Math.min(380, Math.round(W * 0.4)));
      dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      cv.style.width = W + "px"; cv.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      binW = (W - pad.l - pad.r) / NB;
      pitch = W < 520 ? 4.6 : 5.6;
      rad = pitch * 0.42;
      perRow = Math.max(1, Math.floor((binW - 0.5) / pitch));
      // seasons per dot: the tallest column in any state must fit, rounded to a nice number
      var rows = Math.floor((H - pad.t - pad.b - 14) / pitch), cap = rows * perRow, tall = 0;
      for (var s in M.states) {
        var st = M.states[s], f = M.nsim / Math.max(1, st.n);
        for (var b = 0; b < NB; b++) tall = Math.max(tall, (st["in"][b] + st.out[b]) * f);
      }
      var raw = tall / cap, nice = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 16, 20, 25, 30, 40, 50, 60, 80, 100, 125, 150, 200, 250, 500, 1000];
      K = nice[nice.length - 1];
      for (var i = 0; i < nice.length; i++) if (nice[i] >= raw) { K = nice[i]; break; }
      N = Math.round(M.nsim / K);
      if (kEl) kEl.textContent = K.toLocaleString();
    }
    function X(pts) { return pad.l + (pts - M.lo + 0.5) * binW; }

    /* the target layout for a state: N dots, apportioned across (bin, in/out) cells by
       largest remainder so the total is exact, stacked bottom-up, playoff seasons first */
    function targets(name) {
      var st = M.states[name], f = N / Math.max(1, st.n), cells = [], tot = 0, b;
      for (b = 0; b < NB; b++) {
        cells.push({ b: b, inn: 1, v: st["in"][b] * f });
        cells.push({ b: b, inn: 0, v: st.out[b] * f });
      }
      cells.forEach(function (c) { c.n = Math.floor(c.v); c.r = c.v - c.n; tot += c.n; });
      cells.slice().sort(function (a, z) { return z.r - a.r; })
        .slice(0, Math.max(0, N - tot)).forEach(function (c) { c.n++; });
      var out = [], used = new Array(NB).fill(0), base = H - pad.b;
      for (var pass = 1; pass >= 0; pass--) {
        for (b = 0; b < NB; b++) {
          var c = cells[2 * b + (1 - pass)];
          for (var j = 0; j < c.n; j++) {
            var k = used[b]++, row = Math.floor(k / perRow), col = k % perRow;
            var x0 = pad.l + b * binW + (binW - perRow * pitch) / 2 + pitch / 2;
            out.push({ x: x0 + col * pitch, y: base - row * pitch - pitch / 2, inn: pass });
          }
        }
      }
      return out;
    }

    function frame() {
      ctx.clearRect(0, 0, W, H);
      var base = H - pad.b, cut = M.cut;
      // the cut line: where the second wild card finishes, 80% of the time and median
      ctx.fillStyle = "rgba(" + C.navyRgb + ",.06)";
      ctx.fillRect(X(cut.p10) - binW / 2, pad.t - 6, X(cut.p90) - X(cut.p10) + binW, base - pad.t + 6);
      ctx.strokeStyle = C.brand; ctx.lineWidth = 1.25; ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(X(cut.p50), pad.t - 6); ctx.lineTo(X(cut.p50), base); ctx.stroke();
      ctx.setLineDash([]);
      // axis
      ctx.strokeStyle = C.axis; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(pad.l, base + .5); ctx.lineTo(W - pad.r, base + .5); ctx.stroke();
      ctx.fillStyle = C.mute; ctx.font = "600 9.5px system-ui,-apple-system,Segoe UI,sans-serif";
      ctx.textAlign = "center";
      var step = binW * 5 < 26 ? 10 : 5;
      for (var p = Math.ceil(M.lo / step) * step; p <= M.hi; p += step) {
        ctx.fillRect(X(p) - .5, base, 1, 4);
        ctx.fillText(p, X(p), base + 15);
      }
      ctx.fillText("final points", W / 2, base + 27);
      // dots, batched by colour: one path per colour keeps 2,000 dots cheap
      var groups = [[], []];
      for (var i = 0; i < dots.length; i++) if (dots[i].vis) groups[dots[i].inn].push(dots[i]);
      [[0, C.out], [1, C.brand]].forEach(function (g) {
        ctx.fillStyle = g[1]; ctx.beginPath();
        var arr = groups[g[0]];
        for (var j = 0; j < arr.length; j++) {
          ctx.moveTo(arr[j].cx + rad, arr[j].cy);
          ctx.arc(arr[j].cx, arr[j].cy, rad, 0, 6.2832);
        }
        ctx.fill();
      });
      // the label last, with a halo, so falling dots never paint over it. A cut line off
      // the axis (a clinched or buried season) is pointed at from the edge, not dropped
      ctx.font = "700 10px system-ui,-apple-system,Segoe UI,sans-serif";
      var cxp = X(cut.p50), off = cxp < pad.l ? -1 : cxp > W - pad.r ? 1 : 0;
      var lab = "cut line ~" + Math.round(cut.p50) + " pts", lx;
      if (off < 0) { ctx.textAlign = "left"; lx = pad.l; lab = "\u2190 " + lab + " \u2014 below every season here"; }
      else if (off > 0) { ctx.textAlign = "right"; lx = W - pad.r; lab = lab + " \u2014 above every season here \u2192"; }
      else { ctx.textAlign = cxp > W - 120 ? "right" : "left"; lx = cxp + (ctx.textAlign === "left" ? 6 : -6); }
      ctx.lineWidth = 4; ctx.strokeStyle = "rgba(255,255,255,.92)"; ctx.lineJoin = "round";
      ctx.strokeText(lab, lx, pad.t + 2);
      ctx.fillStyle = C.brand; ctx.fillText(lab, lx, pad.t + 2);
    }

    function setCounter(v, settled) {
      if (oddsEl) oddsEl.textContent = pct(v);
      if (capEl) capEl.textContent = settled
        ? capFor(state)
        : "of " + landed.toLocaleString() + " dots landed so far make the playoffs";
    }
    function capFor(name) {
      if (name === "win") return "chance of a playoff spot if " + V.winCap + " next";
      if (name === "loss") return "chance of a playoff spot if " + V.lossCap + " next";
      return "chance of a playoff spot — " + M.nsim.toLocaleString() + " seasons, " + N.toLocaleString() + " dots";
    }

    /* pour: dots leave a hopper at the top centre in random order and arc onto their
       stacks, so the histogram builds from the bottom up the way the seasons do */
    function drop(seed) {
      cancelAnimationFrame(raf);
      var tg = targets(state), rnd = mulberry(seed || 7), order = [];
      dots = tg.map(function (t, i) {
        order.push(i);
        return { tx: t.x, ty: t.y, inn: t.inn, cx: t.x, cy: t.y, vis: true };
      });
      if (RM) { landed = N; frame(); setCounter(M.states[state].odds, true); return; }
      for (var i = order.length - 1; i > 0; i--) {
        var j = Math.floor(rnd() * (i + 1)), tmp = order[i]; order[i] = order[j]; order[j] = tmp;
      }
      var POUR = 2300, FALL = 650, t0 = performance.now(), hx = W / 2;
      order.forEach(function (idx, k) {
        var d = dots[idx];
        d.t0 = (k / order.length) * POUR; d.sx = hx + (rnd() - .5) * 26; d.vis = false; d.done = false;
      });
      landed = 0; landedIn = 0; dropping = true;
      (function tick(now) {
        var el = now - t0, live = false;
        for (var i = 0; i < dots.length; i++) {
          var d = dots[i];
          if (d.done) continue;
          var u = (el - d.t0) / FALL;
          if (u < 0) { live = true; continue; }
          d.vis = true;
          if (u >= 1) {
            d.cx = d.tx; d.cy = d.ty; d.done = true; landed++; if (d.inn) landedIn++;
            continue;
          }
          live = true;
          d.cx = d.sx + (d.tx - d.sx) * easeOut(u);
          d.cy = -6 + (d.ty + 6) * (u * u);
        }
        frame();
        if (live) { setCounter(landed ? landedIn / landed : 0, false); raf = requestAnimationFrame(tick); }
        else { dropping = false; setCounter(M.states[state].odds, true); }
      })(t0);
    }

    /* re-flow: pair the dots with the new layout in reading order and glide them there,
       left to right, recolouring as they go — the same seasons, sorted differently */
    function morph(name) {
      var from = M.states[state].odds, to = M.states[name].odds;
      state = name;
      for (var b = 0; b < btns.length; b++)
        btns[b].setAttribute("aria-pressed", btns[b].dataset.mx === name ? "true" : "false");
      var tg = targets(name);
      if (RM || dropping || !dots.length) {
        cancelAnimationFrame(raf); dropping = false;
        dots = tg.map(function (t) { return { tx: t.x, ty: t.y, inn: t.inn, cx: t.x, cy: t.y, vis: true }; });
        landed = N; frame(); setCounter(to, true); return;
      }
      var key = function (a, z) { return a.cx - z.cx || z.cy - a.cy; };
      dots.sort(key);
      tg.sort(function (a, z) { return a.x - z.x || z.y - a.y; });
      var DUR = 900, STAG = 320, t0 = performance.now();
      dots.forEach(function (d, i) {
        d.fx = d.cx; d.fy = d.cy; d.tx = tg[i].x; d.ty = tg[i].y; d.ninn = tg[i].inn;
        d.delay = (tg[i].x / W) * STAG; d.vis = true;
      });
      cancelAnimationFrame(raf);
      (function tick(now) {
        var el = now - t0, live = false;
        for (var i = 0; i < dots.length; i++) {
          var d = dots[i], u = Math.max(0, Math.min(1, (el - d.delay) / DUR)), e = easeInOut(u);
          d.cx = d.fx + (d.tx - d.fx) * e;
          d.cy = d.fy + (d.ty - d.fy) * e - Math.sin(Math.PI * u) * 18;
          if (u > .5) d.inn = d.ninn;
          if (u < 1) live = true;
        }
        frame();
        var k = Math.min(1, el / (DUR + STAG));
        if (oddsEl) oddsEl.textContent = pct(from + (to - from) * easeInOut(k));
        if (live) raf = requestAnimationFrame(tick);
        else setCounter(to, true);
      })(t0);
    }

    layoutScale();
    dots = targets(state).map(function (t) { return { tx: t.x, ty: t.y, inn: t.inn, cx: t.x, cy: t.y, vis: false }; });
    frame();
    for (var b = 0; b < btns.length; b++) btns[b].addEventListener("click", function (e) {
      var name = e.currentTarget.dataset.mx;
      if (name === "replay") { drop((Math.random() * 1e9) | 0); return; }
      if (name !== state && M.states[name]) morph(name);
    });
    onView(cv, function () { drop(7); });
    var rz = 0, lastW = box.clientWidth;
    window.addEventListener("resize", function () {
      clearTimeout(rz);
      rz = setTimeout(function () {
        if (Math.abs(box.clientWidth - lastW) < 4) return;
        lastW = box.clientWidth; cancelAnimationFrame(raf); dropping = false; layoutScale();
        dots = targets(state).map(function (t) { return { tx: t.x, ty: t.y, inn: t.inn, cx: t.x, cy: t.y, vis: true }; });
        landed = N; frame(); setCounter(M.states[state].odds, true);
      }, 150);
    });
  })();

  /* ================================================================== 2. cone ===== */
  /* drawn at the container's real width, so its text is the size it says on a phone as
     well as a desktop; a resize redraws it at the new width without replaying */
  function cone(still) {
    var D = V.cone, host = document.getElementById("cone");
    if (!D || !host) return;
    host.innerHTML = "";
    var NS = "http://www.w3.org/2000/svg";
    function el(tag, attrs, parent) {
      var e = document.createElementNS(NS, tag);
      for (var k in attrs) e.setAttribute(k, attrs[k]);
      if (parent) parent.appendChild(e);
      return e;
    }
    var W = Math.max(300, Math.round(host.clientWidth || 720));
    var H = W < 560 ? 250 : Math.min(380, Math.round(W * 0.33)), fs = W < 560 ? 9.5 : 11;
    var P = { l: 34, r: W < 560 ? 54 : 64, t: 14, b: 30 };
    var G = D.season_games, g0 = D.start_gp, nF = D.dates.length;
    var top = Math.max(D.q.p95.length ? D.q.p95[nF - 1] : D.start_pts, V.machine.cut.p90) + 6;
    top = Math.ceil(top / 10) * 10;
    var x = function (g) { return P.l + g / G * (W - P.l - P.r); };
    var y = function (v) { return P.t + (1 - v / top) * (H - P.t - P.b); };
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: "100%", role: "img",
      "aria-label": "Forecast cone of the Leafs' points through the season" }, host);

    var grid = el("g", {}, svg);
    for (var v = 0; v <= top; v += 20) {
      el("line", { x1: P.l, x2: W - P.r, y1: y(v), y2: y(v), stroke: C.grid }, grid);
      var tx = el("text", { x: P.l - 7, y: y(v) + 3.5, "text-anchor": "end", "font-size": fs, fill: C.mute }, grid);
      tx.textContent = v;
    }
    for (var gx = 0; gx <= G; gx += 20) {
      var lab = el("text", { x: x(gx), y: H - 10, "text-anchor": "middle", "font-size": fs, fill: C.mute }, grid);
      lab.textContent = gx === 0 ? "game 0" : gx;
    }
    // the cut line, as the forecast sees it at the end of the season
    var cut = V.machine.cut;
    el("rect", { x: x(G) - 4, y: y(cut.p90), width: 8, height: Math.max(2, y(cut.p10) - y(cut.p90)),
      fill: C.brand, opacity: .85, rx: 2 }, svg);
    el("line", { x1: x(g0), x2: x(G), y1: y(cut.p50), y2: y(cut.p50), stroke: C.brand,
      "stroke-dasharray": "3 4", opacity: .55 }, svg);
    var cl = el("text", { x: x(G) + 8, y: y(cut.p50) + 3.5, "font-size": fs + .5, "font-weight": 700, fill: C.brand }, svg);
    cl.textContent = "cut ~" + Math.round(cut.p50);

    var future = el("g", {}, svg);
    function band(lo, hi, op) {
      if (!nF) return null;
      var pts = [x(g0) + "," + y(D.start_pts)];
      for (var i = 0; i < nF; i++) pts.push(x(g0 + i + 1) + "," + y(hi[i]));
      for (var j = nF - 1; j >= 0; j--) pts.push(x(g0 + j + 1) + "," + y(lo[j]));
      return el("polygon", { points: pts.join(" "), fill: C.blue, opacity: op }, future);
    }
    var paths = D.paths.map(function (p) {
      var pts = [x(g0) + "," + y(D.start_pts)];
      for (var i = 0; i < p.pts.length; i++) pts.push(x(g0 + i + 1) + "," + y(p.pts[i]));
      return el("polyline", { points: pts.join(" "), fill: "none",
        stroke: p["in"] ? C.brand : C.out, "stroke-width": 1.1,
        opacity: p["in"] ? .34 : .75, "stroke-linejoin": "round" }, future);
    });
    var b1 = band(D.q.p5, D.q.p95, .14), b2 = band(D.q.p25, D.q.p75, .22);
    var med = null;
    if (nF) {
      var mp = [x(g0) + "," + y(D.start_pts)];
      for (var i2 = 0; i2 < nF; i2++) mp.push(x(g0 + i2 + 1) + "," + y(D.q.p50[i2]));
      med = el("polyline", { points: mp.join(" "), fill: "none", stroke: C.brand, "stroke-width": 2,
        "stroke-dasharray": "5 4" }, future);
    }
    // the season so far
    var actual = null;
    if (D.log.length) {
      var ap = [x(0) + "," + y(0)];
      D.log.forEach(function (g, i) { ap.push(x(i + 1) + "," + y(g.pts)); });
      actual = el("polyline", { points: ap.join(" "), fill: "none", stroke: C.brand, "stroke-width": 2.6,
        "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    }
    el("line", { x1: x(g0), x2: x(g0), y1: P.t, y2: H - P.b, stroke: C.axis, "stroke-dasharray": "2 3" }, svg);
    var tl = el("text", { x: x(g0) + 4, y: P.t + 9, "font-size": fs, "font-weight": 700, fill: C.ink2 }, svg);
    tl.textContent = g0 ? "today" : "opening night";

    // scrubber
    var rule = el("line", { y1: P.t, y2: H - P.b, stroke: C.ink, "stroke-width": 1, opacity: 0 }, svg);
    var dot = el("circle", { r: 4, fill: C.brand, stroke: "#fff", "stroke-width": 2, opacity: 0 }, svg);
    var readout = document.getElementById("coneRead");
    var hit = el("rect", { x: P.l, y: P.t, width: W - P.l - P.r, height: H - P.t - P.b,
      fill: "transparent", style: "cursor:crosshair;touch-action:pan-y" }, svg);
    var fmtD = function (iso) {
      var d = new Date(iso + "T12:00:00Z");
      return d.toLocaleDateString("en-CA", { month: "short", day: "numeric", timeZone: "UTC" });
    };
    function read(evt) {
      var r = svg.getBoundingClientRect(), px = (evt.clientX - r.left) / r.width * W;
      var g = Math.round((px - P.l) / (W - P.l - P.r) * G);
      g = Math.max(1, Math.min(g0 + nF, g));
      var txt, yy;
      if (g <= g0 && D.log[g - 1]) {
        var L = D.log[g - 1];
        yy = L.pts;
        txt = "Game " + g + " · " + fmtD(L.date) + " · " + (L.home ? "vs " : "at ") + L.opp + " · " +
          L.res + " · <b>" + L.pts + " pts</b>";
      } else if (g > g0) {
        var k = g - g0 - 1;
        yy = D.q.p50[k];
        txt = "Game " + g + " · " + fmtD(D.dates[k]) + " · median <b>" + Math.round(D.q.p50[k]) +
          " pts</b> · half of seasons between " + Math.round(D.q.p25[k]) + " and " + Math.round(D.q.p75[k]);
      } else return;
      rule.setAttribute("x1", x(g)); rule.setAttribute("x2", x(g)); rule.setAttribute("opacity", .35);
      dot.setAttribute("cx", x(g)); dot.setAttribute("cy", y(yy)); dot.setAttribute("opacity", 1);
      if (readout) readout.innerHTML = txt;
    }
    hit.addEventListener("pointermove", read);
    hit.addEventListener("pointerdown", read);
    hit.addEventListener("pointerleave", function () {
      rule.setAttribute("opacity", 0); dot.setAttribute("opacity", 0);
      if (readout) readout.innerHTML = readout.dataset.idle;
    });

    if (RM || still || !svg.animate) return;
    // choreography: the season so far draws, the paths fan out, the bands settle in
    function draw(node, delay, dur) {
      if (!node) return;
      var len = node.getTotalLength ? node.getTotalLength() : 1000;
      node.style.strokeDasharray = len; node.style.strokeDashoffset = len;
      node.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }],
        { duration: dur, delay: delay, easing: "cubic-bezier(.3,.7,.2,1)", fill: "forwards" })
        .onfinish = function () { node.style.strokeDasharray = ""; node.style.strokeDashoffset = ""; };
    }
    function fade(node, delay, dur) {
      if (!node) return;
      var op = node.getAttribute("opacity") || 1;
      node.style.opacity = 0;
      node.animate([{ opacity: 0 }, { opacity: op }], { duration: dur, delay: delay, fill: "forwards" })
        .onfinish = function () { node.style.opacity = ""; };
    }
    var medDash = med && med.getAttribute("stroke-dasharray");
    [b1, b2, med].forEach(function (n) { if (n) n.style.opacity = 0; });
    paths.forEach(function (p) { p.style.opacity = 0; });
    if (actual) { actual.style.strokeDasharray = 1e4; actual.style.strokeDashoffset = 1e4; }
    onView(host, function () {
      var t = 0;
      if (actual) { draw(actual, 0, 900); t = 700; }
      paths.forEach(function (p, i) { p.style.opacity = ""; draw(p, t + i * 22, 1100); });
      var after = t + paths.length * 22 + 500;
      fade(b1, after, 700); fade(b2, after + 120, 700);
      if (med) {
        med.style.opacity = "";
        fade(med, after + 300, 500);
        med.setAttribute("stroke-dasharray", medDash);
      }
    });
  }
  cone(false);
  (function () {
    var host = document.getElementById("cone"), lastW = host ? host.clientWidth : 0, rz = 0;
    window.addEventListener("resize", function () {
      clearTimeout(rz);
      rz = setTimeout(function () {
        if (!host || Math.abs(host.clientWidth - lastW) < 24) return;
        lastW = host.clientWidth; cone(true);
      }, 150);
    });
  })();

  /* ============================================================ 3. reveal system === */
  (function reveal() {
    if (RM) return;
    var vh = window.innerHeight, pending = [];
    var cards = document.querySelectorAll(".card, .panel, .ms, .rc");
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      // only what is below the fold is hidden, and only now that this script runs
      if (c.getBoundingClientRect().top < vh * 0.92) continue;
      c.classList.add("rv");
      pending.push(c);
    }
    /* Anything that has reached the viewport, or been scrolled or jumped past, is
       revealed on the next frame. Intersection events alone missed sections a nav link
       or a fast flick skipped over, and those stayed invisible until scrolled back to. */
    var queued = false;
    function sweep() {
      queued = false;
      var vhh = window.innerHeight, lim = vhh * 0.92, keep = [];
      // at the foot of the page the last sections can never rise past the line, so
      // anything on screen there counts as seen
      var atEnd = window.scrollY + vhh >= document.documentElement.scrollHeight - 4;
      for (var k = 0; k < pending.length; k++) {
        var top = pending[k].getBoundingClientRect().top;
        if (top < lim || (atEnd && top < vhh)) pending[k].classList.add("in");
        else keep.push(pending[k]);
      }
      pending = keep;
      if (!pending.length) {
        window.removeEventListener("scroll", queue);
        window.removeEventListener("resize", queue);
      }
    }
    function queue() { if (!queued) { queued = true; requestAnimationFrame(sweep); } }
    window.addEventListener("scroll", queue, { passive: true });
    window.addEventListener("resize", queue);
    window.addEventListener("hashchange", queue);
    var nums = document.querySelectorAll("[data-count]");
    for (var j = 0; j < nums.length; j++) (function (n) {
      var target = parseFloat(n.dataset.count), dec = +(n.dataset.dec || 0);
      var pre = n.dataset.pre || "", suf = n.dataset.suf || "", final = n.innerHTML;
      onView(n, function () {
        var t0 = performance.now(), D = 1100;
        (function tick(now) {
          var u = Math.min(1, (now - t0) / D);
          n.textContent = pre + (target * easeOut(u)).toFixed(dec) + suf;
          if (u < 1) requestAnimationFrame(tick); else n.innerHTML = final;
        })(t0);
      });
    })(nums[j]);
  })();
})();
