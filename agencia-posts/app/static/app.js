// Pequenos ajudantes da interface (o sistema funciona sem JavaScript).
(function () {
  function toast(msg) {
    var t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 1800);
  }

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { toast("Copiado!"); });
    } else {
      var ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); toast("Copiado!"); } catch (e) { /* sem suporte */ }
      ta.remove();
    }
  }

  // selects que enviam o formulário ao mudar
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });

  // confirmação antes de ações destrutivas
  document.querySelectorAll("form[data-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!confirm(form.getAttribute("data-confirmar"))) e.preventDefault();
    });
  });

  document.querySelectorAll("[data-copiar]").forEach(function (el) {
    el.addEventListener("click", function () { copy(el.getAttribute("data-copiar")); });
  });

  // formulário de postagem: contagem, prévia e copiar legenda
  var legenda = document.querySelector("[data-legenda]");
  var hashtags = document.querySelector("[data-hashtags]");
  if (legenda && hashtags) {
    var contagem = document.querySelector("[data-contagem]");
    var previa = document.querySelector("[data-previa-texto]");
    var full = function () {
      var c = legenda.value.trim(), h = hashtags.value.trim();
      return c && h ? c + "\n\n" + h : c || h;
    };
    var update = function () {
      var text = full();
      var tags = (hashtags.value.match(/#[^\s#]+/g) || []).length + (legenda.value.match(/#[^\s#]+/g) || []).length;
      contagem.textContent = text.length + " de 2.200 caracteres · " + tags + " de 30 hashtags";
      contagem.classList.toggle("estourou", text.length > 2200 || tags > 30);
      if (previa) previa.textContent = text || "A legenda aparece aqui.";
    };
    legenda.addEventListener("input", update);
    hashtags.addEventListener("input", update);
    update();
    var btn = document.querySelector("[data-copiar-legenda]");
    if (btn) btn.addEventListener("click", function () {
      if (!full()) { toast("Escreva a legenda primeiro."); return; }
      copy(full());
    });
  }

  // prévia muda junto com o cliente escolhido
  var sel = document.querySelector("[data-trocar-cliente]");
  if (sel) sel.addEventListener("change", function () {
    var o = sel.options[sel.selectedIndex];
    var nome = o.getAttribute("data-insta") || o.getAttribute("data-nome") || "cliente";
    document.querySelectorAll("[data-previa-nome]").forEach(function (el) { el.textContent = nome; });
    var cor = o.getAttribute("data-cor") || "#999";
    document.querySelectorAll(".previa-logo, .previa-imagem").forEach(function (el) { el.style.setProperty("--cor", cor); });
    var logo = document.querySelector(".previa-logo");
    if (logo) {
      logo.innerHTML = "";
      var src = o.getAttribute("data-logo");
      if (src) { var img = document.createElement("img"); img.src = src; img.alt = ""; logo.appendChild(img); }
    }
  });
})();
