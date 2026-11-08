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
    else renderSettings();
  }

  function exampleNotice() {
    if (!state.example) return "";
    return '<div class="notice"><span><b>Estes são dados de exemplo.</b> Edite à vontade ou comece com a sua lista.</span>' +
      '<button class="btn small" data-action="start-blank">Começar do zero</button></div>';
  }

  // ---------- produtos ----------
  function renderProducts() {
    var list = state.products.map(function (p) {
      var c = calc(p);
      var chip;
      if (c.current != null) {
        chip = '<span class="chip ' + level(c.currentMargin, c.margin) + '">' + levelLabel(c.currentMargin, c.margin) + " · " + pct(c.currentMargin) + "</span>";
      } else {
        chip = '<span class="chip neutral">Sem preço definido</span>';
      }
      var priceLine = c.current != null
        ? "Você cobra " + brl(c.current) + " · sugerido " + brl(c.price)
        : "Preço sugerido";
      return '<button class="product" data-action="edit" data-id="' + p.id + '">' +
        '<span class="p-name">' + esc(p.name || "Sem nome") + "</span>" +
        '<span class="p-price"><strong class="num">' + brl(c.current != null ? c.current : c.price) + "</strong>" + chip + "</span>" +
        '<span class="p-meta num">Rende ' + fmt(parseNum(p.yield), 0) + " un · custo " + brl(c.unit) + "/un · " + priceLine + "</span>" +
        "</button>";
    }).join("");
    app.innerHTML = exampleNotice() +
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

      '<section class="result" aria-live="polite">' +
      '<div><div class="label">Preço sugerido por unidade</div><div class="big num" data-out="price"></div><div class="sub" data-out="price-sub"></div></div>' +
      '<div class="result-stats">' +
      '<div><span class="label">Custo por unidade</span><b class="num" data-out="unit"></b></div>' +
      '<div><span class="label">Lucro por unidade</span><b class="num" data-out="profit"></b></div>' +
      '<div><span class="label">Lucro na receita</span><b class="num" data-out="profit-batch"></b></div>' +
      "</div></section>" +
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
      case "restore":
        restoreFrom(document.getElementById("backup-text").value); return;
    }
  });

  app.addEventListener("input", function (e) {
    var t = e.target;
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
