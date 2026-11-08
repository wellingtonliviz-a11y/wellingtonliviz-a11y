(function () {
  "use strict";
  var KEY = "precifica-facil:v1";
  var UNITS = { g: ["g", 1], kg: ["g", 1000], ml: ["ml", 1], L: ["ml", 1000], un: ["un", 1] };

  // ---------- utilidades ----------
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function parseNum(v) {
    if (typeof v === "number") return v;
    var t = String(v || "").trim().replace(/r\$|%|\s/gi, "");
    if (!t) return 0;
    if (t.indexOf(",") >= 0) t = t.replace(/\./g, "").replace(",", ".");
    var n = parseFloat(t);
    return isFinite(n) ? n : 0;
  }
  function brl(n) {
    if (n == null || !isFinite(n)) return "—";
    return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }
  function fmt(n, d) {
    if (!isFinite(n)) return "";
    return n.toLocaleString("pt-BR", { maximumFractionDigits: d == null ? 2 : d });
  }
  function pct(f) { return isFinite(f) ? fmt(f * 100, 1) + "%" : "—"; }
  function smallBrl(n) {
    if (!isFinite(n)) return "—";
    if (n >= 0.1) return brl(n);
    return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 4 });
  }

  // ---------- dados ----------
  // fotos de exemplo ficam no próprio sistema (/f/ex-...)
  var SAMPLE_MENU = {
    "Brigadeiro tradicional": { show: true, desc: "Chocolate 50% cacau e granulado, feito na hora", photo: "ex-brigadeiro" },
    "Bolo de pote de chocolate": { show: true, desc: "Massa fofinha, brigadeiro cremoso e ganache", photo: "ex-bolo-de-pote" },
    "Açaí 300 ml completo": { show: true, desc: "Açaí com granola, banana, leite em pó e leite condensado", photo: "ex-acai" }
  };
  function isSamplePhoto(id) { return /^ex-/.test(id || ""); }
  function sample() {
    var ing = [
      ["Leite condensado", 6.49, 395, "g"], ["Creme de leite", 3.29, 200, "g"],
      ["Chocolate em pó 50%", 9.9, 200, "g"], ["Manteiga", 11.9, 200, "g"],
      ["Granulado", 7.5, 500, "g"], ["Forminha nº 4", 6.0, 100, "un"],
      ["Farinha de trigo", 5.49, 1, "kg"], ["Açúcar", 4.79, 1, "kg"], ["Ovos", 12.0, 12, "un"],
      ["Leite integral", 5.29, 1, "L"], ["Pote 250 ml com tampa", 22.0, 50, "un"],
      ["Polpa de açaí", 24.9, 1, "kg"], ["Granola", 18.0, 1, "kg"], ["Leite em pó", 19.9, 400, "g"],
      ["Banana", 6.0, 1, "kg"], ["Copo 300 ml + tampa", 17.5, 50, "un"]
    ].map(function (r) { return { id: uid(), name: r[0], price: r[1], qty: r[2], unit: r[3] }; });
    function id(name) { return ing.filter(function (i) { return i.name === name; })[0].id; }
    return {
      v: 1, example: true,
      settings: { business: "Doces da Ana", margin: 40, fee: 4, extras: 10, hourly: 15, round: 0.5 },
      ingredients: ing,
      products: [
        { id: uid(), name: "Brigadeiro tradicional", yield: 30, minutes: 50, margin: null, current: 1.5,
          items: [[id("Leite condensado"), 395], [id("Chocolate em pó 50%"), 40], [id("Manteiga"), 15],
                  [id("Granulado"), 120], [id("Forminha nº 4"), 30]] },
        { id: uid(), name: "Bolo de pote de chocolate", yield: 8, minutes: 90, margin: null, current: 12,
          items: [[id("Farinha de trigo"), 240], [id("Açúcar"), 200], [id("Ovos"), 3], [id("Chocolate em pó 50%"), 80],
                  [id("Leite integral"), 240], [id("Leite condensado"), 395], [id("Creme de leite"), 200],
                  [id("Pote 250 ml com tampa"), 8]] },
        { id: uid(), name: "Açaí 300 ml completo", yield: 1, minutes: 4, margin: 45, current: 14,
          items: [[id("Polpa de açaí"), 220], [id("Granola"), 30], [id("Leite em pó"), 20], [id("Banana"), 60],
                  [id("Leite condensado"), 30], [id("Copo 300 ml + tampa"), 1]] }
      ].map(function (p) {
        p.items = p.items.map(function (it) { return { ingId: it[0], qty: it[1] }; });
        p.menu = SAMPLE_MENU[p.name] || { show: true, desc: "", photo: null };
        return p;
      })
    };
  }
  function blank() {
    return { v: 1, example: false,
      settings: { business: "", margin: 40, fee: 0, extras: 10, hourly: 0, round: 0.5 },
      ingredients: [], products: [] };
  }
  var CFG = window.PRECIFICA || {};
  var MODE = CFG.mode === "conta" ? "conta" : "demo";
  var state = null;
  var saveTimer = null, saving = false, dirty = false;

  function loadLocal() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) { var d = JSON.parse(raw); if (d && d.v === 1) return d; }
    } catch (e) { /* armazenamento indisponível */ }
    return sample();
  }
  function setStatus(text, kind) {
    var el = document.getElementById("saveStatus");
    if (el) { el.textContent = text; el.setAttribute("data-state", kind || ""); }
  }
  function api(method, body) {
    return fetch("/api/dados", {
      method: method, credentials: "same-origin", keepalive: method === "PUT",
      headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
      body: body
    }).then(function (r) {
      if (r.status === 401) { location.href = "/entrar"; throw new Error("auth"); }
      if (!r.ok) throw new Error("http " + r.status);
      return r.json();
    });
  }
  function flush() {
    if (MODE !== "conta" || saving || !dirty) return;
    clearTimeout(saveTimer);
    saving = true; dirty = false; setStatus("Salvando…", "pendente");
    api("PUT", JSON.stringify(state)).then(function () {
      saving = false;
      if (dirty) flush(); else setStatus("Salvo na nuvem", "ok");
    }, function (err) {
      saving = false; dirty = true;
      if (err.message === "auth") return;
      setStatus("Sem conexão. Tentando salvar de novo…", "erro");
      saveTimer = setTimeout(flush, 5000);
    });
  }
  function save() {
    clearTimeout(saveTimer);
    if (MODE === "conta") {
      dirty = true; setStatus("Salvando…", "pendente");
      saveTimer = setTimeout(flush, 700);
      return;
    }
    saveTimer = setTimeout(function () {
      try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* ignora */ }
    }, 200);
  }
  window.addEventListener("pagehide", flush);
  document.addEventListener("visibilitychange", function () { if (document.hidden) flush(); });

  function ingById(id) { return state.ingredients.filter(function (i) { return i.id === id; })[0]; }
  function baseUnit(ing) { return (UNITS[ing.unit] || UNITS.un)[0]; }
  function costPerBase(ing) {
    var f = (UNITS[ing.unit] || UNITS.un)[1];
    var q = parseNum(ing.qty) * f;
    return q > 0 ? parseNum(ing.price) / q : 0;
  }

  // ---------- cálculo ----------
  function calc(p) {
    var s = state.settings;
    var ingCost = 0;
    p.items.forEach(function (it) {
      var ing = ingById(it.ingId);
      if (ing) ingCost += parseNum(it.qty) * costPerBase(ing);
    });
    var extras = ingCost * parseNum(s.extras) / 100;
    var labor = parseNum(p.minutes) / 60 * parseNum(s.hourly);
    var batch = ingCost + extras + labor;
    var y = parseNum(p.yield);
    var unit = y > 0 ? batch / y : NaN;
    var m = (p.margin == null || p.margin === "" ? parseNum(s.margin) : parseNum(p.margin)) / 100;
    var f = parseNum(s.fee) / 100;
    var denom = 1 - m - f;
    var suggested = denom > 0.05 && isFinite(unit) ? unit / denom : NaN;
    var step = parseNum(s.round);
    var rounded = isFinite(suggested) && step > 0 ? Math.ceil(suggested / step - 1e-9) * step : suggested;
    var out = {
      ingCost: ingCost, extras: extras, labor: labor, batch: batch, unit: unit,
      margin: m, fee: f, suggested: suggested, price: rounded,
      profitUnit: rounded * (1 - f) - unit, invalid: denom <= 0.05
    };
    out.profitBatch = out.profitUnit * y;
    var cur = parseNum(p.current);
    if (cur > 0 && isFinite(unit)) {
      out.current = cur;
      out.currentProfit = cur * (1 - f) - unit;
      out.currentMargin = out.currentProfit / cur;
    }
    return out;
  }
  // compara a margem real com a meta (com folga de meio ponto percentual)
  function level(m, goal) { return m < 0 ? "crit" : m < goal - 0.005 ? "warn" : "good"; }
  function levelLabel(m, goal) { return m < 0 ? "Prejuízo" : m < goal - 0.005 ? "Abaixo da meta" : "Na meta"; }

  // ---------- navegação ----------
  var view = { tab: "produtos", editing: null, confirm: null };
  var app = document.getElementById("app");

  function setTab(tab) {
    if (!state) return;
    view.tab = tab; view.editing = null; view.confirm = null;
    document.querySelectorAll("nav.tabs button").forEach(function (b) {
      b.setAttribute("aria-selected", String(b.dataset.tab === tab));
    });
    render();
    window.scrollTo(0, 0);
  }

  function render() {
    document.getElementById("bizName").textContent = state.settings.business || "";
    if (view.tab === "produtos") view.editing ? renderEditor() : renderProducts();
    else if (view.tab === "ingredientes") renderIngredients();
    else if (view.tab === "cardapio") renderMenu();
    else renderSettings();
  }

  function exampleNotice() {
    if (!state.example) return "";
    return '<div class="notice"><span><b>Estes são dados de exemplo.</b> Edite à vontade ou comece com a sua lista.</span>' +
      '<button class="btn small" data-action="start-blank">Começar do zero</button></div>';
  }

  // ---------- produtos ----------
  var ICONS = {
    coin: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v10M14.8 9.2c-.5-.8-1.5-1.2-2.8-1.2-1.6 0-2.8.8-2.8 2s1.2 1.7 2.8 2 2.8.8 2.8 2-1.2 2-2.8 2c-1.3 0-2.4-.5-2.9-1.3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    tag: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5V4.5A1.5 1.5 0 0 1 4.5 3h7l9.5 9.5-8.5 8.5L3 11.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><circle cx="8" cy="8" r="1.6" fill="currentColor"/></svg>',
    trend: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17l6-6 4 4 8-8M15 7h6v6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  };
  function productPhoto(p) { var id = p.menu && p.menu.photo; return id && (MODE === "conta" || isSamplePhoto(id)) ? id : null; }
  function heroArt() {
    var withPhoto = state.products.filter(productPhoto)[0];
    if (withPhoto) return '<img src="/f/' + esc(productPhoto(withPhoto)) + '" alt="' + esc(withPhoto.name) + '">';
    var tpl = document.getElementById("heroArt");
    return tpl ? tpl.innerHTML : "";
  }
  function renderHero() {
    var calcs = state.products.map(function (p) { return { p: p, c: calc(p) }; });
    var priced = calcs.filter(function (x) { return x.c.current != null; });
    var avg = priced.length ? priced.reduce(function (s, x) { return s + x.c.currentMargin; }, 0) / priced.length : NaN;
    var attention = priced.filter(function (x) { return level(x.c.currentMargin, x.c.margin) !== "good"; }).length;
    var biz = (state.settings.business || "").trim();
    return '<section class="hero"><div class="hero-text">' +
      '<span class="eyebrow">' + ICONS.tag.replace('<svg', '<svg width="14" height="14"') + "Calculadora de precificação</span>" +
      "<h2>" + (biz ? "Olá, " + esc(biz) + "!" : "Descubra o preço certo") + "</h2>" +
      "<p>Calcule o custo real de cada receita com o que você comprou e usou, inclua taxas e o valor do seu trabalho e veja o preço ideal de venda por unidade.</p>" +
      '<div class="hero-stats">' +
      '<div class="hero-stat"><b>' + state.products.length + "</b><span>produtos cadastrados</span></div>" +
      '<div class="hero-stat"><b>' + (isFinite(avg) ? pct(avg) : "—") + "</b><span>margem média do que você cobra</span></div>" +
      '<div class="hero-stat' + (attention ? " attn" : "") + '"><b>' + attention + "</b><span>" + (attention === 1 ? "produto precisa" : "produtos precisam") + " de atenção</span></div>" +
      "</div></div>" +
      '<div class="hero-art">' + heroArt() + "</div></section>";
  }
  function renderProducts() {
    var list = state.products.map(function (p) {
      var c = calc(p);
      var chip = c.current != null
        ? '<span class="chip ' + level(c.currentMargin, c.margin) + '">' + levelLabel(c.currentMargin, c.margin) + " · " + pct(c.currentMargin) + "</span>"
        : '<span class="chip neutral">Sugerido</span>';
      var photo = productPhoto(p);
      var thumb = photo
        ? '<img class="p-thumb" src="/f/' + esc(photo) + '" alt="">'
        : '<span class="p-thumb" aria-hidden="true">' + esc((p.name || "?").trim().charAt(0).toUpperCase() || "?") + "</span>";
      var meta = "Rende " + fmt(parseNum(p.yield), 0) + " un · custo " + brl(c.unit) + "/un" +
        (c.current != null ? " · sugerido " + brl(c.price) : "");
      return '<button class="product" data-action="edit" data-id="' + p.id + '">' + thumb +
        '<span class="p-main"><span class="p-name">' + esc(p.name || "Sem nome") + '</span><span class="p-meta num">' + meta + "</span></span>" +
        '<span class="p-price"><strong>' + brl(c.current != null ? c.current : c.price) + "</strong>" + chip + "</span></button>";
    }).join("");
    app.innerHTML = renderHero() + exampleNotice() +
      '<div class="row spread"><h2 class="section-title">Seus produtos</h2>' +
      '<button class="btn primary" data-action="new-product">+ Novo produto</button></div>' +
      (state.products.length
        ? '<div class="products">' + list + "</div>"
        : '<div class="empty"><p>Nenhum produto ainda.<br>Cadastre os ingredientes e depois monte a receita do seu primeiro produto.</p>' +
          (state.ingredients.length ? "" : '<button class="btn" data-action="go-ings">Cadastrar ingredientes</button>') + "</div>");
  }

  function renderEditor() {
    var p = state.products.filter(function (x) { return x.id === view.editing; })[0];
    if (!p) { view.editing = null; return renderProducts(); }
    var s = state.settings;
    var options = state.ingredients.slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
    function itemRow(it, idx) {
      var ing = ingById(it.ingId);
      var sel = '<select data-item="' + idx + '" data-field="ingId" aria-label="Ingrediente">' +
        '<option value="">Escolha o ingrediente</option>' +
        options.map(function (o) {
          return '<option value="' + o.id + '"' + (o.id === it.ingId ? " selected" : "") + ">" + esc(o.name) + "</option>";
        }).join("") + "</select>";
      return '<div class="item">' + sel +
        '<span class="suffix qty"><input inputmode="decimal" data-item="' + idx + '" data-field="qty" value="' + esc(fmt(parseNum(it.qty), 3)) + '" aria-label="Quantidade usada"><em data-unit="' + idx + '">' + (ing ? baseUnit(ing) : "") + "</em></span>" +
        '<span class="cost num" data-cost="' + idx + '"></span>' +
        '<button class="iconbtn" data-action="del-item" data-idx="' + idx + '" aria-label="Remover ingrediente">×</button></div>';
    }
    var delArmed = view.confirm === "del-product";
    app.innerHTML =
      '<div class="row spread"><button class="btn ghost" data-action="back">← Produtos</button>' +
      '<div class="row"><button class="btn small" data-action="dup-product">Duplicar</button>' +
      '<button class="btn small danger' + (delArmed ? " armed" : "") + '" data-action="del-product">' + (delArmed ? "Toque de novo para excluir" : "Excluir") + "</button></div></div>" +

      '<section class="panel"><label class="field"><span>NOME DO PRODUTO</span>' +
      '<input id="p-name" data-p="name" value="' + esc(p.name) + '" placeholder="Ex: Coxinha de frango"></label>' +
      '<div class="grid">' +
      '<label class="field"><span>RENDIMENTO</span><span class="suffix"><input id="p-yield" inputmode="numeric" data-p="yield" value="' + esc(fmt(parseNum(p.yield), 0)) + '"><em>un</em></span></label>' +
      '<label class="field"><span>TEMPO DE PREPARO</span><span class="suffix"><input id="p-min" inputmode="numeric" data-p="minutes" value="' + esc(fmt(parseNum(p.minutes), 0)) + '"><em>min</em></span></label>' +
      "</div></section>" +

      '<section class="panel"><div class="row spread"><h3 class="section-title">Ingredientes da receita</h3>' +
      '<span class="hint">Use a receita inteira, incluindo embalagens</span></div>' +
      (options.length
        ? '<div class="items">' + p.items.map(itemRow).join("") + "</div>" +
          '<div><button class="btn small" data-action="add-item">+ Adicionar ingrediente</button></div>'
        : '<p class="hint">Você ainda não cadastrou ingredientes.</p><div><button class="btn small" data-action="go-ings">Cadastrar ingredientes</button></div>') +
      "</section>" +

      '<section class="panel"><div class="grid">' +
      '<label class="field"><span>MARGEM DESEJADA</span><span class="suffix"><input id="p-margin" inputmode="decimal" data-p="margin" value="' + (p.margin == null ? "" : esc(fmt(parseNum(p.margin), 1))) + '" placeholder="' + esc(fmt(parseNum(s.margin), 1)) + ' (padrão)"><em>%</em></span></label>' +
      '<label class="field"><span>PREÇO ATUAL (OPCIONAL)</span><span class="suffix"><input id="p-current" inputmode="decimal" data-p="current" value="' + (parseNum(p.current) > 0 ? esc(fmt(parseNum(p.current), 2)) : "") + '" placeholder="0,00"><em>R$</em></span></label>' +
      "</div></section>" +

      '<section class="result" aria-live="polite"><div class="tiles">' +
      '<div class="tile tile-cost"><span class="tile-label">' + ICONS.coin + 'Custo por unidade</span><b class="num" data-out="unit"></b></div>' +
      '<div class="tile tile-price"><span class="tile-label">' + ICONS.tag + 'Preço sugerido</span><b class="num" data-out="price"></b></div>' +
      '<div class="tile tile-profit"><span class="tile-label">' + ICONS.trend + 'Lucro por unidade</span><b class="num" data-out="profit"></b></div>' +
      '</div><p class="result-sub"><span data-out="price-sub"></span> Lucro na receita inteira: <b class="num" data-out="profit-batch"></b>.</p></section>' +
      '<div data-out="verdict"></div>' +

      '<section class="panel"><h3 class="section-title">De onde vem o custo</h3><table class="breakdown"><tbody data-out="breakdown"></tbody></table>' +
      '<p class="hint">Gás, luz, taxas e valor da sua hora ficam em <a href="#" data-action="go-settings">Ajustes</a>.</p></section>';
    updateEditor();
  }

  function updateEditor() {
    var p = state.products.filter(function (x) { return x.id === view.editing; })[0];
    if (!p) return;
    var s = state.settings, c = calc(p);
    p.items.forEach(function (it, idx) {
      var ing = ingById(it.ingId);
      var el = app.querySelector('[data-cost="' + idx + '"]');
      if (el) el.textContent = ing ? brl(parseNum(it.qty) * costPerBase(ing)) : "";
      var u = app.querySelector('[data-unit="' + idx + '"]');
      if (u) u.textContent = ing ? baseUnit(ing) : "";
    });
    function out(k, html) { var el = app.querySelector('[data-out="' + k + '"]'); if (el) el.innerHTML = html; }
    if (c.invalid) {
      out("price", "—");
      out("price-sub", "A margem mais as taxas passam de 95%. Diminua a margem desejada.");
    } else if (!isFinite(c.unit)) {
      out("price", "—");
      out("price-sub", "Informe quantas unidades a receita rende.");
    } else {
      out("price", brl(c.price));
      out("price-sub", (Math.abs(c.price - c.suggested) > 0.004 ? "Cálculo exato " + brl(c.suggested) + ", arredondado para cima. " : "") +
        "Margem de " + pct(c.margin) + (c.fee ? " já descontando " + pct(c.fee) + " de taxas" : "") + ".");
    }
    out("unit", brl(c.unit));
    out("profit", isFinite(c.profitUnit) ? brl(c.profitUnit) : "—");
    out("profit-batch", isFinite(c.profitBatch) ? brl(c.profitBatch) : "—");

    var v = "";
    if (c.current != null && isFinite(c.price)) {
      var lv = level(c.currentMargin, c.margin), diff = c.price - c.current;
      var msg = lv === "crit"
        ? "Cobrando " + brl(c.current) + " você perde " + brl(-c.currentProfit) + " a cada unidade vendida."
        : "Cobrando " + brl(c.current) + " você lucra " + brl(c.currentProfit) + " por unidade (" + pct(c.currentMargin) + " do preço).";
      var tip = diff > 0.004 ? "Para chegar na margem desejada, aumente " + brl(diff) + "."
        : diff < -0.004 ? "Seu preço está acima do sugerido. Ótimo, se os clientes estão comprando."
        : "Seu preço está igual ao sugerido.";
      v = '<div class="verdict ' + lv + '"><strong>' + levelLabel(c.currentMargin, c.margin) + "</strong><span>" + msg + "</span><span>" + tip + "</span></div>";
    }
    out("verdict", v);

    var rows = [
      ["Ingredientes e embalagens", c.ingCost],
      ["Gás, luz e perdas (" + fmt(parseNum(s.extras), 1) + "%)", c.extras],
      ["Sua mão de obra (" + fmt(parseNum(p.minutes), 0) + " min a " + brl(parseNum(s.hourly)) + "/h)", c.labor]
    ].map(function (r) { return "<tr><td>" + esc(r[0]) + "</td><td>" + brl(r[1]) + "</td></tr>"; }).join("");
    rows += '<tr class="total"><td>Custo da receita inteira</td><td>' + brl(c.batch) + "</td></tr>";
    out("breakdown", rows);
  }

  // ---------- ingredientes ----------
  function usedIn(id) {
    return state.products.filter(function (p) { return p.items.some(function (it) { return it.ingId === id; }); }).length;
  }
  function renderIngredients() {
    var rows = state.ingredients.map(function (i) {
      var armed = view.confirm === "del-ing:" + i.id, n = usedIn(i.id);
      return '<div class="ing" data-ing="' + i.id + '">' +
        '<input class="name" data-f="name" value="' + esc(i.name) + '" placeholder="Nome" aria-label="Nome do ingrediente">' +
        '<span class="suffix"><input inputmode="decimal" data-f="price" value="' + esc(fmt(parseNum(i.price), 2)) + '" aria-label="Preço pago"><em>R$</em></span>' +
        '<input inputmode="decimal" data-f="qty" value="' + esc(fmt(parseNum(i.qty), 3)) + '" aria-label="Quantidade na embalagem">' +
        '<select data-f="unit" aria-label="Unidade">' + Object.keys(UNITS).map(function (u) {
          return '<option value="' + u + '"' + (u === i.unit ? " selected" : "") + ">" + u + "</option>";
        }).join("") + "</select>" +
        '<button class="iconbtn" data-action="del-ing" data-id="' + i.id + '" aria-label="Excluir ingrediente">×</button>' +
        '<span class="unitcost num" data-uc="' + i.id + '">' + unitCostText(i) + "</span>" +
        (armed ? '<div class="row" style="grid-column:1/-1"><span class="hint">' +
          (n ? "Usado em " + n + " produto(s). Ele será removido dessas receitas." : "Excluir este ingrediente?") +
          '</span><button class="btn small danger armed" data-action="del-ing-yes" data-id="' + i.id + '">Excluir</button>' +
          '<button class="btn small" data-action="cancel">Cancelar</button></div>' : "") +
        "</div>";
    }).join("");
    app.innerHTML = exampleNotice() +
      '<div class="row spread"><h2 class="section-title">Ingredientes e embalagens</h2>' +
      '<button class="btn primary" data-action="new-ing">+ Novo ingrediente</button></div>' +
      '<p class="hint">Digite o preço que você pagou e o tamanho da embalagem. Quando o preço mudar no mercado, atualize aqui: todos os produtos são recalculados.</p>' +
      (state.ingredients.length
        ? '<div class="ing-head"><span>Nome</span><span>Preço pago</span><span>Embalagem</span><span>Unidade</span><span></span></div><div class="ings">' + rows + "</div>"
        : '<div class="empty"><p>Nenhum ingrediente cadastrado.<br>Comece pelo que você mais usa: leite condensado, farinha, embalagens…</p></div>');
  }
  function unitCostText(i) {
    var c = costPerBase(i), b = baseUnit(i);
    if (!c) return "Preencha preço e quantidade";
    var n = usedIn(i.id);
    var big = b === "un" ? "" : " · " + brl(c * 1000) + (b === "g" ? "/kg" : "/L");
    return smallBrl(c) + " por " + b + big + (n ? " · usado em " + n + " produto(s)" : "");
  }

  // ---------- cardápio digital ----------
  var menuLink = { loaded: false, slug: null, url: null, base: "", error: "" };
  function apiJson(method, url, body, type) {
    return fetch(url, {
      method: method, credentials: "same-origin", body: body,
      headers: { "Content-Type": type || "application/json", "X-Requested-With": "fetch" }
    }).then(function (r) {
      if (r.status === 401) { location.href = "/entrar"; throw new Error("auth"); }
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(j.error || "Não foi possível concluir (erro " + r.status + ").");
        return j;
      });
    });
  }
  function menuState() {
    if (!state.menu) state.menu = { whatsapp: "", intro: "", delivery: "" };
    return state.menu;
  }
  function pmenu(p) {
    if (!p.menu) p.menu = { show: true, desc: "", photo: null };
    return p.menu;
  }
  function productById(id) { return state.products.filter(function (x) { return x.id === id; })[0]; }
  function shownPrice(p) { var c = calc(p); return c.current != null ? c.current : c.price; }
  function slugify(t) {
    return String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/, "");
  }
  function copyText(text, msgEl) {
    var ok = function () { if (msgEl) msgEl.textContent = "Link copiado."; };
    var fail = function () { if (msgEl) msgEl.textContent = "Selecione o link acima e copie."; };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, fail);
    else fail();
  }
  // QR Code gerado no próprio navegador (biblioteca em /static/vendor)
  function qrCanvas(url, size) {
    if (!window.qrcode) return null;
    var qr = window.qrcode(0, "M");
    qr.addData(url); qr.make();
    var n = qr.getModuleCount(), margin = 4, cell = Math.max(1, Math.floor(size / (n + margin * 2)));
    var px = cell * (n + margin * 2), c = document.createElement("canvas");
    c.width = c.height = px;
    var ctx = c.getContext("2d");
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, px, px);
    ctx.fillStyle = "#1a1a1a";
    for (var r = 0; r < n; r++) for (var col = 0; col < n; col++) {
      if (qr.isDark(r, col)) ctx.fillRect((col + margin) * cell, (r + margin) * cell, cell, cell);
    }
    return c;
  }
  function drawQr(el, url, size) {
    if (!el) return;
    var c = qrCanvas(url, size * 2);
    if (!c) { el.innerHTML = '<p class="hint">QR Code indisponível no momento.</p>'; return; }
    c.style.width = c.style.height = size + "px";
    el.innerHTML = ""; el.appendChild(c);
  }
  function resizeImage(file) {
    return new Promise(function (resolve, reject) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () {
        var max = 800, w = img.naturalWidth, h = img.naturalHeight, k = Math.min(1, max / Math.max(w, h));
        var c = document.createElement("canvas");
        c.width = Math.round(w * k); c.height = Math.round(h * k);
        var ctx = c.getContext("2d");
        ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, c.width, c.height);
        ctx.drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        c.toBlob(function (b) { b ? resolve(b) : reject(new Error("Não consegui ler a imagem.")); }, "image/jpeg", 0.82);
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error("Esse arquivo não parece ser uma imagem.")); };
      img.src = url;
    });
  }

  function renderMenu() {
    var m = menuState();
    if (MODE === "conta" && !menuLink.loaded) {
      app.innerHTML = '<div class="empty"><p>Carregando seu cardápio…</p></div>';
      apiJson("GET", "/api/cardapio").then(function (j) {
        menuLink.loaded = true; menuLink.slug = j.slug; menuLink.url = j.url; menuLink.base = j.base;
        if (view.tab === "cardapio") renderMenu();
      }, function (err) {
        if (err.message === "auth") return;
        menuLink.loaded = true; menuLink.error = "Não foi possível carregar o link agora.";
        if (view.tab === "cardapio") renderMenu();
      });
      return;
    }
    var linkBlock;
    if (MODE !== "conta") {
      linkBlock = '<section class="panel"><h3 class="section-title">Seu link de cardápio</h3>' +
        '<p class="hint">Na conta completa você ganha um link próprio, como <b>/c/doces-da-ana</b>, e um QR Code para imprimir. ' +
        'Seus clientes abrem, escolhem os produtos e o pedido chega pronto no seu WhatsApp.</p></section>';
    } else {
      var suggestion = menuLink.slug || slugify(state.settings.business);
      linkBlock = '<section class="panel"><h3 class="section-title">Seu link de cardápio</h3>' +
        '<label class="field"><span>ENDEREÇO DO CARDÁPIO</span><span class="slug-row"><span class="slug-base">' + esc(menuLink.base) + '</span>' +
        '<input id="m-slug" value="' + esc(suggestion) + '" placeholder="doces-da-ana" autocapitalize="off" autocomplete="off" spellcheck="false"></span></label>' +
        '<div class="row"><button class="btn primary" data-action="save-slug">' + (menuLink.slug ? "Salvar novo link" : "Criar meu link") + '</button>' +
        '<span class="hint" id="slug-msg" role="status">' + esc(menuLink.error) + '</span></div>' +
        (menuLink.url
          ? '<div class="share"><div class="share-url num" id="share-url">' + esc(menuLink.url) + '</div><div class="row">' +
            '<button class="btn small" data-action="copy-link">Copiar link</button>' +
            '<a class="btn small" href="' + esc(menuLink.url) + '" target="_blank" rel="noopener">Abrir cardápio</a>' +
            '<a class="btn small" href="https://wa.me/?text=' + encodeURIComponent("Veja nosso cardápio e faça seu pedido: " + menuLink.url) + '" target="_blank" rel="noopener">Enviar no WhatsApp</a>' +
            '</div><div class="qr-box"><div id="qr" class="qr"></div><div class="qr-side"><b>QR Code do cardápio</b>' +
            '<p class="hint">Imprima e cole no balcão, na embalagem ou no cartão de visita.</p>' +
            '<button class="btn small" data-action="download-qr">Baixar QR Code</button></div></div></div>'
          : "") +
        "</section>";
    }
    var rows = state.products.filter(function (p) { return (p.name || "").trim(); }).map(function (p) {
      var pm = pmenu(p), price = shownPrice(p);
      var photo = productPhoto(p)
        ? '<img class="mi-photo" src="/f/' + esc(pm.photo) + '" alt="">'
        : '<div class="mi-photo mi-empty" aria-hidden="true">' + esc(p.name.trim().charAt(0).toUpperCase()) + "</div>";
      return '<div class="menu-item" data-mp="' + p.id + '">' + photo + '<div class="mi-body">' +
        '<div class="row spread"><label class="check"><input type="checkbox" data-mf="show"' + (pm.show !== false ? " checked" : "") + "> <b>" + esc(p.name) + "</b></label>" +
        '<span class="num mi-price">' + (isFinite(price) && price > 0 ? brl(price) : "sem preço") + "</span></div>" +
        '<input data-mf="desc" value="' + esc(pm.desc) + '" maxlength="300" placeholder="Descrição curta (ex: massa fofinha com recheio de Ninho)" aria-label="Descrição de ' + esc(p.name) + '">' +
        (MODE === "conta"
          ? '<div class="row"><label class="btn small" for="ph-' + p.id + '">' + (pm.photo ? "Trocar foto" : "Adicionar foto") + "</label>" +
            '<input type="file" accept="image/*" id="ph-' + p.id + '" data-photo="' + p.id + '" hidden>' +
            (pm.photo ? '<button class="btn small ghost" data-action="del-photo" data-id="' + p.id + '">Remover foto</button>' : "") +
            '<button class="btn small ghost" data-action="menu-edit" data-id="' + p.id + '">Editar produto</button>' +
            '<span class="hint" data-phmsg="' + p.id + '"></span></div>'
          : '<div class="row"><button class="btn small ghost" data-action="menu-edit" data-id="' + p.id + '">Editar produto</button></div>') +
        "</div></div>";
    }).join("");
    app.innerHTML =
      '<h2 class="section-title">Cardápio digital</h2>' +
      '<p class="hint">Monte um cardápio com fotos e preços. Seus clientes escolhem os produtos e o pedido chega pronto no seu WhatsApp, com o total calculado.</p>' +
      linkBlock +
      '<section class="panel"><h3 class="section-title">Informações do cardápio</h3>' +
      '<label class="field"><span>WHATSAPP PARA RECEBER PEDIDOS</span><input id="m-wa" data-m="whatsapp" inputmode="tel" value="' + esc(m.whatsapp) + '" placeholder="(11) 99999-8888"></label>' +
      '<label class="field"><span>MENSAGEM DE BOAS-VINDAS</span><textarea id="m-intro" data-m="intro" maxlength="500" rows="2" placeholder="Doces artesanais feitos com carinho. Encomendas com 2 dias de antecedência.">' + esc(m.intro) + "</textarea></label>" +
      '<label class="field"><span>ENTREGA E RETIRADA</span><input id="m-delivery" data-m="delivery" maxlength="300" value="' + esc(m.delivery) + '" placeholder="Entregamos no Centro (taxa R$ 5). Retirada na Rua das Flores, 123."></label>' +
      "</section>" +
      '<section class="panel"><div class="row spread"><h3 class="section-title">Produtos no cardápio</h3>' +
      '<button class="btn primary small" data-action="menu-new">+ Novo produto</button></div>' +
      '<p class="hint">Os produtos do cardápio são os mesmos da aba <b>Produtos</b>: todo produto que você cadastra aparece aqui. ' +
      'Desmarque o que não quiser mostrar. O preço é o que você cobra hoje ou, se não informou, o sugerido.</p>' +
      (rows ? '<div class="menu-items">' + rows + "</div>"
        : '<div class="empty"><p>Você ainda não tem produtos.<br>Crie o primeiro e ele aparece aqui no cardápio.</p>' +
          '<button class="btn primary" data-action="menu-new">+ Criar meu primeiro produto</button></div>') +
      "</section>";
    if (menuLink.url) drawQr(document.getElementById("qr"), menuLink.url, 148);
  }

  function uploadPhoto(input) {
    var p = productById(input.dataset.photo), file = input.files[0];
    var msg = app.querySelector('[data-phmsg="' + input.dataset.photo + '"]');
    if (!p || !file) return;
    if (msg) msg.textContent = "Enviando foto…";
    resizeImage(file).then(function (blob) {
      return apiJson("POST", "/api/fotos", blob, "image/jpeg");
    }).then(function (j) {
      var pm = pmenu(p), old = pm.photo;
      pm.photo = j.id; save();
      if (old && !isSamplePhoto(old)) apiJson("DELETE", "/api/fotos/" + old).catch(function () {});
      renderMenu();
    }, function (err) {
      if (err.message !== "auth" && msg) msg.textContent = err.message;
    });
  }

  // ---------- ajustes ----------
  function renderSettings() {
    var s = state.settings, armed = view.confirm === "wipe";
    app.innerHTML =
      '<h2 class="section-title">Ajustes</h2>' +
      '<section class="panel"><label class="field"><span>NOME DO SEU NEGÓCIO</span><input id="s-business" data-s="business" value="' + esc(s.business) + '" placeholder="Ex: Doces da Ana"></label>' +
      '<div class="grid">' +
      settingField("s-margin", "margin", "MARGEM DE LUCRO PADRÃO", "%", "Quanto do preço é lucro. Doces costumam usar de 30% a 50%.") +
      settingField("s-fee", "fee", "TAXAS SOBRE A VENDA", "%", "Maquininha, iFood, nota fiscal. Some tudo.") +
      settingField("s-extras", "extras", "GÁS, LUZ E PERDAS", "%", "Adicionado sobre o custo dos ingredientes. 10% é um bom começo.") +
      settingField("s-hourly", "hourly", "VALOR DA SUA HORA", "R$", "Quanto você quer ganhar por hora de trabalho. Deixe 0 para ignorar.") +
      '<label class="field"><span>ARREDONDAR PREÇO PARA CIMA</span><select id="s-round" data-s="round">' +
      [[0, "Não arredondar"], [0.1, "De R$ 0,10 em R$ 0,10"], [0.5, "De R$ 0,50 em R$ 0,50"], [1, "Para o real inteiro"]].map(function (o) {
        return '<option value="' + o[0] + '"' + (parseNum(s.round) === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
      }).join("") + "</select></label>" +
      "</div></section>" +

      '<section class="panel"><h3 class="section-title">Backup dos seus dados</h3>' +
      '<p class="hint">' + (MODE === "conta" ? "Seus dados já ficam salvos na nuvem. Se quiser uma cópia extra, gere o backup e guarde." : "Na demonstração os dados ficam só neste aparelho.") + '</p>' +
      '<div class="row"><button class="btn" data-action="export">Gerar backup</button>' +
      '<button class="btn" data-action="download">Baixar arquivo</button>' +
      '<label class="btn" for="import-file">Abrir arquivo de backup</label><input type="file" id="import-file" accept=".json,application/json,text/plain" hidden></div>' +
      '<textarea id="backup-text" class="backup" placeholder="Cole aqui um backup para restaurar, ou toque em Gerar backup."></textarea>' +
      '<div class="row"><button class="btn small" data-action="copy">Copiar texto</button><button class="btn small" data-action="restore">Restaurar do texto colado</button>' +
      '<span class="hint" id="backup-msg" role="status"></span></div></section>' +

      '<section class="panel"><h3 class="section-title">Recomeçar</h3><div class="row">' +
      '<button class="btn small" data-action="load-sample">Carregar exemplos</button>' +
      '<button class="btn small danger' + (armed ? " armed" : "") + '" data-action="wipe">' + (armed ? "Toque de novo para apagar tudo" : "Apagar todos os dados") + "</button>" +
      "</div></section>";
  }
  function settingField(id, key, label, unit, hint) {
    return '<label class="field"><span>' + label + '</span><span class="suffix"><input id="' + id + '" inputmode="decimal" data-s="' + key +
      '" value="' + esc(fmt(parseNum(state.settings[key]), 2)) + '"><em>' + unit + "</em></span><small class=\"hint\">" + hint + "</small></label>";
  }
  function backupMsg(t) { var el = document.getElementById("backup-msg"); if (el) el.textContent = t; }
  function restoreFrom(text) {
    try {
      var d = JSON.parse(text);
      if (!d || d.v !== 1 || !Array.isArray(d.products) || !Array.isArray(d.ingredients) || !d.settings) throw new Error();
      state = d; save(); render(); backupMsg("Backup restaurado.");
    } catch (e) { backupMsg("Esse texto não é um backup válido do Precifica Fácil."); }
  }

  // ---------- eventos ----------
  document.querySelector("nav.tabs").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-tab]");
    if (b) setTab(b.dataset.tab);
  });

  app.addEventListener("click", function (e) {
    var t = e.target.closest("[data-action]");
    if (!t) return;
    var a = t.dataset.action;
    if (t.tagName === "A") e.preventDefault();
    if (a !== "del-product" && a !== "wipe" && a !== "del-ing") view.confirm = null;
    var p = state.products.filter(function (x) { return x.id === view.editing; })[0];

    switch (a) {
      case "start-blank":
        state = blank(); save(); setTab("ingredientes"); return;
      case "load-sample":
        state = sample(); save(); setTab("produtos"); return;
      case "go-ings": setTab("ingredientes"); return;
      case "go-settings": setTab("ajustes"); return;
      case "menu-edit":
        setTab("produtos"); view.editing = t.dataset.id; render(); window.scrollTo(0, 0); return;
      case "menu-new":
        setTab("produtos");
        /* falls through */
      case "new-product":
        var np = { id: uid(), name: "", yield: 1, minutes: 0, margin: null, current: 0, items: [{ ingId: "", qty: 0 }] };
        state.products.unshift(np); state.example = false; save();
        view.editing = np.id; render();
        var n = document.getElementById("p-name"); if (n) n.focus();
        return;
      case "edit": view.editing = t.dataset.id; render(); window.scrollTo(0, 0); return;
      case "back":
        state.products = state.products.filter(function (x) { return x.name || x.items.some(function (i) { return i.ingId; }); });
        save(); view.editing = null; render(); return;
      case "dup-product":
        var copy = JSON.parse(JSON.stringify(p)); copy.id = uid(); copy.name = p.name + " (cópia)";
        state.products.unshift(copy); save(); view.editing = copy.id; render(); window.scrollTo(0, 0); return;
      case "del-product":
        if (view.confirm === "del-product") {
          state.products = state.products.filter(function (x) { return x.id !== p.id; });
          save(); view.confirm = null; view.editing = null; render();
        } else { view.confirm = "del-product"; render(); }
        return;
      case "add-item":
        p.items.push({ ingId: "", qty: 0 }); save(); render();
        var sels = app.querySelectorAll(".item select"); if (sels.length) sels[sels.length - 1].focus();
        return;
      case "del-item":
        p.items.splice(+t.dataset.idx, 1); save(); render(); return;
      case "new-ing":
        var ni = { id: uid(), name: "", price: 0, qty: 1, unit: "g" };
        state.ingredients.unshift(ni); state.example = false; save(); render();
        var f = app.querySelector('[data-ing="' + ni.id + '"] input'); if (f) f.focus();
        return;
      case "del-ing":
        view.confirm = "del-ing:" + t.dataset.id; render(); return;
      case "del-ing-yes":
        var did = t.dataset.id;
        state.ingredients = state.ingredients.filter(function (i) { return i.id !== did; });
        state.products.forEach(function (pp) { pp.items = pp.items.filter(function (it) { return it.ingId !== did; }); });
        save(); view.confirm = null; render(); return;
      case "cancel": render(); return;
      case "wipe":
        if (view.confirm === "wipe") { state = blank(); save(); view.confirm = null; setTab("produtos"); }
        else { view.confirm = "wipe"; render(); }
        return;
      case "export":
        document.getElementById("backup-text").value = JSON.stringify(state);
        backupMsg("Backup gerado. Copie e guarde em lugar seguro."); return;
      case "copy":
        var ta = document.getElementById("backup-text");
        if (!ta.value) ta.value = JSON.stringify(state);
        var done = function () { backupMsg("Copiado."); };
        var fallback = function () { ta.focus(); ta.select(); backupMsg("Texto selecionado. Use Copiar do seu aparelho."); };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(ta.value).then(done, fallback);
        else fallback();
        return;
      case "download":
        try {
          var blob = new Blob([JSON.stringify(state, null, 1)], { type: "application/json" });
          var link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = "precifica-backup-" + new Date().toISOString().slice(0, 10) + ".json";
          document.body.appendChild(link); link.click(); link.remove();
          backupMsg("Se o download não começar, use Gerar backup e Copiar texto.");
        } catch (err) { backupMsg("Download indisponível aqui. Use Gerar backup e Copiar texto."); }
        return;
      case "reload": location.reload(); return;
      case "save-slug":
        var slugIn = document.getElementById("m-slug"), slugMsg = document.getElementById("slug-msg");
        var val = slugify(slugIn.value); slugIn.value = val;
        slugMsg.textContent = "Salvando…";
        apiJson("PUT", "/api/cardapio", JSON.stringify({ slug: val })).then(function (j) {
          menuLink.slug = j.slug; menuLink.url = j.url; menuLink.error = "";
          renderMenu();
          var m2 = document.getElementById("slug-msg"); if (m2) m2.textContent = "Link salvo. Já pode compartilhar!";
        }, function (err) { if (err.message !== "auth") slugMsg.textContent = err.message; });
        return;
      case "copy-link":
        copyText(menuLink.url, document.getElementById("slug-msg")); return;
      case "download-qr":
        var canvas = qrCanvas(menuLink.url, 720);
        if (canvas) {
          var a2 = document.createElement("a");
          a2.href = canvas.toDataURL("image/png");
          a2.download = "qrcode-cardapio-" + (menuLink.slug || "precifica") + ".png";
          document.body.appendChild(a2); a2.click(); a2.remove();
        }
        return;
      case "del-photo":
        var pp = productById(t.dataset.id), oldPhoto = pp && pmenu(pp).photo;
        if (oldPhoto) { pmenu(pp).photo = null; save(); if (!isSamplePhoto(oldPhoto)) apiJson("DELETE", "/api/fotos/" + oldPhoto).catch(function () {}); }
        renderMenu(); return;
      case "restore":
        restoreFrom(document.getElementById("backup-text").value); return;
    }
  });

  app.addEventListener("input", function (e) {
    var t = e.target;
    if (t.dataset.m) { menuState()[t.dataset.m] = t.value; save(); return; }
    if (t.dataset.mf) {
      var mrow = t.closest("[data-mp]"), mp = productById(mrow.dataset.mp);
      if (t.dataset.mf === "show") pmenu(mp).show = t.checked; else pmenu(mp).desc = t.value;
      save(); return;
    }
    var p = state.products.filter(function (x) { return x.id === view.editing; })[0];
    if (t.dataset.p && p) {
      var k = t.dataset.p;
      if (k === "name") p.name = t.value;
      else if (k === "margin") p.margin = t.value.trim() === "" ? null : parseNum(t.value);
      else p[k] = parseNum(t.value);
      state.example = false; save(); updateEditor(); return;
    }
    if (t.dataset.item != null && p) {
      var it = p.items[+t.dataset.item];
      if (t.dataset.field === "ingId") it.ingId = t.value; else it.qty = parseNum(t.value);
      save(); updateEditor(); return;
    }
    var row = t.closest("[data-ing]");
    if (row && t.dataset.f) {
      var ing = ingById(row.dataset.ing);
      ing[t.dataset.f] = t.dataset.f === "name" || t.dataset.f === "unit" ? t.value : parseNum(t.value);
      save();
      var uc = row.querySelector("[data-uc]"); if (uc) uc.textContent = unitCostText(ing);
      return;
    }
    if (t.dataset.s) {
      state.settings[t.dataset.s] = t.dataset.s === "business" ? t.value : parseNum(t.value);
      document.getElementById("bizName").textContent = state.settings.business || "";
      save();
    }
  });
  app.addEventListener("change", function (e) {
    if (e.target.dataset.photo) { uploadPhoto(e.target); return; }
    if (e.target.id === "import-file" && e.target.files[0]) {
      var r = new FileReader();
      r.onload = function () { restoreFrom(String(r.result)); };
      r.readAsText(e.target.files[0]);
    }
  });

  function boot() {
    if (MODE === "demo") { state = loadLocal(); render(); return; }
    app.innerHTML = '<div class="empty"><p>Carregando seus dados…</p></div>';
    api("GET").then(function (j) {
      if (j.data && j.data.v === 1) { state = j.data; render(); setStatus("Salvo na nuvem", "ok"); }
      else { state = sample(); render(); save(); }
    }, function (err) {
      if (err.message === "auth") return;
      app.innerHTML = '<div class="empty"><p>Não foi possível carregar seus dados. Confira sua internet.</p>' +
        '<button class="btn" data-action="reload">Tentar de novo</button></div>';
    });
  }
  boot();
})();
