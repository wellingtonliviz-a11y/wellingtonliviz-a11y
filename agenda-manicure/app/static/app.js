(function () {
  "use strict";
  var KEY = "precifica-manicure:v1";
  var UNITS = { g: ["g", 1], kg: ["g", 1000], ml: ["ml", 1], L: ["ml", 1000], un: ["un", 1] };
  var WD = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
  var WD_FULL = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];

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
  function duration(min) {
    min = Math.round(parseNum(min));
    if (min < 60) return min + " min";
    var h = Math.floor(min / 60), m = min % 60;
    return h + "h" + (m ? (m < 10 ? "0" : "") + m : "");
  }
  // datas no horário do aparelho, no formato AAAA-MM-DD
  function isoOf(d) { return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
  function dateOf(iso) { var p = iso.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function addDays(iso, n) { var d = dateOf(iso); d.setDate(d.getDate() + n); return isoOf(d); }
  function todayIso() { return isoOf(new Date()); }
  function dm(iso) { var d = dateOf(iso); return ("0" + d.getDate()).slice(-2) + "/" + ("0" + (d.getMonth() + 1)).slice(-2); }
  function wd(iso) { return WD[dateOf(iso).getDay()]; }
  function dayLabel(iso) {
    var t = todayIso();
    var rel = iso === t ? "Hoje" : iso === addDays(t, 1) ? "Amanhã" : iso === addDays(t, -1) ? "Ontem" : "";
    return (rel ? rel + " · " : "") + WD_FULL[dateOf(iso).getDay()] + ", " + dm(iso);
  }
  function hm(t) { var m = /^(\d{1,2}):(\d{2})$/.exec(String(t || "").trim()); return m ? +m[1] * 60 + +m[2] : null; }
  function fmtHm(min) { return ("0" + Math.floor(min / 60)).slice(-2) + ":" + ("0" + (min % 60)).slice(-2); }
  function waDigits(raw) {
    var d = String(raw || "").replace(/\D/g, "");
    if (d.length === 10 || d.length === 11) d = "55" + d;
    return d.length >= 12 && d.length <= 15 ? d : "";
  }
  function firstName(n) { return String(n || "").trim().split(/\s+/)[0] || ""; }

  // ---------- exemplos por segmento ----------
  // material: [nome, preço pago, tamanho da embalagem, unidade]
  // serviço: [nome, duração (min), preço atual, margem (null = padrão), materiais [[material, qtd por atendimento]], descrição]
  var SEGMENTS = {
    manicure: { label: "Manicure e pedicure", business: "Espaço da Carol", margin: 40, round: 1,
      ing: [["Esmalte cremoso", 7.9, 8, "ml"], ["Base fortalecedora", 9.9, 8, "ml"], ["Extra brilho (top coat)", 9.9, 8, "ml"],
            ["Removedor de esmalte", 14.9, 500, "ml"], ["Algodão", 6.5, 100, "g"], ["Lixa de unha descartável", 18, 50, "un"],
            ["Palito de laranjeira", 6, 100, "un"], ["Luva descartável", 32, 100, "un"], ["Amolecedor de cutícula", 16, 500, "ml"],
            ["Creme hidratante", 29.9, 1, "L"], ["Toalha descartável", 22, 100, "un"], ["Lixa para pés descartável", 25, 50, "un"],
            ["Esfoliante para pés", 24.9, 500, "g"], ["Óleo secante", 19.9, 100, "ml"]],
      prod: [["Mão", 45, 30, null, [["Esmalte cremoso", 0.6], ["Base fortalecedora", 0.4], ["Extra brilho (top coat)", 0.4], ["Removedor de esmalte", 8],
              ["Algodão", 2], ["Lixa de unha descartável", 1], ["Palito de laranjeira", 1], ["Luva descartável", 2], ["Amolecedor de cutícula", 3],
              ["Toalha descartável", 1], ["Óleo secante", 1]], "Cutilagem caprichada e esmaltação na cor que você escolher"],
             ["Pé", 50, 35, null, [["Esmalte cremoso", 0.8], ["Base fortalecedora", 0.5], ["Extra brilho (top coat)", 0.5], ["Removedor de esmalte", 10],
              ["Algodão", 3], ["Lixa para pés descartável", 1], ["Palito de laranjeira", 1], ["Luva descartável", 2], ["Amolecedor de cutícula", 4],
              ["Creme hidratante", 5], ["Toalha descartável", 1], ["Óleo secante", 1]], "Cutilagem, lixamento e esmaltação dos pés"],
             ["Pé e mão", 90, 60, null, [["Esmalte cremoso", 1.4], ["Base fortalecedora", 0.9], ["Extra brilho (top coat)", 0.9], ["Removedor de esmalte", 18],
              ["Algodão", 5], ["Lixa de unha descartável", 1], ["Lixa para pés descartável", 1], ["Palito de laranjeira", 2], ["Luva descartável", 2],
              ["Amolecedor de cutícula", 7], ["Creme hidratante", 5], ["Toalha descartável", 2], ["Óleo secante", 2]], "O combo completo, com desconto"],
             ["Spa dos pés", 60, 70, null, [["Esfoliante para pés", 20], ["Creme hidratante", 15], ["Lixa para pés descartável", 1], ["Luva descartável", 2],
              ["Toalha descartável", 2]], "Esfoliação, hidratação profunda e massagem relaxante"]] },
    gel: { label: "Alongamento e gel", business: "Studio Nails da Bia", margin: 45, round: 5,
      ing: [["Gel construtor", 45, 15, "g"], ["Esmalte em gel", 22, 10, "ml"], ["Base em gel", 25, 10, "ml"], ["Top coat em gel", 25, 10, "ml"],
            ["Primer ácido", 30, 10, "ml"], ["Prep desidratador", 20, 10, "ml"], ["Molde de papel", 25, 500, "un"],
            ["Lixa 100/180", 18, 50, "un"], ["Bloco polidor", 15, 20, "un"], ["Álcool isopropílico", 35, 1, "L"],
            ["Luva descartável", 32, 100, "un"], ["Toalha descartável", 22, 100, "un"], ["Removedor de gel", 29.9, 500, "ml"]],
      prod: [["Alongamento em gel (aplicação)", 150, 150, null, [["Gel construtor", 4], ["Base em gel", 0.4], ["Top coat em gel", 0.4], ["Esmalte em gel", 0.5],
              ["Primer ácido", 0.2], ["Prep desidratador", 0.2], ["Molde de papel", 10], ["Lixa 100/180", 2], ["Bloco polidor", 1],
              ["Álcool isopropílico", 10], ["Luva descartável", 2], ["Toalha descartável", 2]], "Unhas alongadas no molde, formato e tamanho que você quiser"],
             ["Manutenção do alongamento", 100, 100, null, [["Gel construtor", 2], ["Top coat em gel", 0.4], ["Esmalte em gel", 0.5], ["Primer ácido", 0.2],
              ["Prep desidratador", 0.2], ["Lixa 100/180", 2], ["Bloco polidor", 1], ["Álcool isopropílico", 10], ["Luva descartável", 2],
              ["Toalha descartável", 1]], "Manutenção a cada 15 a 20 dias"],
             ["Esmaltação em gel", 60, 60, null, [["Base em gel", 0.4], ["Esmalte em gel", 0.6], ["Top coat em gel", 0.4], ["Prep desidratador", 0.2],
              ["Bloco polidor", 1], ["Álcool isopropílico", 5], ["Luva descartável", 2], ["Toalha descartável", 1]], "Brilho e cor por até 3 semanas"],
             ["Banho de gel", 75, 80, null, [["Gel construtor", 2], ["Base em gel", 0.4], ["Top coat em gel", 0.4], ["Primer ácido", 0.2],
              ["Prep desidratador", 0.2], ["Lixa 100/180", 1], ["Bloco polidor", 1], ["Álcool isopropílico", 5], ["Luva descartável", 2],
              ["Toalha descartável", 1]], "Camada de gel na unha natural, para fortalecer"]] }
  };
  function defaultAgenda() {
    var week = [];
    for (var d = 0; d < 7; d++) week.push({ on: d >= 1, start: "09:00", end: d === 6 ? "14:00" : "18:00" });
    return { whatsapp: "", intro: "", address: "", week: week, lunch: { on: true, start: "12:00", end: "13:00" },
             step: 30, notice: 2, daysAhead: 30, autoConfirm: false, notifyEmail: true };
  }
  function sampleFor(seg, business) {
    var S = SEGMENTS[seg] || SEGMENTS.manicure;
    var ing = S.ing.map(function (r) { return { id: uid(), name: r[0], price: r[1], qty: r[2], unit: r[3] }; });
    function id(name) { return ing.filter(function (i) { return i.name === name; })[0].id; }
    var st = {
      v: 1, example: true, onboarded: false,
      settings: { business: business == null ? "" : business, segment: SEGMENTS[seg] ? seg : "manicure",
                  margin: S.margin, fee: 4, extras: 10, hourly: 20, round: S.round },
      ingredients: ing,
      products: S.prod.map(function (r) {
        return { id: uid(), name: r[0], yield: 1, minutes: r[1], current: r[2], margin: r[3],
                 items: r[4].map(function (it) { return { ingId: id(it[0]), qty: it[1] }; }),
                 menu: { show: true, desc: r[5], photo: null } };
      }),
      agenda: defaultAgenda()
    };
    if (MODE === "demo") st.appts = demoAppts(st);
    return st;
  }
  function demoAppts(st) {
    var t = todayIso(), p = st.products, list = [];
    function add(day, time, prod, name, phone, status, source) {
      list.push({ id: uid(), day: day, time: time, start: hm(time), duration: prod.minutes, end: fmtHm(hm(time) + prod.minutes),
                  status: status, source: source, client_name: name, client_phone: phone, wa: waDigits(phone),
                  services: prod.name, price: parseNum(prod.current), note: "" });
    }
    add(t, "09:00", p[0], "Juliana Alves", "(11) 98888-1111", "confirmado", "manual");
    add(t, "10:00", p[2] || p[0], "Fernanda Rocha", "(11) 97777-2222", "pendente", "online");
    add(t, "14:00", p[1] || p[0], "Patrícia Lima", "(11) 96666-3333", "confirmado", "online");
    add(addDays(t, 1), "09:30", p[0], "Camila Souza", "(11) 95555-4444", "pendente", "online");
    add(addDays(t, 1), "15:00", p[3] || p[0], "Renata Dias", "(11) 94444-5555", "confirmado", "manual");
    return list;
  }
  function sample() { return sampleFor("manicure", MODE === "demo" ? SEGMENTS.manicure.business : ""); }
  function blank() {
    return { v: 1, example: false,
      settings: { business: "", margin: 40, fee: 0, extras: 10, hourly: 0, round: 1 },
      ingredients: [], products: [], agenda: defaultAgenda() };
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
  function apiJson(method, url, body, type) {
    return fetch(url, {
      method: method, credentials: "same-origin", body: body,
      headers: { "Content-Type": type || "application/json", "X-Requested-With": "fetch" }
    }).then(function (r) {
      if (r.status === 401) { location.href = "/entrar"; throw new Error("auth"); }
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) { var e = new Error(j.error || "Não foi possível concluir (erro " + r.status + ")."); e.conflict = !!j.conflict; throw e; }
        return j;
      });
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
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* ignora */ }
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
  function agendaCfg() {
    if (!state.agenda) state.agenda = defaultAgenda();
    var a = state.agenda, def = defaultAgenda();
    Object.keys(def).forEach(function (k) { if (a[k] == null) a[k] = def[k]; });
    return a;
  }

  // ---------- cálculo do preço do serviço ----------
  function calc(p) {
    var s = state.settings;
    var ingCost = 0;
    p.items.forEach(function (it) {
      var ing = ingById(it.ingId);
      if (ing) ingCost += parseNum(it.qty) * costPerBase(ing);
    });
    var extras = ingCost * parseNum(s.extras) / 100;
    var labor = parseNum(p.minutes) / 60 * parseNum(s.hourly);
    var unit = ingCost + extras + labor;
    var m = (p.margin == null || p.margin === "" ? parseNum(s.margin) : parseNum(p.margin)) / 100;
    var f = parseNum(s.fee) / 100;
    var denom = 1 - m - f;
    var suggested = denom > 0.05 ? unit / denom : NaN;
    var step = parseNum(s.round);
    var rounded = isFinite(suggested) && step > 0 ? Math.ceil(suggested / step - 1e-9) * step : suggested;
    var hours = parseNum(p.minutes) / 60;
    var out = {
      ingCost: ingCost, extras: extras, labor: labor, unit: unit,
      margin: m, fee: f, suggested: suggested, price: rounded,
      profitUnit: rounded * (1 - f) - unit, invalid: denom <= 0.05
    };
    // quanto sobra por hora de cadeira (seu trabalho + lucro), depois de materiais e taxas
    out.perHour = hours > 0 ? (rounded * (1 - f) - ingCost - extras) / hours : NaN;
    var cur = parseNum(p.current);
    if (cur > 0) {
      out.current = cur;
      out.currentProfit = cur * (1 - f) - unit;
      out.currentMargin = out.currentProfit / cur;
      out.currentPerHour = hours > 0 ? (cur * (1 - f) - ingCost - extras) / hours : NaN;
    }
    return out;
  }
  function level(m, goal) { return m < 0 ? "crit" : m < goal - 0.005 ? "warn" : "good"; }
  function levelLabel(m, goal) { return m < 0 ? "Prejuízo" : m < goal - 0.005 ? "Abaixo da meta" : "Na meta"; }
  function shownPrice(p) { var c = calc(p); return c.current != null ? c.current : c.price; }

  // ---------- navegação ----------
  var view = { tab: "agenda", editing: null, confirm: null, day: todayIso(), form: null };
  var app = document.getElementById("app");

  function setTab(tab) {
    if (!state) return;
    view.tab = tab; view.editing = null; view.confirm = null; view.form = null;
    document.querySelectorAll("nav.tabs button").forEach(function (b) {
      b.setAttribute("aria-selected", String(b.dataset.tab === tab));
    });
    render();
    window.scrollTo(0, 0);
  }

  function render() {
    document.getElementById("bizName").textContent = state.settings.business || "";
    if (view.tab === "agenda") renderAgenda();
    else if (view.tab === "produtos") view.editing ? renderEditor() : renderProducts();
    else if (view.tab === "ingredientes") renderIngredients();
    else if (view.tab === "link") renderLink();
    else renderSettings();
  }

  function exampleNotice() {
    var out = "";
    if (MODE === "conta" && !(state.settings.business || "").trim()) {
      out += '<div class="notice"><span><b>Coloque o nome do seu espaço</b> para ele aparecer no sistema e na sua página de agendamento.</span>' +
        '<button class="btn small" data-action="go-settings">Ir para Ajustes</button></div>';
    }
    if (state.example) {
      out += '<div class="notice"><span><b>Estes serviços e materiais são exemplos.</b> Edite à vontade ou comece com a sua lista.</span>' +
        '<button class="btn small" data-action="start-blank">Começar do zero</button></div>';
    }
    return out;
  }

  var ICONS = {
    coin: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v10M14.8 9.2c-.5-.8-1.5-1.2-2.8-1.2-1.6 0-2.8.8-2.8 2s1.2 1.7 2.8 2 2.8.8 2.8 2-1.2 2-2.8 2c-1.3 0-2.4-.5-2.9-1.3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    tag: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5V4.5A1.5 1.5 0 0 1 4.5 3h7l9.5 9.5-8.5 8.5L3 11.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><circle cx="8" cy="8" r="1.6" fill="currentColor"/></svg>',
    trend: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17l6-6 4 4 8-8M15 7h6v6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    cal: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15.5" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3.5 10h17M8 3v4M16 3v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
  };

  // ---------- agenda: armazenamento (nuvem na conta, aparelho na demonstração) ----------
  var appts = { byId: {}, loaded: {}, loading: false, error: "" };
  function storeList() { return Object.keys(appts.byId).map(function (k) { return appts.byId[k]; }); }
  function put(item) { appts.byId[item.id] = item; return item; }
  function overlapsLocal(day, start, dur, ignoreId) {
    return storeList().some(function (a) {
      return a.id !== ignoreId && a.day === day && a.status !== "cancelado" && start < a.start + a.duration && a.start < start + dur;
    });
  }
  function localItem(body, old) {
    var it = old ? JSON.parse(JSON.stringify(old)) : { id: uid(), source: "manual", status: "confirmado" };
    ["day", "status", "client_name", "client_phone", "services", "note"].forEach(function (k) { if (body[k] != null) it[k] = body[k]; });
    if (body.time != null) { it.time = body.time; it.start = hm(body.time); }
    if (body.duration != null) it.duration = Math.round(parseNum(body.duration));
    if (body.price != null) it.price = parseNum(body.price);
    if (it.status === "bloqueio") { it.client_name = ""; it.client_phone = ""; it.price = 0; }
    it.end = fmtHm(it.start + it.duration); it.wa = waDigits(it.client_phone);
    return it;
  }
  function syncDemo() { state.appts = storeList(); save(); }
  var store = {
    ensure: function (from, to) {
      if (MODE !== "conta") {
        if (!appts.demoLoaded) { (state.appts || []).forEach(put); appts.demoLoaded = true; }
        return Promise.resolve(false);
      }
      var missing = false;
      for (var d = from; d <= to; d = addDays(d, 1)) if (!appts.loaded[d]) { missing = true; break; }
      if (!missing) return Promise.resolve(false);
      return apiJson("GET", "/api/agendamentos?de=" + from + "&ate=" + to).then(function (j) {
        storeList().forEach(function (a) { if (a.day >= from && a.day <= to) delete appts.byId[a.id]; });
        j.items.forEach(put);
        for (var d2 = from; d2 <= to; d2 = addDays(d2, 1)) appts.loaded[d2] = true;
        return true;
      });
    },
    create: function (body) {
      if (MODE !== "conta") {
        if (!body.force && overlapsLocal(body.day, hm(body.time), parseNum(body.duration))) {
          var e = new Error("Já existe outro horário nesse período."); e.conflict = true; return Promise.reject(e);
        }
        var it = put(localItem(body)); syncDemo(); return Promise.resolve(it);
      }
      return apiJson("POST", "/api/agendamentos", JSON.stringify(body)).then(function (j) { return put(j.item); });
    },
    update: function (id, body) {
      if (MODE !== "conta") {
        var old = appts.byId[id], it = localItem(body, old);
        var check = it.status !== "cancelado" && (body.day != null || body.time != null || body.duration != null || old.status === "cancelado");
        if (check && !body.force && overlapsLocal(it.day, it.start, it.duration, id)) {
          var e = new Error("Já existe outro horário nesse período."); e.conflict = true; return Promise.reject(e);
        }
        put(it); syncDemo(); return Promise.resolve(it);
      }
      return apiJson("PATCH", "/api/agendamentos/" + id, JSON.stringify(body)).then(function (j) { return put(j.item); });
    },
    remove: function (id) {
      if (MODE !== "conta") { delete appts.byId[id]; syncDemo(); return Promise.resolve(); }
      return apiJson("DELETE", "/api/agendamentos/" + id).then(function () { delete appts.byId[id]; });
    }
  };

  // ---------- agenda: tela ----------
  var STATUS = {
    pendente: ["warn", "Aguardando confirmação"], confirmado: ["good", "Confirmado"], concluido: ["neutral", "Concluído"],
    cancelado: ["crit", "Cancelado"], bloqueio: ["neutral", "Horário bloqueado"]
  };
  function counts(a) { return a.status !== "cancelado" && a.status !== "bloqueio"; }
  function dayItems(day) {
    return storeList().filter(function (a) { return a.day === day; }).sort(function (x, y) { return x.start - y.start; });
  }
  function bizName() { return (state.settings.business || "").trim(); }
  function waMessage(a) {
    var who = firstName(a.client_name), biz = bizName();
    var when = wd(a.day) + ", " + dm(a.day) + " às " + a.time;
    if (a.status === "cancelado") {
      return "Olá" + (who ? ", " + who : "") + "! Precisei desmarcar o seu horário de " + when + ". Podemos remarcar?" +
        (linkInfo.url ? " Escolha um novo horário aqui: " + linkInfo.url : "");
    }
    return "Olá" + (who ? ", " + who : "") + "! Seu horário" + (biz ? " no " + biz : "") + " está confirmado: " + when +
      " (" + a.services + "). Qualquer imprevisto, me avise por aqui. Até lá!";
  }
  function apptCard(a) {
    var st = STATUS[a.status] || STATUS.confirmado, past = a.day < todayIso();
    var head = '<div class="ap-time num"><b>' + esc(a.time) + "</b><span>" + esc(a.end) + "</span></div>";
    var actions = [];
    if (a.status === "pendente") {
      actions.push('<button class="btn small primary" data-action="ap-status" data-status="confirmado" data-id="' + a.id + '">Confirmar</button>');
      actions.push('<button class="btn small" data-action="ap-status" data-status="cancelado" data-id="' + a.id + '">Recusar</button>');
    } else if (a.status === "confirmado") {
      actions.push('<button class="btn small" data-action="ap-status" data-status="concluido" data-id="' + a.id + '">Concluído</button>');
      actions.push('<button class="btn small" data-action="ap-status" data-status="cancelado" data-id="' + a.id + '">Cancelar</button>');
    } else if (a.status === "cancelado" || a.status === "concluido") {
      actions.push('<button class="btn small" data-action="ap-status" data-status="confirmado" data-id="' + a.id + '">' + (a.status === "cancelado" ? "Reabrir" : "Desfazer") + "</button>");
    }
    if (a.wa && a.status !== "bloqueio" && !(past && a.status === "concluido")) {
      actions.push('<a class="btn small wa" href="https://wa.me/' + esc(a.wa) + "?text=" + encodeURIComponent(waMessage(a)) + '" target="_blank" rel="noopener">WhatsApp</a>');
    }
    if (a.status !== "concluido") actions.push('<button class="btn small ghost" data-action="ap-edit" data-id="' + a.id + '">Editar</button>');
    var armed = view.confirm === "del-ap:" + a.id;
    if (a.status === "cancelado" || a.status === "bloqueio") {
      actions.push('<button class="btn small ghost danger' + (armed ? " armed" : "") + '" data-action="ap-del" data-id="' + a.id + '">' + (armed ? "Toque de novo para excluir" : "Excluir") + "</button>");
    }
    var body = a.status === "bloqueio"
      ? '<span class="ap-name">Horário bloqueado</span>' + (a.note ? '<span class="ap-meta">' + esc(a.note) + "</span>" : "")
      : '<span class="ap-name">' + esc(a.client_name || "Cliente") + "</span>" +
        '<span class="ap-meta">' + esc(a.services || "Atendimento") + " · " + duration(a.duration) + (a.price ? " · <b class=\"num\">" + brl(a.price) + "</b>" : "") + "</span>" +
        (a.note ? '<span class="ap-meta">“' + esc(a.note) + "”</span>" : "");
    return '<article class="appt s-' + esc(a.status) + '">' + head + '<div class="ap-body"><div class="row ap-tags">' +
      '<span class="chip ' + st[0] + '">' + st[1] + "</span>" + (a.source === "online" ? '<span class="chip neutral">pelo link</span>' : "") + "</div>" +
      body + '<div class="row ap-actions">' + actions.join("") + "</div></div></article>";
  }
  function agendaHero() {
    var t = todayIso(), weekEnd = addDays(t, 6), all = storeList();
    var today = all.filter(function (a) { return a.day === t && counts(a); });
    var pend = all.filter(function (a) { return a.day >= t && a.status === "pendente"; });
    var week = all.filter(function (a) { return a.day >= t && a.day <= weekEnd && counts(a); });
    var sum = function (l) { return l.reduce(function (s, a) { return s + (a.price || 0); }, 0); };
    var biz = bizName();
    return '<section class="hero no-art"><div class="hero-text">' +
      '<span class="eyebrow">' + ICONS.cal.replace("<svg", '<svg width="14" height="14"') + "Sua agenda</span>" +
      "<h2>" + (biz ? "Olá, " + esc(biz) + "!" : CFG.firstName ? "Olá, " + esc(CFG.firstName) + "!" : "Sua agenda") + "</h2>" +
      '<div class="hero-stats">' +
      '<div class="hero-stat"><b>' + today.length + "</b><span>" + (today.length === 1 ? "atendimento hoje" : "atendimentos hoje") + " · " + brl(sum(today)) + "</span></div>" +
      '<div class="hero-stat' + (pend.length ? " attn" : "") + '"><b>' + pend.length + "</b><span>" + (pend.length === 1 ? "aguarda" : "aguardam") + " sua confirmação</span></div>" +
      '<div class="hero-stat"><b>' + brl(sum(week)) + "</b><span>previsto nos próximos 7 dias</span></div>" +
      "</div></div></section>";
  }
  function renderAgenda() {
    var t = todayIso(), from = view.day < t ? view.day : t, to = addDays(view.day > t ? view.day : t, 30);
    if (addDays(from, 62) < to) from = addDays(to, -62);
    if (MODE === "conta" && !linkInfo.loaded) loadLink();
    var done = false;
    store.ensure(from, to).then(function (changed) {
      done = true; appts.error = "";
      if (changed && view.tab === "agenda") renderAgenda();
    }, function (err) {
      done = true;
      if (err.message === "auth") return;
      appts.error = "Não foi possível carregar a agenda. Confira sua internet.";
      if (view.tab === "agenda") drawAgenda();
    });
    if (MODE === "conta" && !done && !Object.keys(appts.loaded).length) {
      app.innerHTML = '<div class="empty"><p>Carregando sua agenda…</p></div>';
      return;
    }
    drawAgenda();
  }
  function drawAgenda() {
    var t = todayIso(), day = view.day;
    var pend = storeList().filter(function (a) { return a.day >= t && a.status === "pendente" && a.day !== day; })
      .sort(function (x, y) { return x.day < y.day ? -1 : x.day > y.day ? 1 : x.start - y.start; });
    var items = dayItems(day);
    var a = agendaCfg(), win = a.week[dateOf(day).getDay()];
    var dayInfo = win && win.on ? "Atendimento das " + esc(win.start) + " às " + esc(win.end) : "Dia de folga na sua agenda online";
    var linkNotice = MODE === "conta" && linkInfo.loaded && !linkInfo.url
      ? '<div class="notice"><span><b>Crie seu link de agendamento</b> e deixe suas clientes marcarem horário sozinhas, 24 horas por dia.</span>' +
        '<button class="btn small" data-action="go-link">Criar meu link</button></div>' : "";
    var demoNotice = MODE === "demo"
      ? '<div class="notice"><span><b>Agenda de exemplo.</b> Confirme, conclua, cancele ou crie horários para ver como funciona.</span></div>' : "";
    app.innerHTML = agendaHero() + demoNotice + linkNotice +
      (appts.error ? '<div class="notice"><span>' + esc(appts.error) + '</span><button class="btn small" data-action="reload">Tentar de novo</button></div>' : "") +
      (pend.length ? '<section class="panel"><h3 class="section-title">Aguardando sua confirmação</h3><div class="appts">' +
        pend.map(function (x) { return '<div class="ap-day-label">' + esc(dayLabel(x.day)) + "</div>" + apptCard(x); }).join("") + "</div></section>" : "") +
      '<div class="day-nav"><button class="iconbtn big" data-action="day-prev" aria-label="Dia anterior">‹</button>' +
      '<div class="day-title"><h2 class="section-title">' + esc(dayLabel(day)) + '</h2><span class="hint">' + dayInfo + "</span></div>" +
      '<button class="iconbtn big" data-action="day-next" aria-label="Próximo dia">›</button></div>' +
      '<div class="row spread"><div class="row">' + (day !== t ? '<button class="btn small" data-action="day-today">Hoje</button>' : "") +
      '<input type="date" id="day-pick" class="date-pick" value="' + day + '" aria-label="Escolher data"></div>' +
      '<div class="row"><button class="btn small" data-action="ap-new-block">Bloquear horário</button>' +
      '<button class="btn primary" data-action="ap-new">+ Novo horário</button></div></div>' +
      (view.form ? apptForm() : "") +
      (items.length ? '<div class="appts">' + items.map(apptCard).join("") + "</div>"
        : '<div class="empty"><p>Nenhum horário neste dia.' + (win && win.on ? "<br>Sua agenda está livre para novos agendamentos." : "") + "</p></div>");
  }
  function apptForm() {
    var f = view.form, block = f.status === "bloqueio";
    var chips = state.products.filter(function (p) { return (p.name || "").trim(); }).map(function (p) {
      return '<button type="button" class="seg-chip small" data-action="af-svc" data-id="' + p.id + '">+ ' + esc(p.name) + "</button>";
    }).join("");
    return '<section class="panel ap-form" id="ap-form"><div class="row spread"><h3 class="section-title">' +
      (f.id ? "Editar horário" : block ? "Bloquear horário" : "Novo horário") + '</h3>' +
      '<button class="iconbtn" data-action="af-close" aria-label="Fechar">×</button></div>' +
      (block ? '<p class="hint">Use para folgas, compromissos ou horários que você não quer abrir no link.</p>' :
        '<div class="grid"><label class="field"><span>NOME DA CLIENTE</span><input data-af="client_name" value="' + esc(f.client_name) + '" maxlength="120" placeholder="Ex: Juliana Alves"></label>' +
        '<label class="field"><span>WHATSAPP</span><input data-af="client_phone" inputmode="tel" value="' + esc(f.client_phone) + '" placeholder="(11) 98888-7777"></label></div>' +
        '<label class="field"><span>SERVIÇO</span><input data-af="services" value="' + esc(f.services) + '" maxlength="300" placeholder="Ex: Pé e mão"></label>' +
        (chips ? '<div class="seg-chips">' + chips + "</div>" : "")) +
      '<div class="grid"><label class="field"><span>DATA</span><input type="date" data-af="day" value="' + esc(f.day) + '"></label>' +
      '<label class="field"><span>HORÁRIO</span><input type="time" step="300" data-af="time" value="' + esc(f.time) + '"></label>' +
      '<label class="field"><span>DURAÇÃO</span><span class="suffix"><input inputmode="numeric" data-af="duration" value="' + esc(f.duration) + '"><em>min</em></span></label>' +
      (block ? "" : '<label class="field"><span>VALOR</span><span class="suffix"><input inputmode="decimal" data-af="price" value="' + esc(f.price ? fmt(parseNum(f.price), 2) : "") + '" placeholder="0,00"><em>R$</em></span></label>') +
      "</div>" +
      '<label class="field"><span>' + (block ? "MOTIVO (SÓ VOCÊ VÊ)" : "OBSERVAÇÃO") + '</span><input data-af="note" value="' + esc(f.note) + '" maxlength="300" placeholder="' + (block ? "Ex: Consulta médica" : "Ex: Quer francesinha") + '"></label>' +
      (f.error ? '<div class="verdict ' + (f.conflict ? "warn" : "crit") + '"><strong>' + esc(f.error) + "</strong>" +
        (f.conflict ? '<span>Você pode escolher outro horário ou encaixar mesmo assim.</span>' : "") + "</div>" : "") +
      '<div class="row"><button class="btn primary" data-action="af-save">' + (f.id ? "Salvar alterações" : block ? "Bloquear" : "Agendar") + "</button>" +
      (f.conflict ? '<button class="btn" data-action="af-force">Encaixar mesmo assim</button>' : "") +
      '<button class="btn ghost" data-action="af-close">Cancelar</button></div></section>';
  }
  function openForm(status, item) {
    var a = agendaCfg(), win = a.week[dateOf(view.day).getDay()];
    view.form = item
      ? { id: item.id, status: item.status, day: item.day, time: item.time, duration: item.duration, price: item.price,
          client_name: item.client_name, client_phone: item.client_phone, services: item.services, note: item.note }
      : { status: status, day: view.day, time: win && win.on ? win.start : "09:00", duration: status === "bloqueio" ? 60 : 0,
          price: 0, client_name: "", client_phone: "", services: "", note: "" };
    drawAgenda();
    var el = document.getElementById("ap-form");
    if (el) { el.scrollIntoView({ block: "start", behavior: "smooth" }); var inp = el.querySelector("input"); if (inp) inp.focus({ preventScroll: true }); }
  }
  function saveForm(force) {
    var f = view.form;
    if (hm(f.time) == null || !/^\d{4}-\d{2}-\d{2}$/.test(f.day || "")) { f.error = "Escolha a data e o horário."; f.conflict = false; return drawAgenda(); }
    if (!(parseNum(f.duration) >= 5)) { f.error = "Informe a duração (em minutos)."; f.conflict = false; return drawAgenda(); }
    if (f.status !== "bloqueio" && !String(f.client_name || "").trim()) { f.error = "Informe o nome da cliente."; f.conflict = false; return drawAgenda(); }
    var body = { day: f.day, time: f.time, duration: Math.round(parseNum(f.duration)), note: f.note || "" };
    if (f.status === "bloqueio") body.services = "";
    else { body.client_name = f.client_name; body.client_phone = f.client_phone; body.services = f.services; body.price = parseNum(f.price); }
    if (!f.id) body.status = f.status;
    if (force) body.force = true;
    var p = f.id ? store.update(f.id, body) : store.create(body);
    p.then(function (it) {
      view.form = null; view.day = it.day; drawAgenda();
    }, function (err) {
      if (err.message === "auth") return;
      f.error = err.message; f.conflict = !!err.conflict; drawAgenda();
    });
  }

  // ---------- serviços ----------
  function productPhoto(p) { var id = p.menu && p.menu.photo; return id && MODE === "conta" ? id : null; }
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
    var art = heroArt();
    return '<section class="hero' + (art ? "" : " no-art") + '"><div class="hero-text">' +
      '<span class="eyebrow">' + ICONS.tag.replace('<svg', '<svg width="14" height="14"') + "Preço dos seus serviços</span>" +
      "<h2>Quanto cobrar em cada atendimento</h2>" +
      "<p>Some os materiais que você gasta, a luz, a esterilização, as taxas e o valor da sua hora e veja o preço certo de cada serviço.</p>" +
      '<div class="hero-stats">' +
      '<div class="hero-stat"><b>' + state.products.length + "</b><span>serviços cadastrados</span></div>" +
      '<div class="hero-stat"><b>' + (isFinite(avg) ? pct(avg) : "—") + "</b><span>margem média do que você cobra</span></div>" +
      '<div class="hero-stat' + (attention ? " attn" : "") + '"><b>' + attention + "</b><span>" + (attention === 1 ? "serviço precisa" : "serviços precisam") + " de atenção</span></div>" +
      "</div></div>" +
      (art ? '<div class="hero-art">' + art + "</div>" : "") + "</section>";
  }
  function needsOnboarding() {
    return state.example && !state.onboarded && (MODE === "demo" || !(state.settings.business || "").trim());
  }
  function onboardingCard() {
    var seg = view.obSeg || state.settings.segment || "manicure";
    var chips = Object.keys(SEGMENTS).map(function (k) {
      return '<button type="button" class="seg-chip" data-action="ob-seg" data-seg="' + k + '" aria-pressed="' + (k === seg) + '">' + SEGMENTS[k].label + "</button>";
    }).join("");
    return '<section class="panel onboard"><div><h3 class="section-title">Vamos deixar com a cara do seu espaço</h3>' +
      '<p class="hint">Em 10 segundos o sistema monta exemplos dos serviços que você faz. Depois é só ajustar com os seus preços.</p></div>' +
      '<label class="field"><span>NOME DO SEU ESPAÇO</span><input id="ob-name" maxlength="60" placeholder="Ex: ' + esc(SEGMENTS[seg].business) + '" value="' +
      esc(MODE === "demo" ? "" : state.settings.business || "") + '"></label>' +
      '<div class="field"><span>O QUE VOCÊ FAZ?</span><div class="seg-chips" role="group" aria-label="Segmento">' + chips + "</div></div>" +
      '<div class="row"><button class="btn primary" data-action="ob-go">Montar meus exemplos</button>' +
      '<button class="btn ghost" data-action="ob-skip">Pular</button></div></section>';
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
      var meta = duration(p.minutes) + " · custo " + brl(c.unit) + (c.current != null ? " · sugerido " + brl(c.price) : "");
      return '<button class="product" data-action="edit" data-id="' + p.id + '">' + thumb +
        '<span class="p-main"><span class="p-name">' + esc(p.name || "Sem nome") + '</span><span class="p-meta num">' + meta + "</span></span>" +
        '<span class="p-price"><strong>' + brl(c.current != null ? c.current : c.price) + "</strong>" + chip + "</span></button>";
    }).join("");
    app.innerHTML = (needsOnboarding() ? onboardingCard() : "") + renderHero() + exampleNotice() +
      '<div class="row spread"><h2 class="section-title">Seus serviços</h2>' +
      '<button class="btn primary" data-action="new-product">+ Novo serviço</button></div>' +
      (state.products.length
        ? '<div class="products">' + list + "</div>"
        : '<div class="empty"><p>Nenhum serviço ainda.<br>Cadastre os materiais e depois monte o seu primeiro serviço.</p>' +
          (state.ingredients.length ? "" : '<button class="btn" data-action="go-ings">Cadastrar materiais</button>') + "</div>");
  }

  function renderEditor() {
    var p = state.products.filter(function (x) { return x.id === view.editing; })[0];
    if (!p) { view.editing = null; return renderProducts(); }
    var s = state.settings;
    var options = state.ingredients.slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
    function itemRow(it, idx) {
      var ing = ingById(it.ingId);
      var sel = '<select data-item="' + idx + '" data-field="ingId" aria-label="Material">' +
        '<option value="">Escolha o material</option>' +
        options.map(function (o) {
          return '<option value="' + o.id + '"' + (o.id === it.ingId ? " selected" : "") + ">" + esc(o.name) + "</option>";
        }).join("") + "</select>";
      return '<div class="item">' + sel +
        '<span class="suffix qty"><input inputmode="decimal" data-item="' + idx + '" data-field="qty" value="' + esc(fmt(parseNum(it.qty), 3)) + '" aria-label="Quantidade usada por atendimento"><em data-unit="' + idx + '">' + (ing ? baseUnit(ing) : "") + "</em></span>" +
        '<span class="cost num" data-cost="' + idx + '"></span>' +
        '<button class="iconbtn" data-action="del-item" data-idx="' + idx + '" aria-label="Remover material">×</button></div>';
    }
    var delArmed = view.confirm === "del-product";
    app.innerHTML =
      '<div class="row spread"><button class="btn ghost" data-action="back">← Serviços</button>' +
      '<div class="row"><button class="btn small" data-action="dup-product">Duplicar</button>' +
      '<button class="btn small danger' + (delArmed ? " armed" : "") + '" data-action="del-product">' + (delArmed ? "Toque de novo para excluir" : "Excluir") + "</button></div></div>" +

      '<section class="panel"><label class="field"><span>NOME DO SERVIÇO</span>' +
      '<input id="p-name" data-p="name" value="' + esc(p.name) + '" placeholder="Ex: Pé e mão"></label>' +
      '<div class="grid">' +
      '<label class="field"><span>DURAÇÃO DO ATENDIMENTO</span><span class="suffix"><input id="p-min" inputmode="numeric" data-p="minutes" value="' + esc(fmt(parseNum(p.minutes), 0)) + '"><em>min</em></span>' +
      '<small class="hint">Usada no preço (valor da sua hora) e para reservar o tempo certo na agenda.</small></label>' +
      "</div></section>" +

      '<section class="panel"><div class="row spread"><h3 class="section-title">Materiais usados em 1 atendimento</h3>' +
      '<span class="hint">Ex.: 0,6 ml de esmalte, 1 lixa, 2 luvas</span></div>' +
      (options.length
        ? '<div class="items">' + p.items.map(itemRow).join("") + "</div>" +
          '<div><button class="btn small" data-action="add-item">+ Adicionar material</button></div>'
        : '<p class="hint">Você ainda não cadastrou materiais.</p><div><button class="btn small" data-action="go-ings">Cadastrar materiais</button></div>') +
      "</section>" +

      '<section class="panel"><div class="grid">' +
      '<label class="field"><span>MARGEM DESEJADA</span><span class="suffix"><input id="p-margin" inputmode="decimal" data-p="margin" value="' + (p.margin == null ? "" : esc(fmt(parseNum(p.margin), 1))) + '" placeholder="' + esc(fmt(parseNum(s.margin), 1)) + ' (padrão)"><em>%</em></span></label>' +
      '<label class="field"><span>PREÇO QUE VOCÊ COBRA HOJE</span><span class="suffix"><input id="p-current" inputmode="decimal" data-p="current" value="' + (parseNum(p.current) > 0 ? esc(fmt(parseNum(p.current), 2)) : "") + '" placeholder="0,00"><em>R$</em></span></label>' +
      "</div></section>" +

      '<section class="result" aria-live="polite"><div class="tiles">' +
      '<div class="tile tile-cost"><span class="tile-label">' + ICONS.coin + 'Custo do atendimento</span><b class="num" data-out="unit"></b></div>' +
      '<div class="tile tile-price"><span class="tile-label">' + ICONS.tag + 'Preço sugerido</span><b class="num" data-out="price"></b></div>' +
      '<div class="tile tile-profit"><span class="tile-label">' + ICONS.trend + 'Lucro por atendimento</span><b class="num" data-out="profit"></b></div>' +
      '</div><p class="result-sub"><span data-out="price-sub"></span> <span data-out="per-hour"></span></p></section>' +
      '<div data-out="verdict"></div>' +

      '<section class="panel"><h3 class="section-title">De onde vem o custo</h3><table class="breakdown"><tbody data-out="breakdown"></tbody></table>' +
      '<p class="hint">Luz, esterilização, taxas e o valor da sua hora ficam em <a href="#" data-action="go-settings">Ajustes</a>.</p></section>';
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
    } else {
      out("price", brl(c.price));
      out("price-sub", (Math.abs(c.price - c.suggested) > 0.004 ? "Cálculo exato " + brl(c.suggested) + ", arredondado para cima. " : "") +
        "Margem de " + pct(c.margin) + (c.fee ? " já descontando " + pct(c.fee) + " de taxas" : "") + ".");
    }
    out("unit", brl(c.unit));
    out("profit", isFinite(c.profitUnit) ? brl(c.profitUnit) : "—");
    var ph = c.current != null ? c.currentPerHour : c.perHour;
    out("per-hour", isFinite(ph) ? "Você ganha <b class=\"num\">" + brl(ph) + "</b> por hora de atendimento (seu trabalho + lucro)" + (c.current != null ? ", cobrando " + brl(c.current) : "") + "." : "");

    var v = "";
    if (c.current != null && isFinite(c.price)) {
      var lv = level(c.currentMargin, c.margin), diff = c.price - c.current;
      var msg = lv === "crit"
        ? "Cobrando " + brl(c.current) + " você perde " + brl(-c.currentProfit) + " a cada atendimento."
        : "Cobrando " + brl(c.current) + " você lucra " + brl(c.currentProfit) + " por atendimento (" + pct(c.currentMargin) + " do preço).";
      var tip = diff > 0.004 ? "Para chegar na margem desejada, aumente " + brl(diff) + "."
        : diff < -0.004 ? "Seu preço está acima do sugerido. Ótimo, se a agenda continua cheia."
        : "Seu preço está igual ao sugerido.";
      v = '<div class="verdict ' + lv + '"><strong>' + levelLabel(c.currentMargin, c.margin) + "</strong><span>" + msg + "</span><span>" + tip + "</span></div>";
    }
    out("verdict", v);

    var rows = [
      ["Materiais e descartáveis", c.ingCost],
      ["Luz, esterilização e desgaste (" + fmt(parseNum(s.extras), 1) + "%)", c.extras],
      ["Seu trabalho (" + fmt(parseNum(p.minutes), 0) + " min a " + brl(parseNum(s.hourly)) + "/h)", c.labor]
    ].map(function (r) { return "<tr><td>" + esc(r[0]) + "</td><td>" + brl(r[1]) + "</td></tr>"; }).join("");
    rows += '<tr class="total"><td>Custo total do atendimento</td><td>' + brl(c.unit) + "</td></tr>";
    out("breakdown", rows);
  }

  // ---------- materiais ----------
  function usedIn(id) {
    return state.products.filter(function (p) { return p.items.some(function (it) { return it.ingId === id; }); }).length;
  }
  function renderIngredients() {
    var rows = state.ingredients.map(function (i) {
      var armed = view.confirm === "del-ing:" + i.id, n = usedIn(i.id);
      return '<div class="ing" data-ing="' + i.id + '">' +
        '<input class="name" data-f="name" value="' + esc(i.name) + '" placeholder="Nome" aria-label="Nome do material">' +
        '<span class="suffix"><input inputmode="decimal" data-f="price" value="' + esc(fmt(parseNum(i.price), 2)) + '" aria-label="Preço pago"><em>R$</em></span>' +
        '<input inputmode="decimal" data-f="qty" value="' + esc(fmt(parseNum(i.qty), 3)) + '" aria-label="Quantidade na embalagem">' +
        '<select data-f="unit" aria-label="Unidade">' + Object.keys(UNITS).map(function (u) {
          return '<option value="' + u + '"' + (u === i.unit ? " selected" : "") + ">" + u + "</option>";
        }).join("") + "</select>" +
        '<button class="iconbtn" data-action="del-ing" data-id="' + i.id + '" aria-label="Excluir material">×</button>' +
        '<span class="unitcost num" data-uc="' + i.id + '">' + unitCostText(i) + "</span>" +
        (armed ? '<div class="row" style="grid-column:1/-1"><span class="hint">' +
          (n ? "Usado em " + n + " serviço(s). Ele será removido desses serviços." : "Excluir este material?") +
          '</span><button class="btn small danger armed" data-action="del-ing-yes" data-id="' + i.id + '">Excluir</button>' +
          '<button class="btn small" data-action="cancel">Cancelar</button></div>' : "") +
        "</div>";
    }).join("");
    app.innerHTML = exampleNotice() +
      '<div class="row spread"><h2 class="section-title">Materiais e descartáveis</h2>' +
      '<button class="btn primary" data-action="new-ing">+ Novo material</button></div>' +
      '<p class="hint">Digite o preço que você pagou e o tamanho da embalagem (ex.: esmalte, R$ 7,90, 8 ml). Quando o preço mudar, atualize aqui: todos os serviços são recalculados.</p>' +
      (state.ingredients.length
        ? '<div class="ing-head"><span>Nome</span><span>Preço pago</span><span>Embalagem</span><span>Unidade</span><span></span></div><div class="ings">' + rows + "</div>"
        : '<div class="empty"><p>Nenhum material cadastrado.<br>Comece pelo que você mais usa: esmaltes, lixas, algodão, luvas…</p></div>');
  }
  function unitCostText(i) {
    var c = costPerBase(i), b = baseUnit(i);
    if (!c) return "Preencha preço e quantidade";
    var n = usedIn(i.id);
    return smallBrl(c) + " por " + b + (n ? " · usado em " + n + " serviço(s)" : "");
  }

  // ---------- link de agendamento ----------
  var linkInfo = { loaded: false, loading: false, slug: null, url: null, base: "", error: "" };
  function loadLink() {
    if (linkInfo.loading || linkInfo.loaded) return;
    linkInfo.loading = true;
    apiJson("GET", "/api/agenda/link").then(function (j) {
      linkInfo.loaded = true; linkInfo.loading = false; linkInfo.slug = j.slug; linkInfo.url = j.url; linkInfo.base = j.base;
      if (view.tab === "link" || view.tab === "agenda") render();
    }, function (err) {
      linkInfo.loading = false;
      if (err.message === "auth") return;
      linkInfo.loaded = true; linkInfo.error = "Não foi possível carregar o link agora.";
      if (view.tab === "link") renderLink();
    });
  }
  function pmenu(p) {
    if (!p.menu) p.menu = { show: true, desc: "", photo: null };
    return p.menu;
  }
  function productById(id) { return state.products.filter(function (x) { return x.id === id; })[0]; }
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
  function selectField(key, label, opts, hint) {
    var a = agendaCfg();
    return '<label class="field"><span>' + label + '</span><select data-ag="' + key + '">' + opts.map(function (o) {
      return '<option value="' + o[0] + '"' + (parseNum(a[key]) === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
    }).join("") + "</select>" + (hint ? '<small class="hint">' + hint + "</small>" : "") + "</label>";
  }

  function renderLink() {
    var a = agendaCfg();
    if (MODE === "conta" && !linkInfo.loaded) {
      app.innerHTML = '<div class="empty"><p>Carregando seu link…</p></div>';
      loadLink();
      return;
    }
    var linkBlock;
    if (MODE !== "conta") {
      linkBlock = '<section class="panel"><h3 class="section-title">Seu link de agendamento</h3>' +
        '<p class="hint">Na conta completa você ganha um link próprio, como <b>/a/espaco-da-carol</b>, e um QR Code para imprimir. ' +
        'Suas clientes escolhem o serviço, o dia e o horário livre, e o agendamento cai direto na sua agenda.</p></section>';
    } else {
      var suggestion = linkInfo.slug || slugify(state.settings.business);
      linkBlock = '<section class="panel"><h3 class="section-title">Seu link de agendamento</h3>' +
        '<label class="field"><span>ENDEREÇO DA SUA PÁGINA</span><span class="slug-row"><span class="slug-base">' + esc(linkInfo.base) + '</span>' +
        '<input id="m-slug" value="' + esc(suggestion) + '" placeholder="espaco-da-carol" autocapitalize="off" autocomplete="off" spellcheck="false"></span></label>' +
        '<div class="row"><button class="btn primary" data-action="save-slug">' + (linkInfo.slug ? "Salvar novo link" : "Criar meu link") + '</button>' +
        '<span class="hint" id="slug-msg" role="status">' + esc(linkInfo.error) + '</span></div>' +
        (linkInfo.url
          ? '<div class="share"><div class="share-url num" id="share-url">' + esc(linkInfo.url) + '</div><div class="row">' +
            '<button class="btn small" data-action="copy-link">Copiar link</button>' +
            '<a class="btn small" href="' + esc(linkInfo.url) + '" target="_blank" rel="noopener">Abrir minha página</a>' +
            '<a class="btn small" href="https://wa.me/?text=' + encodeURIComponent("Agende seu horário comigo por aqui: " + linkInfo.url) + '" target="_blank" rel="noopener">Enviar no WhatsApp</a>' +
            '</div><div class="qr-box"><div id="qr" class="qr"></div><div class="qr-side"><b>QR Code da agenda</b>' +
            '<p class="hint">Imprima e deixe na bancada, no espelho ou no cartão de visita. Coloque o link na bio do Instagram.</p>' +
            '<button class="btn small" data-action="download-qr">Baixar QR Code</button></div></div></div>'
          : "") +
        "</section>";
    }
    var hours = a.week.map(function (d, i) {
      return '<div class="wk-row"><label class="check"><input type="checkbox" data-wk="' + i + '" data-wf="on"' + (d.on ? " checked" : "") + "> <b>" + WD_FULL[i] + "</b></label>" +
        '<input type="time" step="900" data-wk="' + i + '" data-wf="start" value="' + esc(d.start) + '" aria-label="Início ' + WD_FULL[i] + '"' + (d.on ? "" : " disabled") + ">" +
        '<span class="hint">às</span><input type="time" step="900" data-wk="' + i + '" data-wf="end" value="' + esc(d.end) + '" aria-label="Fim ' + WD_FULL[i] + '"' + (d.on ? "" : " disabled") + "></div>";
    }).join("");
    var rows = state.products.filter(function (p) { return (p.name || "").trim(); }).map(function (p) {
      var pm = pmenu(p), price = shownPrice(p);
      var photo = productPhoto(p)
        ? '<img class="mi-photo" src="/f/' + esc(pm.photo) + '" alt="">'
        : '<div class="mi-photo mi-empty" aria-hidden="true">' + esc(p.name.trim().charAt(0).toUpperCase()) + "</div>";
      return '<div class="menu-item" data-mp="' + p.id + '">' + photo + '<div class="mi-body">' +
        '<div class="row spread"><label class="check"><input type="checkbox" data-mf="show"' + (pm.show !== false ? " checked" : "") + "> <b>" + esc(p.name) + "</b></label>" +
        '<span class="num mi-price">' + duration(p.minutes) + " · " + (isFinite(price) && price > 0 ? brl(price) : "sem preço") + "</span></div>" +
        '<input data-mf="desc" value="' + esc(pm.desc) + '" maxlength="300" placeholder="Descrição curta (ex: cutilagem e esmaltação)" aria-label="Descrição de ' + esc(p.name) + '">' +
        (MODE === "conta"
          ? '<div class="row"><label class="btn small" for="ph-' + p.id + '">' + (pm.photo ? "Trocar foto" : "Adicionar foto") + "</label>" +
            '<input type="file" accept="image/*" id="ph-' + p.id + '" data-photo="' + p.id + '" hidden>' +
            (pm.photo ? '<button class="btn small ghost" data-action="del-photo" data-id="' + p.id + '">Remover foto</button>' : "") +
            '<button class="btn small ghost" data-action="menu-edit" data-id="' + p.id + '">Editar serviço</button>' +
            '<span class="hint" data-phmsg="' + p.id + '"></span></div>'
          : '<div class="row"><button class="btn small ghost" data-action="menu-edit" data-id="' + p.id + '">Editar serviço</button></div>') +
        "</div></div>";
    }).join("");
    app.innerHTML =
      '<h2 class="section-title">Agendamento online</h2>' +
      '<p class="hint">Sua cliente abre o link, escolhe os serviços, o dia e um horário livre. O horário entra na sua agenda e ela pode te avisar no WhatsApp com tudo preenchido.</p>' +
      linkBlock +
      '<section class="panel"><h3 class="section-title">Dias e horários de atendimento</h3>' +
      '<p class="hint">Só aparecem para as clientes os horários dentro destes períodos, sem conflito com outros agendamentos.</p>' +
      '<div class="week">' + hours + "</div>" +
      '<div class="wk-row"><label class="check"><input type="checkbox" data-lunch="on"' + (a.lunch.on ? " checked" : "") + "> <b>Intervalo</b></label>" +
      '<input type="time" step="900" data-lunch="start" value="' + esc(a.lunch.start) + '" aria-label="Início do intervalo"' + (a.lunch.on ? "" : " disabled") + ">" +
      '<span class="hint">às</span><input type="time" step="900" data-lunch="end" value="' + esc(a.lunch.end) + '" aria-label="Fim do intervalo"' + (a.lunch.on ? "" : " disabled") + "></div>" +
      '<div class="grid">' +
      selectField("step", "HORÁRIOS DE", [[15, "15 em 15 min"], [20, "20 em 20 min"], [30, "30 em 30 min"], [45, "45 em 45 min"], [60, "1 em 1 hora"]], "De quanto em quanto tempo os horários aparecem.") +
      selectField("notice", "ANTECEDÊNCIA MÍNIMA", [[0, "Sem antecedência"], [1, "1 hora"], [2, "2 horas"], [4, "4 horas"], [12, "12 horas"], [24, "1 dia"], [48, "2 dias"]], "Evita agendamentos em cima da hora.") +
      selectField("daysAhead", "AGENDA ABERTA PARA", [[7, "Próximos 7 dias"], [15, "Próximos 15 dias"], [30, "Próximos 30 dias"], [60, "Próximos 60 dias"], [90, "Próximos 90 dias"]], "") +
      "</div>" +
      '<label class="check"><input type="checkbox" data-agc="autoConfirm"' + (a.autoConfirm ? " checked" : "") + "> Confirmar automaticamente os agendamentos feitos pelo link</label>" +
      '<small class="hint">Desligado: o horário fica reservado como “aguardando confirmação” até você confirmar.</small>' +
      (MODE === "conta" ? '<label class="check"><input type="checkbox" data-agc="notifyEmail"' + (a.notifyEmail !== false ? " checked" : "") + "> Avisar por e-mail quando chegar um agendamento novo</label>" : "") +
      "</section>" +
      '<section class="panel"><h3 class="section-title">Informações da página</h3>' +
      '<label class="field"><span>SEU WHATSAPP</span><input data-ag="whatsapp" inputmode="tel" value="' + esc(a.whatsapp) + '" placeholder="(11) 99999-8888"><small class="hint">A cliente usa para te avisar do agendamento e tirar dúvidas.</small></label>' +
      '<label class="field"><span>MENSAGEM DE BOAS-VINDAS</span><textarea data-ag="intro" maxlength="500" rows="2" placeholder="Unhas impecáveis com todo o cuidado. Materiais esterilizados e lixas descartáveis.">' + esc(a.intro) + "</textarea></label>" +
      '<label class="field"><span>ENDEREÇO OU ATENDIMENTO</span><input data-ag="address" maxlength="300" value="' + esc(a.address) + '" placeholder="Rua das Flores, 123 - Centro. Também atendo a domicílio."></label>' +
      "</section>" +
      '<section class="panel"><div class="row spread"><h3 class="section-title">Serviços na página</h3>' +
      '<button class="btn primary small" data-action="menu-new">+ Novo serviço</button></div>' +
      '<p class="hint">São os mesmos serviços da aba <b>Serviços</b>. Desmarque o que não quiser oferecer pelo link. ' +
      'O preço é o que você cobra hoje ou, se não informou, o sugerido. A duração reserva o tempo certo na agenda.</p>' +
      (rows ? '<div class="menu-items">' + rows + "</div>"
        : '<div class="empty"><p>Você ainda não tem serviços.<br>Crie o primeiro e ele aparece aqui.</p>' +
          '<button class="btn primary" data-action="menu-new">+ Criar meu primeiro serviço</button></div>') +
      "</section>";
    if (linkInfo.url) drawQr(document.getElementById("qr"), linkInfo.url, 148);
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
      if (old) apiJson("DELETE", "/api/fotos/" + old).catch(function () {});
      renderLink();
    }, function (err) {
      if (err.message !== "auth" && msg) msg.textContent = err.message;
    });
  }

  // ---------- ajustes ----------
  function renderSettings() {
    var s = state.settings, armed = view.confirm === "wipe";
    app.innerHTML =
      '<h2 class="section-title">Ajustes</h2>' +
      '<section class="panel"><label class="field"><span>NOME DO SEU ESPAÇO</span><input id="s-business" data-s="business" value="' + esc(s.business) + '" placeholder="Ex: Espaço da Carol"></label>' +
      '<div class="grid">' +
      settingField("s-margin", "margin", "MARGEM DE LUCRO PADRÃO", "%", "Quanto do preço é lucro. Manicures costumam usar de 35% a 50%.") +
      settingField("s-fee", "fee", "TAXAS SOBRE O ATENDIMENTO", "%", "Maquininha, cartão, nota fiscal. Some tudo.") +
      settingField("s-extras", "extras", "LUZ, ESTERILIZAÇÃO E DESGASTE", "%", "Somado ao custo dos materiais: estufa ou autoclave, alicates, lixa elétrica. 10% é um bom começo.") +
      settingField("s-hourly", "hourly", "VALOR DA SUA HORA", "R$", "Quanto você quer ganhar por hora de atendimento. Deixe 0 para ignorar.") +
      '<label class="field"><span>ARREDONDAR PREÇO PARA CIMA</span><select id="s-round" data-s="round">' +
      [[0, "Não arredondar"], [0.5, "De R$ 0,50 em R$ 0,50"], [1, "Para o real inteiro"], [5, "De R$ 5 em R$ 5"]].map(function (o) {
        return '<option value="' + o[0] + '"' + (parseNum(s.round) === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
      }).join("") + "</select></label>" +
      "</div></section>" +

      '<section class="panel"><h3 class="section-title">Backup dos seus dados</h3>' +
      '<p class="hint">' + (MODE === "conta" ? "Seus serviços, materiais e ajustes já ficam salvos na nuvem. Se quiser uma cópia extra, gere o backup e guarde. (Os agendamentos ficam guardados à parte, na sua agenda.)" : "Na demonstração os dados ficam só neste aparelho.") + '</p>' +
      '<div class="row"><button class="btn" data-action="export">Gerar backup</button>' +
      '<button class="btn" data-action="download">Baixar arquivo</button>' +
      '<label class="btn" for="import-file">Abrir arquivo de backup</label><input type="file" id="import-file" accept=".json,application/json,text/plain" hidden></div>' +
      '<textarea id="backup-text" class="backup" placeholder="Cole aqui um backup para restaurar, ou toque em Gerar backup."></textarea>' +
      '<div class="row"><button class="btn small" data-action="copy">Copiar texto</button><button class="btn small" data-action="restore">Restaurar do texto colado</button>' +
      '<span class="hint" id="backup-msg" role="status"></span></div></section>' +

      '<section class="panel"><h3 class="section-title">Recomeçar</h3><div class="row">' +
      '<button class="btn small" data-action="load-sample">Carregar exemplos</button>' +
      '<button class="btn small danger' + (armed ? " armed" : "") + '" data-action="wipe">' + (armed ? "Toque de novo para apagar serviços e materiais" : "Apagar serviços e materiais") + "</button>" +
      "</div></section>";
  }
  function settingField(id, key, label, unit, hint) {
    return '<label class="field"><span>' + label + '</span><span class="suffix"><input id="' + id + '" inputmode="decimal" data-s="' + key +
      '" value="' + esc(fmt(parseNum(state.settings[key]), 2)) + '"><em>' + unit + "</em></span><small class=\"hint\">" + hint + "</small></label>";
  }
  function backupMsg(t) { var el = document.getElementById("backup-msg"); if (el) el.textContent = t; }
  function backupText() { var copy = JSON.parse(JSON.stringify(state)); delete copy.appts; return JSON.stringify(copy); }
  function restoreFrom(text) {
    try {
      var d = JSON.parse(text);
      if (!d || d.v !== 1 || !Array.isArray(d.products) || !Array.isArray(d.ingredients) || !d.settings) throw new Error();
      if (MODE === "demo") d.appts = state.appts;
      state = d; agendaCfg(); save(); render(); backupMsg("Backup restaurado.");
    } catch (e) { backupMsg("Esse texto não é um backup válido."); }
  }
  // troca serviços e materiais, mas mantém agenda e link
  function replaceData(next) {
    next.agenda = state.agenda || next.agenda;
    if (MODE === "demo") next.appts = state.appts;
    state = next;
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
    if (a !== "del-product" && a !== "wipe" && a !== "del-ing" && a !== "ap-del") view.confirm = null;
    var p = state.products.filter(function (x) { return x.id === view.editing; })[0];

    switch (a) {
      // agenda
      case "day-prev": view.day = addDays(view.day, -1); view.form = null; renderAgenda(); return;
      case "day-next": view.day = addDays(view.day, 1); view.form = null; renderAgenda(); return;
      case "day-today": view.day = todayIso(); view.form = null; renderAgenda(); return;
      case "ap-new": openForm("confirmado"); return;
      case "ap-new-block": openForm("bloqueio"); return;
      case "ap-edit": openForm(null, appts.byId[t.dataset.id]); return;
      case "af-close": view.form = null; drawAgenda(); return;
      case "af-save": saveForm(false); return;
      case "af-force": saveForm(true); return;
      case "af-svc":
        var sp = productById(t.dataset.id), f = view.form;
        if (!sp || !f) return;
        f.services = f.services ? f.services + " + " + sp.name : sp.name;
        f.duration = Math.round(parseNum(f.duration)) + Math.round(parseNum(sp.minutes));
        var spPrice = shownPrice(sp);
        f.price = Math.round((parseNum(f.price) + (isFinite(spPrice) ? spPrice : 0)) * 100) / 100;
        ["services", "duration", "price"].forEach(function (k) {
          var el = app.querySelector('[data-af="' + k + '"]');
          if (el) el.value = k === "price" ? fmt(f.price, 2) : f[k];
        });
        return;
      case "ap-status":
        var target = appts.byId[t.dataset.id], ns = t.dataset.status;
        store.update(t.dataset.id, { status: ns }).then(drawAgenda, function (err) {
          if (err.message === "auth") return;
          if (err.conflict && window.confirm("Esse horário agora conflita com outro agendamento. Reabrir mesmo assim?")) {
            store.update(target.id, { status: ns, force: true }).then(drawAgenda, function (e2) { window.alert(e2.message); });
          } else if (!err.conflict) window.alert(err.message);
        });
        return;
      case "ap-del":
        if (view.confirm === "del-ap:" + t.dataset.id) {
          view.confirm = null;
          store.remove(t.dataset.id).then(drawAgenda, function (err) { if (err.message !== "auth") window.alert(err.message); });
        } else { view.confirm = "del-ap:" + t.dataset.id; drawAgenda(); }
        return;
      case "go-link": setTab("link"); return;
      // serviços e materiais
      case "start-blank":
        replaceData(blank()); save(); setTab("ingredientes"); return;
      case "load-sample":
        var seg2 = state.settings.segment || "manicure", biz2 = state.settings.business;
        replaceData(sampleFor(seg2, biz2)); state.onboarded = true; save(); setTab("produtos"); return;
      case "go-ings": setTab("ingredientes"); return;
      case "go-settings": setTab("ajustes"); return;
      case "ob-seg":
        view.obSeg = t.dataset.seg;
        app.querySelectorAll(".seg-chip").forEach(function (c) { c.setAttribute("aria-pressed", String(c === t)); });
        var obIn = document.getElementById("ob-name"); if (obIn) obIn.placeholder = "Ex: " + SEGMENTS[view.obSeg].business;
        return;
      case "ob-go":
        var obSeg = view.obSeg || state.settings.segment || "manicure";
        var obName = (document.getElementById("ob-name").value || "").trim();
        if (!obName && MODE === "demo") obName = SEGMENTS[obSeg].business;
        replaceData(sampleFor(obSeg, obName)); state.onboarded = true;
        save(); view.obSeg = null; render(); window.scrollTo(0, 0); return;
      case "ob-skip":
        state.onboarded = true; save(); render(); return;
      case "menu-edit":
        setTab("produtos"); view.editing = t.dataset.id; render(); window.scrollTo(0, 0); return;
      case "menu-new":
        setTab("produtos");
        /* falls through */
      case "new-product":
        var np = { id: uid(), name: "", yield: 1, minutes: 60, margin: null, current: 0, items: [{ ingId: "", qty: 0 }], menu: { show: true, desc: "", photo: null } };
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
        if (copy.menu) copy.menu.photo = null;
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
        var ni = { id: uid(), name: "", price: 0, qty: 1, unit: "un" };
        state.ingredients.unshift(ni); state.example = false; save(); render();
        var fi = app.querySelector('[data-ing="' + ni.id + '"] input'); if (fi) fi.focus();
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
        if (view.confirm === "wipe") { replaceData(blank()); save(); view.confirm = null; setTab("produtos"); }
        else { view.confirm = "wipe"; render(); }
        return;
      case "export":
        document.getElementById("backup-text").value = backupText();
        backupMsg("Backup gerado. Copie e guarde em lugar seguro."); return;
      case "copy":
        var ta = document.getElementById("backup-text");
        if (!ta.value) ta.value = backupText();
        var done = function () { backupMsg("Copiado."); };
        var fallback = function () { ta.focus(); ta.select(); backupMsg("Texto selecionado. Use Copiar do seu aparelho."); };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(ta.value).then(done, fallback);
        else fallback();
        return;
      case "download":
        try {
          var blob = new Blob([backupText()], { type: "application/json" });
          var link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = "manicure-backup-" + todayIso() + ".json";
          document.body.appendChild(link); link.click(); link.remove();
          backupMsg("Se o download não começar, use Gerar backup e Copiar texto.");
        } catch (err) { backupMsg("Download indisponível aqui. Use Gerar backup e Copiar texto."); }
        return;
      case "reload": location.reload(); return;
      // link
      case "save-slug":
        var slugIn = document.getElementById("m-slug"), slugMsg = document.getElementById("slug-msg");
        var val = slugify(slugIn.value); slugIn.value = val;
        slugMsg.textContent = "Salvando…";
        apiJson("PUT", "/api/agenda/link", JSON.stringify({ slug: val })).then(function (j) {
          linkInfo.slug = j.slug; linkInfo.url = j.url; linkInfo.error = "";
          renderLink();
          var m2 = document.getElementById("slug-msg"); if (m2) m2.textContent = "Link salvo. Já pode compartilhar!";
        }, function (err) { if (err.message !== "auth") slugMsg.textContent = err.message; });
        return;
      case "copy-link":
        copyText(linkInfo.url, document.getElementById("slug-msg")); return;
      case "download-qr":
        var canvas = qrCanvas(linkInfo.url, 720);
        if (canvas) {
          var a2 = document.createElement("a");
          a2.href = canvas.toDataURL("image/png");
          a2.download = "qrcode-agenda-" + (linkInfo.slug || "manicure") + ".png";
          document.body.appendChild(a2); a2.click(); a2.remove();
        }
        return;
      case "del-photo":
        var pp = productById(t.dataset.id), oldPhoto = pp && pmenu(pp).photo;
        if (oldPhoto) { pmenu(pp).photo = null; save(); apiJson("DELETE", "/api/fotos/" + oldPhoto).catch(function () {}); }
        renderLink(); return;
      case "restore":
        restoreFrom(document.getElementById("backup-text").value); return;
    }
  });

  app.addEventListener("input", function (e) {
    var t = e.target, ag;
    if (t.dataset.af && view.form) { view.form[t.dataset.af] = t.value; return; }
    if (t.dataset.ag) { ag = agendaCfg(); ag[t.dataset.ag] = t.tagName === "SELECT" ? parseNum(t.value) : t.value; save(); return; }
    if (t.dataset.agc) { agendaCfg()[t.dataset.agc] = t.checked; save(); return; }
    if (t.dataset.wk != null) {
      var d = agendaCfg().week[+t.dataset.wk];
      if (t.dataset.wf === "on") {
        d.on = t.checked;
        t.closest(".wk-row").querySelectorAll('input[type="time"]').forEach(function (x) { x.disabled = !t.checked; });
      } else d[t.dataset.wf] = t.value;
      save(); return;
    }
    if (t.dataset.lunch) {
      var l = agendaCfg().lunch;
      if (t.dataset.lunch === "on") {
        l.on = t.checked;
        t.closest(".wk-row").querySelectorAll('input[type="time"]').forEach(function (x) { x.disabled = !t.checked; });
      } else l[t.dataset.lunch] = t.value;
      save(); return;
    }
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
    var t = e.target;
    if (t.id === "day-pick" && /^\d{4}-\d{2}-\d{2}$/.test(t.value)) { view.day = t.value; view.form = null; renderAgenda(); return; }
    if (t.dataset.photo) { uploadPhoto(t); return; }
    if (t.id === "import-file" && t.files[0]) {
      var r = new FileReader();
      r.onload = function () { restoreFrom(String(r.result)); };
      r.readAsText(t.files[0]);
    }
  });

  function boot() {
    if (MODE === "demo") { state = loadLocal(); agendaCfg(); setTab(needsOnboarding() ? "produtos" : "agenda"); return; }
    app.innerHTML = '<div class="empty"><p>Carregando seus dados…</p></div>';
    api("GET").then(function (j) {
      if (j.data && j.data.v === 1) { state = j.data; agendaCfg(); setTab(needsOnboarding() ? "produtos" : "agenda"); setStatus("Salvo na nuvem", "ok"); }
      else { state = sample(); setTab("produtos"); save(); }
    }, function (err) {
      if (err.message === "auth") return;
      app.innerHTML = '<div class="empty"><p>Não foi possível carregar seus dados. Confira sua internet.</p>' +
        '<button class="btn" data-action="reload">Tentar de novo</button></div>';
    });
  }
  boot();
})();
