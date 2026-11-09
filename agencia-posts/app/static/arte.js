// Criador de artes: desenha os modelos num <canvas> com as cores e o logo do cliente.
(function () {
  var form = document.getElementById("arte-form");
  if (!form) return;
  var cfg = JSON.parse(form.getAttribute("data-cliente"));
  var canvas = document.getElementById("arte");
  var ctx = canvas.getContext("2d");
  var W = 1080, HEIGHTS = { feed: 1350, story: 1920 };
  var SERIF = '"Fraunces", Georgia, serif', SANS = '"Poppins", Arial, sans-serif';
  var state = { foto: null, logo: null };

  // ---------- cores ----------
  function rgb(h) { h = h.replace("#", ""); return [0, 2, 4].map(function (i) { return parseInt(h.slice(i, i + 2), 16); }); }
  function hex(a) { return "#" + a.map(function (v) { return Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0"); }).join(""); }
  function mix(a, b, t) { var x = rgb(a), y = rgb(b); return hex(x.map(function (v, i) { return v + (y[i] - v) * t; })); }
  function alpha(h, a) { var c = rgb(h); return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")"; }
  function lum(h) {
    var c = rgb(h).map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function palette() {
    var p = cfg.primary, s = cfg.secondary;
    return {
      p: p, s: s,
      dark: mix(p, "#000000", 0.66),
      bg: mix(s, "#ffffff", 0.8),
      acc: lum(p) > 0.4 ? mix(p, "#000000", 0.45) : p,       // destaque sobre fundo claro
      onP: lum(p) > 0.45 ? mix(p, "#000000", 0.78) : "#ffffff", // texto sobre a cor principal
      onDarkAcc: lum(s) > 0.3 ? s : mix(s, "#ffffff", 0.6)      // destaque sobre fundo escuro
    };
  }

  // ---------- modelos ----------
  function phone(p) {
    var d = (p || "").replace(/\D/g, "");
    if (d.length === 11) return "(" + d.slice(0, 2) + ") " + d.slice(2, 7) + "-" + d.slice(7);
    if (d.length === 10) return "(" + d.slice(0, 2) + ") " + d.slice(2, 6) + "-" + d.slice(6);
    return p;
  }
  var FOOTER = {
    rodape1: cfg.address ? "📍 " + cfg.address : (cfg.instagram ? "@" + cfg.instagram : cfg.name),
    rodape2: cfg.phone ? "WhatsApp " + phone(cfg.phone) : (cfg.instagram ? "@" + cfg.instagram : "")
  };
  var MODELOS = {
    promo: {
      campos: ["foto", "selo", "titulo", "destaque", "texto", "preco", "preco_base", "cta", "rodape1", "rodape2"],
      def: { selo: "Promoção da semana", titulo: "Oferta especial", destaque: "só esta semana", texto: "Aproveite enquanto durar!",
             preco: "19,90", preco_topo: "por apenas", preco_base: "só até sábado", cta: "Peça pelo WhatsApp" }
    },
    produto: {
      campos: ["foto", "selo", "titulo", "destaque", "texto", "preco", "preco_base", "rodape1"],
      def: { selo: "Novidade", titulo: "Conheça o nosso", destaque: "produto do dia", texto: "Venha experimentar!", preco: "",
             preco_topo: "a partir de", preco_base: "" }
    },
    horario: {
      campos: ["titulo", "destaque", "horarios", "texto", "rodape1", "rodape2"],
      def: { titulo: "Horário de", destaque: "funcionamento", texto: "Esperamos a sua visita!",
             horarios: "Segunda a sexta: 7h às 19h\nSábado: 7h às 14h\nDomingo: fechado" }
    },
    recado: {
      campos: ["foto", "selo", "titulo", "destaque", "texto", "rodape1"],
      def: { selo: "Data especial", titulo: "Feliz dia", destaque: "das mães", texto: "Obrigado por fazer parte da nossa história." }
    }
  };
  var touched = {};

  function val(name) { return (form.elements[name] && form.elements[name].value || "").trim(); }
  function modelo() { return form.elements.modelo.value; }
  function formato() { return form.elements.formato.value; }

  function applyDefaults() {
    var m = MODELOS[modelo()];
    Object.keys(m.def).forEach(function (k) { if (!touched[k]) form.elements[k].value = m.def[k]; });
    ["rodape1", "rodape2"].forEach(function (k) { if (!touched[k]) form.elements[k].value = FOOTER[k]; });
    if (!touched.cta && !form.elements.cta.value) form.elements.cta.value = "Peça pelo WhatsApp";
    if (cfg.theme && !touched.titulo && modelo() !== "horario") {
      form.elements.titulo.value = cfg.theme;
      if (!touched.destaque) form.elements.destaque.value = "";
    }
    document.querySelectorAll("[data-campo]").forEach(function (el) {
      el.hidden = m.campos.indexOf(el.getAttribute("data-campo")) < 0;
    });
  }

  // ---------- desenho: ajudantes ----------
  function font(weight, size, fam) { ctx.font = weight + " " + size + "px " + fam; }
  function spacing(px) { if ("letterSpacing" in ctx) ctx.letterSpacing = px + "px"; }
  function rr(x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  function wrap(text, maxW) {
    var words = text.split(/\s+/).filter(Boolean), lines = [], cur = "";
    words.forEach(function (w) {
      var t = cur ? cur + " " + w : w;
      if (ctx.measureText(t).width <= maxW || !cur) cur = t; else { lines.push(cur); cur = w; }
    });
    if (cur) lines.push(cur);
    return lines;
  }
  function widest(lines) { return lines.reduce(function (m, l) { return Math.max(m, ctx.measureText(l).width); }, 0); }
  function fit(text, weight, fam, maxSize, minSize, maxW, maxLines) {
    var size = maxSize, lines;
    for (;;) {
      font(weight, size, fam);
      lines = wrap(text, maxW);
      if ((lines.length <= maxLines && widest(lines) <= maxW) || size <= minSize) break;
      size -= 4;
    }
    return { size: size, lines: lines };
  }
  function textLines(lines, x, y, lh, align) {
    ctx.textAlign = align; ctx.textBaseline = "alphabetic";
    lines.forEach(function (l, i) { ctx.fillText(l, x, y + i * lh); });
  }

  // título em duas partes (escura + colorida), mesmo tamanho para as duas
  function measureTitle(maxW, maxSize) {
    var t = val("titulo"), d = val("destaque");
    var a = t ? fit(t, 900, SERIF, maxSize, 48, maxW, 2) : { size: maxSize, lines: [] };
    var b = d ? fit(d, 900, SERIF, maxSize, 48, maxW, 2) : { size: maxSize, lines: [] };
    var size = Math.min(a.size, b.size);
    font(900, size, SERIF);
    var la = t ? wrap(t, maxW) : [], lb = d ? wrap(d, maxW) : [];
    var lh = size * 0.98;
    return { size: size, la: la, lb: lb, lh: lh, height: (la.length + lb.length) * lh };
  }
  function drawTitle(m, x, y, align, c1, c2) {
    font(900, m.size, SERIF); spacing(-1);
    var base = y + m.size * 0.8;
    ctx.fillStyle = c1; textLines(m.la, x, base, m.lh, align);
    ctx.fillStyle = c2; textLines(m.lb, x, base + m.la.length * m.lh, m.lh, align);
    spacing(0);
    return y + m.height;
  }
  function pill(text, x, y, align, bg, fg, size) {
    size = size || 26;
    font(700, size, SANS); spacing(3);
    text = text.toUpperCase();
    var w = ctx.measureText(text).width + 52, h = size + 30;
    var left = align === "center" ? x - w / 2 : x;
    ctx.fillStyle = bg; rr(left, y, w, h, h / 2); ctx.fill();
    ctx.fillStyle = fg; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(text, left + w / 2, y + h / 2 + 1);
    spacing(0); ctx.textBaseline = "alphabetic";
    return y + h;
  }
  function cover(img, x, y, w, h, r) {
    ctx.save(); rr(x, y, w, h, r); ctx.clip();
    var z = parseFloat(val("zoom")) || 1;
    var s = Math.max(w / img.width, h / img.height) * z, iw = img.width * s, ih = img.height * s;
    ctx.drawImage(img, x + (w - iw) * (val("posx") / 100), y + (h - ih) * (val("posy") / 100), iw, ih);
    ctx.restore();
  }
  function photoOrPlaceholder(x, y, w, h, r, c) {
    if (h < 40) return;
    if (state.foto) { ctx.save(); ctx.shadowColor = "rgba(0,0,0,.22)"; ctx.shadowBlur = 40; ctx.shadowOffsetY = 14;
      ctx.fillStyle = "#fff"; rr(x, y, w, h, r); ctx.fill(); ctx.restore(); cover(state.foto, x, y, w, h, r); return; }
    ctx.fillStyle = mix(c.s, "#ffffff", 0.45); rr(x, y, w, h, r); ctx.fill();
    ctx.strokeStyle = alpha(c.dark, 0.25); ctx.lineWidth = 4; ctx.setLineDash([18, 14]); rr(x + 16, y + 16, w - 32, h - 32, r - 10); ctx.stroke(); ctx.setLineDash([]);
    font(600, 32, SANS); ctx.fillStyle = alpha(c.dark, 0.55); ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("escolha uma foto ao lado", x + w / 2, y + h / 2); ctx.textBaseline = "alphabetic";
  }
  function logo(x, y, size, c) {
    ctx.save();
    ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size / 2 + 7, 0, Math.PI * 2); ctx.fillStyle = c.p; ctx.fill();
    ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size / 2 + 3, 0, Math.PI * 2); ctx.fillStyle = "#ffffff"; ctx.fill();
    ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2); ctx.clip();
    if (state.logo) {
      ctx.fillStyle = "#ffffff"; ctx.fillRect(x, y, size, size);
      var s = Math.max(size / state.logo.width, size / state.logo.height);
      ctx.drawImage(state.logo, x + (size - state.logo.width * s) / 2, y + (size - state.logo.height * s) / 2, state.logo.width * s, state.logo.height * s);
    } else {
      ctx.fillStyle = c.p; ctx.fillRect(x, y, size, size);
      var ini = cfg.name.split(/\s+/).filter(function (w) { return w.length > 2; }).slice(0, 2).map(function (w) { return w[0]; }).join("").toUpperCase() || cfg.name[0];
      font(900, size * 0.36, SERIF); ctx.fillStyle = c.onP === "#ffffff" ? c.onDarkAcc : c.onP;
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(ini, x + size / 2, y + size / 2 + 2);
    }
    ctx.restore(); ctx.textBaseline = "alphabetic";
  }
  function header(x, y, align, c, light) {
    var size = 100, gap = 24;
    font(900, 40, SERIF); var wn = ctx.measureText(cfg.name).width;
    font(600, 20, SANS); spacing(4); var ws = cfg.segment ? ctx.measureText(cfg.segment.toUpperCase()).width : 0; spacing(0);
    var total = size + gap + Math.max(wn, ws);
    var left = align === "center" ? x - total / 2 : x;
    logo(left, y, size, c);
    var tx = left + size + gap, mid = y + size / 2;
    ctx.textAlign = "left";
    font(900, 40, SERIF); ctx.fillStyle = light ? "#ffffff" : c.acc;
    ctx.fillText(cfg.name, tx, cfg.segment ? mid - 2 : mid + 14);
    if (cfg.segment) {
      font(600, 20, SANS); spacing(4); ctx.fillStyle = light ? "rgba(255,255,255,.85)" : alpha(c.dark, 0.75);
      ctx.fillText(cfg.segment.toUpperCase(), tx, mid + 30); spacing(0);
    }
  }
  function priceBadge(cx, cy, R, c) {
    var preco = val("preco");
    if (!preco) return;
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(-10 * Math.PI / 180);
    ctx.shadowColor = "rgba(0,0,0,.3)"; ctx.shadowBlur = 36; ctx.shadowOffsetY = 16;
    ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.fillStyle = c.p; ctx.fill();
    ctx.shadowColor = "transparent";
    ctx.beginPath(); ctx.arc(0, 0, R - 20, 0, Math.PI * 2); ctx.strokeStyle = c.onDarkAcc; ctx.lineWidth = 7; ctx.setLineDash([22, 13]); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = c.onP; ctx.textAlign = "center";
    var top = val("preco_topo");
    if (top) { font(600, R * 0.17, SANS); ctx.fillText(top, 0, -R * 0.36); }
    var size = R * 0.74;
    font(900, size, SERIF); spacing(-3);
    while (ctx.measureText(preco).width > R * 1.42 && size > 30) { size -= 3; font(900, size, SERIF); }
    var pw = ctx.measureText(preco).width; spacing(0);
    var rs = Math.max(22, size * 0.32);
    font(800, rs, SANS); var rw = ctx.measureText("R$").width + 4;
    var start = -(pw + rw) / 2, baseY = R * 0.1 + size * 0.3;
    ctx.textAlign = "left"; ctx.fillText("R$", start, baseY - size * 0.42);
    font(900, size, SERIF); spacing(-3); ctx.fillText(preco, start + rw, baseY); spacing(0);
    var base = val("preco_base");
    if (base) { var bs = R * 0.12; font(700, bs, SANS); spacing(2); while (ctx.measureText(base.toUpperCase()).width > R * 1.3 && bs > 12) { bs -= 1; font(700, bs, SANS); }
      ctx.fillStyle = c.onDarkAcc; ctx.textAlign = "center"; ctx.fillText(base.toUpperCase(), 0, R * 0.58); spacing(0); }
    ctx.restore();
  }
  function footerBand(H, h, c, centered) {
    ctx.fillStyle = c.p; ctx.fillRect(0, H - h, W, h);
    var a = val("rodape1"), b = val("rodape2"), y = H - h / 2;
    ctx.fillStyle = c.onP; ctx.textBaseline = "middle";
    var size = 30; font(600, size, SANS);
    if (centered || !b || !a) {
      var t = [a, b].filter(Boolean).join("   ·   ");
      while (ctx.measureText(t).width > W - 120 && size > 18) { size -= 2; font(600, size, SANS); }
      ctx.textAlign = "center"; ctx.fillText(t, W / 2, y);
    } else {
      while (ctx.measureText(a).width + ctx.measureText(b).width > W - 190 && size > 18) { size -= 2; font(600, size, SANS); }
      ctx.textAlign = "left"; ctx.fillText(a, 64, y);
      ctx.textAlign = "right"; ctx.fillText(b, W - 64, y);
    }
    ctx.textBaseline = "alphabetic";
  }
  function supportText(text, x, y, maxW, align, color, size, maxLines) {
    if (!text) return y;
    var f = fit(text, 500, SANS, size, 22, maxW, maxLines || 2);
    ctx.fillStyle = color; textLines(f.lines, x, y + f.size, f.size * 1.3, align);
    return y + f.size * 1.3 * f.lines.length;
  }
  function glow(x, y, r, color, a) {
    var g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, alpha(color, a)); g.addColorStop(1, alpha(color, 0));
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, canvas.height);
  }

  // ---------- modelos ----------
  function drawPromo(H, c, story) {
    ctx.fillStyle = c.bg; ctx.fillRect(0, 0, W, H);
    glow(W * 0.85, H * 0.06, 650, c.s, 0.75); glow(0, H, 500, c.s, 0.35);
    var band = story ? 130 : 110, hasPrice = !!val("preco");
    if (!story) {
      header(64, 60, "left", c);
      var y = 225;
      if (val("selo")) y = pill(val("selo"), 64, y, "left", c.dark, c.onDarkAcc) + 26;
      y = drawTitle(measureTitle(952, 116), 64, y, "left", c.dark, c.acc) + 10;
      y = supportText(val("texto"), 64, y, 952, "left", alpha(c.dark, 0.85), 34, 2);
      var top = y + 44, bottom = H - band - 44, left = hasPrice ? 330 : 64;
      photoOrPlaceholder(left, top, W - 64 - left, bottom - top, 40, c);
      priceBadge(64 + 150, top + Math.max(150, (bottom - top) / 2), 150, c);
      footerBand(H, band, c, false);
    } else {
      header(W / 2, 140, "center", c);
      var ys = 320;
      if (val("selo")) ys = pill(val("selo"), W / 2, ys, "center", c.dark, c.onDarkAcc) + 30;
      ys = drawTitle(measureTitle(960, 132), W / 2, ys, "center", c.dark, c.acc) + 10;
      ys = supportText(val("texto"), W / 2, ys, 940, "center", alpha(c.dark, 0.85), 36, 2);
      var cta = val("cta"), ctaTop = H - band - 80 - 112;
      var t2 = ys + 50, b2 = (cta ? ctaTop : H - band) - 50;
      photoOrPlaceholder(90, t2, W - 180, b2 - t2, 48, c);
      priceBadge(W - 90 - 130, b2 - 120, 150, c);
      if (cta) {
        ctx.fillStyle = c.dark; rr(110, ctaTop, W - 220, 112, 56); ctx.fill();
        font(800, 40, SANS); spacing(1); ctx.fillStyle = c.onDarkAcc; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(cta.toUpperCase() + "  👇", W / 2, ctaTop + 58); ctx.textBaseline = "alphabetic"; spacing(0);
      }
      footerBand(H, band, c, true);
    }
  }

  function drawProduto(H, c, story) {
    if (state.foto) { ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H); cover(state.foto, 0, 0, W, H, 0); }
    else { var g0 = ctx.createLinearGradient(0, 0, W, H); g0.addColorStop(0, c.p); g0.addColorStop(1, c.dark); ctx.fillStyle = g0; ctx.fillRect(0, 0, W, H);
      glow(W * 0.7, H * 0.3, 600, c.s, 0.45); }
    var g = ctx.createLinearGradient(0, H * 0.32, 0, H);
    g.addColorStop(0, alpha(c.dark, 0)); g.addColorStop(0.55, alpha(c.dark, 0.78)); g.addColorStop(1, alpha(c.dark, 0.96));
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    var gt = ctx.createLinearGradient(0, 0, 0, 260); gt.addColorStop(0, "rgba(0,0,0,.35)"); gt.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = gt; ctx.fillRect(0, 0, W, 260);
    var align = story ? "center" : "left", x = story ? W / 2 : 64, maxW = story ? 940 : 952;
    header(x, story ? 130 : 60, align, c, true);
    priceBadge(W - 64 - 130, story ? 470 : 300, 140, c);
    // texto de baixo para cima
    var m = measureTitle(maxW, story ? 132 : 120);
    var foot = val("rodape1"), y = H - (story ? 170 : 70);
    if (foot) { font(600, 30, SANS); ctx.fillStyle = "rgba(255,255,255,.85)"; ctx.textAlign = align; ctx.fillText(foot, x, y); y -= 60; }
    var texto = val("texto"), tf = null;
    if (texto) { tf = fit(texto, 500, SANS, 36, 22, maxW, 2); y -= tf.size * 1.3 * tf.lines.length; }
    var titleTop = y - m.height - 10;
    var seloH = val("selo") ? 56 + 26 : 0;
    if (seloH) pill(val("selo"), x, titleTop - seloH, align, c.onDarkAcc, c.dark);
    drawTitle(m, x, titleTop, align, "#ffffff", c.onDarkAcc);
    if (tf) { ctx.fillStyle = "rgba(255,255,255,.9)"; font(500, tf.size, SANS); textLines(tf.lines, x, y + tf.size, tf.size * 1.3, align); }
  }

  function drawHorario(H, c, story) {
    ctx.fillStyle = c.p; ctx.fillRect(0, 0, W, H);
    glow(W, 0, 700, c.s, 0.45); glow(0, H, 600, c.s, 0.3);
    header(W / 2, story ? 150 : 70, "center", c, c.onP === "#ffffff");
    var top = story ? 360 : 240, bottom = H - (story ? 260 : 140), cx = 70, cw = W - 140;
    ctx.save(); ctx.shadowColor = "rgba(0,0,0,.25)"; ctx.shadowBlur = 50; ctx.shadowOffsetY = 20;
    ctx.fillStyle = c.bg; rr(cx, top, cw, bottom - top, 48); ctx.fill(); ctx.restore();
    var y = drawTitle(measureTitle(cw - 120, story ? 110 : 92), W / 2, top + 70, "center", c.dark, c.acc);
    var rows = val("horarios").split("\n").map(function (l) { return l.trim(); }).filter(Boolean).slice(0, 9);
    var texto = val("texto");
    var areaTop = y + 50, areaBottom = bottom - (texto ? 130 : 60);
    var rh = Math.min(story ? 130 : 88, (areaBottom - areaTop) / Math.max(rows.length, 1));
    var fs = Math.min(story ? 46 : 36, rh * 0.45);
    var ry = areaTop + ((areaBottom - areaTop) - rh * rows.length) / 2;
    rows.forEach(function (row, i) {
      var parts = row.split(/:(.+)/), label = parts[0].trim(), value = (parts[1] || "").trim();
      var yy = ry + rh * i + rh / 2;
      ctx.textBaseline = "middle";
      font(600, fs, SANS); ctx.fillStyle = c.dark; ctx.textAlign = "left"; ctx.fillText(label, cx + 70, yy);
      var lw = ctx.measureText(label).width;
      font(700, fs, SANS); ctx.fillStyle = c.acc; ctx.textAlign = "right"; ctx.fillText(value, cx + cw - 70, yy);
      var vw = ctx.measureText(value).width;
      if (value) { ctx.strokeStyle = alpha(c.dark, 0.25); ctx.lineWidth = 3; ctx.setLineDash([3, 10]); ctx.beginPath();
        ctx.moveTo(cx + 70 + lw + 20, yy + 4); ctx.lineTo(cx + cw - 70 - vw - 20, yy + 4); ctx.stroke(); ctx.setLineDash([]); }
      if (i < rows.length - 1) { ctx.strokeStyle = alpha(c.dark, 0.08); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(cx + 60, ry + rh * (i + 1)); ctx.lineTo(cx + cw - 60, ry + rh * (i + 1)); ctx.stroke(); }
      ctx.textBaseline = "alphabetic";
    });
    if (texto) supportText(texto, W / 2, bottom - 110, cw - 120, "center", alpha(c.dark, 0.8), 32, 1);
    var foot = [val("rodape1"), val("rodape2")].filter(Boolean).join("   ·   ");
    if (foot) { var s = 30; font(600, s, SANS); while (ctx.measureText(foot).width > W - 120 && s > 18) { s -= 2; font(600, s, SANS); }
      ctx.fillStyle = c.onP; ctx.textAlign = "center"; ctx.fillText(foot, W / 2, H - (story ? 140 : 62)); }
  }

  function drawRecado(H, c, story) {
    if (state.foto) { cover(state.foto, 0, 0, W, H, 0); ctx.fillStyle = alpha(c.p, 0.8); ctx.fillRect(0, 0, W, H); }
    else {
      ctx.fillStyle = c.p; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = alpha(c.s, 0.22); ctx.beginPath(); ctx.arc(W - 40, 80, 380, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = alpha(c.s, 0.16); ctx.beginPath(); ctx.arc(60, H - 60, 300, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = alpha("#ffffff", 0.08); ctx.beginPath(); ctx.arc(W * 0.2, H * 0.22, 90, 0, Math.PI * 2); ctx.fill();
    }
    var light = c.onP === "#ffffff" || !!state.foto;
    var c1 = light ? "#ffffff" : c.onP, c2 = light ? c.onDarkAcc : c.dark;
    var m = measureTitle(940, story ? 150 : 136);
    var texto = val("texto"), tf = null;
    if (texto) tf = fit(texto, 500, SANS, 38, 22, 880, 3);
    var seloH = val("selo") ? 56 + 34 : 0;
    var blockH = seloH + m.height + (tf ? 30 + tf.size * 1.3 * tf.lines.length : 0);
    var y = (H - (story ? 420 : 300)) / 2 - blockH / 2 + (story ? 60 : 30);
    if (seloH) y = pill(val("selo"), W / 2, y, "center", c.onDarkAcc, c.dark) + 34;
    y = drawTitle(m, W / 2, y, "center", c1, c2) + 30;
    if (tf) { ctx.fillStyle = light ? "rgba(255,255,255,.92)" : c.onP; font(500, tf.size, SANS); textLines(tf.lines, W / 2, y + tf.size, tf.size * 1.3, "center"); }
    var ly = H - (story ? 400 : 290);
    logo(W / 2 - 60, ly, 120, c);
    font(900, 40, SERIF); ctx.fillStyle = c1; ctx.textAlign = "center"; ctx.fillText(cfg.name, W / 2, ly + 190);
    var foot = val("rodape1");
    if (foot) { font(500, 26, SANS); ctx.fillStyle = light ? "rgba(255,255,255,.85)" : c.onP; ctx.fillText(foot, W / 2, ly + 236); }
  }

  var DRAW = { promo: drawPromo, produto: drawProduto, horario: drawHorario, recado: drawRecado };
  var pending = false;
  function draw() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () {
      pending = false;
      var H = HEIGHTS[formato()];
      if (canvas.height !== H) canvas.height = H;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, W, H);
      DRAW[modelo()](H, palette(), formato() === "story");
    });
  }

  // ---------- imagens ----------
  function loadImage(src) {
    return new Promise(function (ok, fail) { var img = new Image(); img.onload = function () { ok(img); }; img.onerror = fail; img.src = src; });
  }
  form.addEventListener("change", function (e) {
    var t = e.target;
    if (t.name === "modelo") applyDefaults();
    if (t.name === "foto") {
      form.elements.foto_local.value = "";
      if (!t.value) { state.foto = null; draw(); return; }
      loadImage(t.value).then(function (img) { state.foto = img; draw(); });
    }
    if (t.name === "foto_local" && t.files[0]) {
      loadImage(URL.createObjectURL(t.files[0])).then(function (img) {
        state.foto = img;
        form.querySelectorAll('input[name="foto"]').forEach(function (r) { r.checked = false; });
        draw();
      });
    }
    draw();
  });
  form.addEventListener("input", function (e) { if (e.target.name) touched[e.target.name] = true; draw(); });

  // ---------- salvar / baixar ----------
  var status = form.querySelector("[data-status]");
  function fileName() {
    var slug = cfg.name.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return slug + "-" + modelo() + "-" + formato() + "-" + new Date().toISOString().slice(0, 10) + ".png";
  }
  function withBlob(fn) { canvas.toBlob(function (blob) { fn(blob); }, "image/png"); }
  form.querySelector("[data-baixar]").addEventListener("click", function () {
    withBlob(function (blob) {
      var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = fileName();
      document.body.appendChild(a); a.click(); a.remove();
    });
  });
  var saveBtn = form.querySelector("[data-salvar]");
  saveBtn.addEventListener("click", function () {
    saveBtn.disabled = true; status.textContent = "Salvando…";
    withBlob(function (blob) {
      var fd = new FormData();
      fd.append("_csrf", cfg.csrf); fd.append("post_id", cfg.post_id || ""); fd.append("arte", blob, fileName());
      fetch(cfg.save_url, { method: "POST", body: fd, credentials: "same-origin" })
        .then(function (r) { return r.json().then(function (j) { return [r.ok, j]; }); })
        .then(function (res) {
          if (res[0] && res[1].ok) {
            if (cfg.post_id) { window.location = res[1].voltar; return; }
            status.innerHTML = "";
            status.append("Arte salva na pasta do cliente. ");
            var a = document.createElement("a"); a.href = res[1].voltar; a.textContent = "Ver artes"; status.append(a);
          } else { status.textContent = (res[1] && res[1].erro) || "Não deu para salvar."; }
        })
        .catch(function () { status.textContent = "Sem conexão. Tente de novo."; })
        .finally(function () { saveBtn.disabled = false; });
    });
  });

  // ---------- início ----------
  var faces = [new FontFace("Fraunces", "url(" + cfg.fonts + "Fraunces.woff2)", { weight: "100 900" })];
  [500, 600, 700, 800].forEach(function (w) { faces.push(new FontFace("Poppins", "url(" + cfg.fonts + "Poppins-" + w + ".woff2)", { weight: String(w) })); });
  var loading = faces.map(function (f) { return f.load().then(function (ff) { document.fonts.add(ff); }); });
  if (cfg.logo) loading.push(loadImage(cfg.logo).then(function (img) { state.logo = img; }));
  applyDefaults();
  Promise.all(loading.map(function (p) { return p.catch(function () {}); })).then(function () {
    var l = document.querySelector("[data-carregando]"); if (l) l.remove();
    canvas.setAttribute("data-pronto", "1");
    draw();
  });
})();
