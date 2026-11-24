/* MagicPro kirish animatsiyasi.
   Har bir kadr seek(t) ichida vaqtdan hisoblanadi: CSS o'tishlari, taymerlar va kadrlar orasida saqlanadigan holat yo'q.
   Sahna 390x844 mantiqiy birlikda chiziladi va istalgan ekranga moslab kattalashtiriladi.
   Ranglar: oq, qora, to'q ko'k. Bitta nuqta: ekranni to'ldiradi -> MacBook -> logodagi tugmachani yoqadi. */
(function () {
  const C = {bg: "#FFFFFF", ink: "#0B0B0D", deep: "#14295C", blue: "#1F3F99", lid: "#1C1C1F", base: "#2A2A2E", screenOff: "#141416", sub: "#9A9AA0"};
  const T_END = 4.75, SW = 390, SH = 844;
  const F = {unb: "700 26px MPUnb, Unbounded, sans-serif", pac: "56px MPPac, Pacifico, cursive",
             tag: "800 24px MPInt, Inter, sans-serif", sub: "600 14px MPInt, Inter, sans-serif", pro: "MPInt, Inter, sans-serif"};
  const FONTS = [["MPPac", "pacifico.woff2", {}], ["MPUnb", "unbounded.woff2", {weight: "700"}],
                 ["MPInt", "inter-800.woff2", {weight: "800"}], ["MPInt", "inter-600.woff2", {weight: "600"}]];
  function loadFonts(base) {
    return Promise.all(FONTS.map(([fam, file, d]) =>
      new FontFace(fam, "url(" + base + file + ")", d).load().then(f => document.fonts.add(f))));
  }
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const P = (t, a, b) => clamp((t - a) / (b - a));
  const lerp = (a, b, u) => a + (b - a) * u;
  const eo = u => 1 - (1 - u) ** 3, ei = u => u * u * u;
  const eio = u => u < .5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2;
  function spring(t, z = .5, f = 3) {                // yopiq ko'rinishdagi prujina
    if (t <= 0) return 0;
    const w = 2 * Math.PI * f, wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + z * w / wd * Math.sin(wd * t));
  }
  function mix(a, b, u) {
    const h = s => [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16));
    const A = h(a), B = h(b);
    return "rgb(" + A.map((v, i) => Math.round(lerp(v, B[i], clamp(u)))).join(",") + ")";
  }
  const O = {x: 75, y: 345};                         // logolar bloki MacBook ekrani ichida
  const KNOB_OFF = [O.x + 133.1 + 7.85, O.y + 14.77], KNOB_ON = [O.x + 164.88, O.y + 14.77];

  function create(cv) {
    const ctx = cv.getContext("2d");
    let dpr = 1, s = 1, ox = 0, oy = 0, vw = 0, vh = 0, R = 490, uz = [];
    function rr(x, y, w, h, r) {
      r = Math.max(0, Math.min(r, w / 2, h / 2));
      ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
    }
    function txt(str, font, x, y, color, a = 1, align = "left") {
      if (a <= 0) return;
      ctx.save(); ctx.globalAlpha *= a; ctx.font = font; ctx.fillStyle = color; ctx.textAlign = align; ctx.fillText(str, x, y); ctx.restore();
    }
    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2.5); vw = cv.clientWidth || innerWidth; vh = cv.clientHeight || innerHeight;
      cv.width = Math.round(vw * dpr); cv.height = Math.round(vh * dpr);
      s = Math.min(vw / SW, vh / 700); ox = (vw - SW * s) / 2; oy = (vh - SH * s) / 2;
      // to'ldiruvchi doira ekranning to'rt burchagidan ham o'tib ketishi uchun
      const cx = 195, cy = 422, xs = [-ox / s, (vw - ox) / s], ys = [-oy / s, (vh - oy) / s];
      R = Math.max(...xs.flatMap(x => ys.map(y => Math.hypot(x - cx, y - cy)))) + 20;
      ctx.font = F.unb; uz = [..."uzmacb"].map((ch, i) => ({ch, x: O.x + ctx.measureText("uzmacb".slice(0, i)).width}));
    }
    function dot(t) {
      if (t < .45) return {x: 195, y: 422, r: 12 * clamp(spring(t - .05, .55, 2.4), 0, 1.25)};
      if (t < 1.70) return {x: 195, y: 422, r: lerp(12, R, ei(P(t, .45, .95)))};
      if (t < 2.05) { const u = eio(P(t, 1.70, 2.05)); return {x: 195, y: lerp(422, 386, u), r: lerp(R, 9, u)}; }
      if (t < 3.20) return {x: 195, y: 386, r: 9};
      if (t < 3.50) {
        const u = eio(P(t, 3.20, 3.50));
        return {x: lerp(195, KNOB_OFF[0], u), y: lerp(386, KNOB_OFF[1], u) - 34 * 4 * u * (1 - u), r: lerp(9, 7.85, u)};
      }
      const lead = spring(t - 3.55, .5, 3), trail = spring(t - 3.60, .62, 2.3);   // tugmacha yoqiladi, oldingi cheti cho'ziladi
      return {x: lerp(KNOB_OFF[0], KNOB_ON[0], trail), x2: lerp(KNOB_OFF[0], KNOB_ON[0], lead), y: KNOB_ON[1], r: 7.85};
    }
    function drawDot(d) {
      if (d.r <= .2) return;
      ctx.fillStyle = mix(C.blue, C.deep, (d.r - 12) / 140);
      if (d.x2 !== undefined) {
        const a = Math.min(d.x, d.x2), b = Math.max(d.x, d.x2);
        rr(a - d.r, d.y - d.r, b - a + 2 * d.r, 2 * d.r, d.r); ctx.fill(); return;
      }
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2); ctx.fill();
    }
    function pill(t) {                                 // doira ichidagi kvadrat aylanadi, kapsulaga cho'ziladi
      const sz = 120 * clamp(spring(t - .85, .6, 2.0), 0, 1.3), rot = Math.PI / 2 * spring(t - .90, .62, 2.2);
      const m = clamp(spring(t - 1.30, .78, 2.2), 0, 1.1);
      return {rot, lw: lerp(sz, 26, m), lh: lerp(sz, 260, m), r: lerp(28, 13, m) * Math.min(1, sz / 120)};
    }
    function handWord(x, y, reveal) {
      if (reveal <= 0) return;
      ctx.save(); ctx.font = F.pac;
      const w = ctx.measureText("magıc").width, xr = lerp(x - 14, x + w + 18, reveal), sl = 12.3;
      ctx.beginPath(); ctx.moveTo(x - 20, y - 56); ctx.lineTo(xr + sl, y - 56); ctx.lineTo(xr - sl, y + 34); ctx.lineTo(x - 20, y + 34); ctx.closePath(); ctx.clip();
      ctx.fillStyle = C.ink; ctx.fillText("magıc", x, y); ctx.restore();
    }
    function proPill(x, y, w, h, k) {
      if (k <= .01) return;
      ctx.save(); ctx.translate(x + w / 2, y + h / 2); ctx.scale(k, k);
      ctx.fillStyle = C.ink; rr(-w / 2, -h / 2, w, h, h * .32); ctx.fill();
      ctx.font = "800 " + (h * .52).toFixed(1) + "px " + F.pro; ctx.fillStyle = C.bg; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText("PRO", 0, 1); ctx.restore();
    }
    function seek(t) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = t < .95 ? C.bg : C.ink; ctx.fillRect(0, 0, vw, vh);
      ctx.setTransform(dpr * s, 0, 0, dpr * s, dpr * ox, dpr * oy);
      const d = dot(t);
      if (t < 2.05) drawDot(d);
      if (t > .85 && t < 1.95) {
        const q = pill(t);
        ctx.save(); ctx.translate(195, 422); ctx.rotate(q.rot); ctx.fillStyle = mix(C.ink, C.base, P(t, 1.75, 1.95));
        rr(-q.lw / 2, -q.lh / 2, q.lw, q.lh, q.r); ctx.fill(); ctx.restore();
      }
      if (t >= 1.95) {                                 // kapsula MacBook asosiga aylanadi
        const q = pill(1.95), u = eio(P(t, 1.95, 2.25));
        const w = lerp(q.lh, 340, u), h = lerp(q.lw, 13, u), cy = lerp(422, 492.5, u);
        ctx.fillStyle = C.base; rr(195 - w / 2, cy - h / 2, w, h, lerp(q.r, 6, u)); ctx.fill();
        if (u > .9) { ctx.fillStyle = C.lid; rr(170, 486, 50, 5, 2.5); ctx.fill(); }
      }
      if (t >= 2.20) {                                 // qopqoq ochiladi, ekran yonadi
        const lh = 200 * clamp(spring(t - 2.20, .62, 1.4), 0, 1.06);
        if (lh > 2) {
          ctx.fillStyle = C.lid; rr(45, 486 - lh, 300, lh, 16); ctx.fill();
          ctx.strokeStyle = "rgba(255,255,255,.08)"; ctx.lineWidth = 1; ctx.stroke();
          if (lh > 22) { ctx.fillStyle = mix(C.screenOff, C.bg, P(t, 2.70, 3.00)); rr(54, 486 - lh + 9, 282, lh - 18, 8); ctx.fill(); }
        }
      }
      if (t >= 2.95) {                                 // uzmacbook + magic, umumiy nuqta bilan
        uz.forEach((g, i) => { const u = eo(P(t, 2.95 + .03 * i, 3.25 + .03 * i)); txt(g.ch, F.unb, g.x, 367.2 + 10 * (1 - u), C.ink, u); });
        const ku = eo(P(t, 3.15, 3.45)); txt("k", F.unb, O.x + 173.5, 367.2 + 10 * (1 - ku), C.ink, ku);
        const tr = eo(P(t, 3.05, 3.25));
        if (tr > 0) { ctx.save(); ctx.globalAlpha = tr; ctx.strokeStyle = C.ink; ctx.lineWidth = 3.38; rr(O.x + 134.79, O.y + 8.61, 36.24 * tr, 12.32, 6.16); ctx.stroke(); ctx.restore(); }
        handWord(O.x + 60.4, 399, eio(P(t, 3.75, 4.30)));
        proPill(O.x + 198, O.y + 30.1, 40, 22, clamp(spring(t - 4.25, .55, 2.4), 0, 1.2));
        const a1 = eo(P(t, 4.30, 4.60)), a2 = eo(P(t, 4.42, 4.72));
        txt("Ishonchli b/u MacBook.", F.tag, 195, 578 + 10 * (1 - a1), C.bg, a1, "center");
        txt("3 oy kafolat · 8 oygacha bo‘lib to‘lash", F.sub, 195, 606 + 8 * (1 - a2), C.sub, a2, "center");
      }
      if (t >= 2.05) drawDot(d);
    }
    resize();
    return {seek, resize};
  }
  window.MPIntro = {loadFonts, create, T_END};
})();
