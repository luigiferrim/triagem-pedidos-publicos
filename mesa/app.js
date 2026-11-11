// Mesa de triagem: fila, detalhe e painel com controle de limiar.
// Todos os números do painel são calculados aqui a partir de dados/holdout.json (previsões reais, sem texto).
"use strict";

const NIVEL = { alta: 2, media: 1, baixa: 0 };
const NOME_CONF = { alta: "alta", media: "média", baixa: "baixa" };
const NOME_NIVEL = { 2: "alta", 1: "média", 0: "baixa", "-1": "sem resposta" };
const estado = { holdout: null, exemplos: [], filtroStatus: "todos", filtroOrgao: "todos", selecionado: null, decisoes: {}, pontos: [] };

// ---------- números ----------
const br = (x, casas = 1) => (Math.round(x * 10 ** casas + 1e-9) / 10 ** casas).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const pct = (x, casas = 1) => br(100 * x, casas) + "%";
function wilson(k, n, z = 1.959964) {
  if (n === 0) return [0, 0];
  const p = k / n, d = 1 + z * z / n, c = (p + z * z / (2 * n)) / d, m = (z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d;
  return [Math.max(0, c - m), Math.min(1, c + m)];
}
function nota(p) { return [p.confianca in NIVEL ? NIVEL[p.confianca] : -1, p.sonnet === p.ml ? 1 : 0, p.p_ml]; }
function cmp(a, b) { for (let i = 0; i < 3; i++) { if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1; } return 0; }
const atinge = (n, limiar) => cmp(n, limiar) >= 0;

// Política v1 (mesma do Python, triagem.mesa.politica)
function politica(p, limiar) {
  const n = nota(p), auto = p.sonnet != null && atinge(n, limiar);
  if (p.confianca === "alta") return [auto, "confiança alta"];
  if (auto) return [true, `média, mas o ML concordou (p = ${br(p.p_ml, 2)})`];
  if (p.confianca === "media" && p.sonnet === p.ml) return [false, `incerto, foi para pessoa (média; o ML concordou, mas com p = ${br(p.p_ml, 2)})`];
  if (p.confianca === "media") return [false, `incerto, foi para pessoa (média; o ML sugeriu ${p.ml})`];
  return [false, "incerto, foi para pessoa (confiança baixa)"];
}

// Curva: um ponto por limiar distinto, do mais exigente ao menos exigente (empates entram juntos).
function curva(pedidos) {
  const itens = pedidos.map(p => ({ n: nota(p), ok: p.sonnet === p.rotulo })).sort((a, b) => cmp(b.n, a.n));
  const pontos = []; let acertos = 0;
  itens.forEach((it, k) => {
    acertos += it.ok;
    if (k === itens.length - 1 || cmp(itens[k + 1].n, it.n) !== 0) {
      const cob = k + 1, erros = cob - acertos;
      pontos.push({ limiar: it.n, cobertos: cob, erros, cobertura: cob / itens.length, erro: erros / cob, ic: wilson(erros, cob) });
    }
  });
  return pontos;
}
function regraEmPalavras(l, casas = 2) {
  const [n, a, p] = l, x = br(p, casas);
  if (n === 2) return a === 1 ? `Só confiança alta, com o ML concordando (p ≥ ${x}).` : `Só confiança alta (se o ML discordar, p ≥ ${x}).`;
  if (n === 1) return a === 1 ? `Confiança alta; ou média com o ML concordando e p ≥ ${x}.` : `Confiança alta ou média (média com o ML discordando, só se p ≥ ${x}).`;
  if (n === 0) return a === 1 ? `Alta ou média; ou baixa com o ML concordando e p ≥ ${x}.` : `Todos com resposta do modelo (baixa com o ML discordando, só se p ≥ ${x}).`;
  return "Todos os pedidos, inclusive sem resposta do modelo.";
}

// ---------- painel ----------
function painel() {
  const h = estado.holdout, r = h.resultado_1pct;
  document.getElementById("kpis").innerHTML = [
    ["Sem pessoa", pct(r.cobertura), `${r.cobertos} de ${h.pedidos.length} pedidos novos`],
    ["Erro na parte automática", pct(r.erro, 2), `IC 95% ${pct(r.erro_ic95[0], 2)}–${pct(r.erro_ic95[1], 2)}`],
    ["Custo por 1.000", "US$ " + br(h.custo_por_1000_usd, 2), "tokens reais"],
    ["Hoje, sem a máquina", pct(h.dor.pct_reencaminhados_10_orgaos / 100), "reencaminhados nestes 10 órgãos"],
  ].map(([t, v, s]) => `<div><dt>${t}</dt><dd><span class="v">${v}</span><span class="sub">${s}</span></dd></div>`).join("");

  const pts = estado.pontos = curva(h.pedidos);
  const ctl = document.getElementById("controle");
  ctl.max = pts.length - 1;
  const idx = l => pts.findIndex(p => p.cobertos === h.pedidos.filter(q => atinge(nota(q), l)).length);
  const marcas = [["meta de 1%", idx(h.limiares["1%"])], ["meta de 2%", idx(h.limiares["2%"])]];
  const elM = document.getElementById("marcas");
  estado.marcas = { [marcas[0][1]]: h.limiares["1%"], [marcas[1][1]]: h.limiares["2%"] };
  // Traços finos no trilho (posição de cada marca) e, abaixo, botões para ir até elas.
  elM.innerHTML = `<div class="tracos">${marcas.map(([t, i]) => `<span style="left:${100 * i / (pts.length - 1)}%"></span>`).join("")}</div>` +
    `<div class="ir">${marcas.map(([t, i]) => `<button type="button" class="pilula" data-i="${i}">Ir para a ${t}</button>`).join("")}</div>`;
  elM.querySelectorAll("button").forEach(b => b.addEventListener("click", () => { ctl.value = b.dataset.i; atualizarLimiar(); }));
  ctl.value = marcas[0][1];
  ctl.addEventListener("input", atualizarLimiar);
  desenharCurva();
  atualizarLimiar();
}
function atualizarLimiar() {
  const pts = estado.pontos, i = +document.getElementById("controle").value, p = pts[i], n = estado.holdout.pedidos.length;
  // Nas marcas, mostra o limiar escolhido no dev (o que a política usa); fora delas, o corte desta posição no holdout.
  const doDev = estado.marcas && estado.marcas[i];
  document.getElementById("regra").textContent = regraEmPalavras(doDev || p.limiar, doDev ? 4 : 2) + (doDev ? " Limiar escolhido no dev (Marco 4), congelado." : "");
  document.getElementById("controle").setAttribute("aria-valuetext", `${pct(p.cobertura)} sem pessoa, ${pct(p.erro, 2)} de erro`);
  document.getElementById("limiar-numeros").innerHTML = [
    ["Sem pessoa", pct(p.cobertura), `${p.cobertos} de ${n}`],
    ["Erro", pct(p.erro, 2), `IC 95% ${pct(p.ic[0], 2)}–${pct(p.ic[1], 2)}`],
    ["Para uma pessoa", String(n - p.cobertos), "pedidos"],
    ["Erros da máquina", String(p.erros), `em ${p.cobertos} encaminhados`],
  ].map(([t, v, s]) => `<div><dt>${t}</dt><dd>${v}<small>${s}</small></dd></div>`).join("");
  const c = document.querySelector("#curva .cursor");
  if (c) { const { x, y } = estado.escala; c.setAttribute("cx", x(p.cobertura)); c.setAttribute("cy", y(p.erro)); }
}
function desenharCurva() {
  const W = 640, H = 260, L = 40, R = 10, T = 10, B = 30, ymax = 0.06, xmin = 0.5;
  const x = v => L + (W - L - R) * (Math.max(v, xmin) - xmin) / (1 - xmin), y = v => T + (H - T - B) * (1 - Math.min(v, ymax) / ymax);
  estado.escala = { x, y };
  const pts = estado.pontos.filter(p => p.cobertura >= xmin);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Curva de cobertura por erro">`;
  for (const g of [0, 0.02, 0.04, 0.06]) s += `<line x1="${L}" x2="${W - R}" y1="${y(g)}" y2="${y(g)}" stroke="var(--line)"/><text x="${L - 6}" y="${y(g) + 4}" text-anchor="end">${br(100 * g, 0)}%</text>`;
  for (const g of [0.5, 0.75, 1]) s += `<text x="${x(g)}" y="${H - 8}" text-anchor="${g === 1 ? "end" : g === 0.5 ? "start" : "middle"}">${br(100 * g, 0)}%</text>`;
  s += `<path d="${pts.map((p, i) => (i ? "L" : "M") + x(p.cobertura).toFixed(1) + " " + y(p.erro).toFixed(1)).join(" ")}" fill="none" stroke="var(--ink)" stroke-width="1.5"/>`;
  s += `<circle class="cursor" r="5" fill="var(--ink)" stroke="var(--bg)" stroke-width="2"/></svg>`;
  document.getElementById("curva").innerHTML = s + `<p class="ajuda">Sem pessoa (horizontal) × erro (vertical).</p>`;
}

// ---------- fila e detalhe ----------
function statusDe(e) {
  const d = estado.decisoes[e.id];
  if (d) return { cls: "feito", txt: d.tipo === "confirmado" ? "confirmado" : `corrigido para ${d.orgao}` };
  if (e.tipo.startsWith("erro")) return { cls: "erro", txt: "encaminhado automaticamente · erro da IA" };
  return e.status === "encaminhado automaticamente" ? { cls: "auto", txt: "encaminhado automaticamente" } : { cls: "pessoa", txt: "aguardando servidor" };
}
function visiveis() {
  return estado.exemplos.filter(e =>
    (estado.filtroStatus === "todos" || e.status === estado.filtroStatus) &&
    (estado.filtroOrgao === "todos" || e.sonnet === estado.filtroOrgao));
}
function filtros() {
  const opcoes = [["todos", "Todos", "Todos"], ["encaminhado automaticamente", "Encaminhados automaticamente", "Automáticos"], ["aguardando servidor", "Aguardando servidor", "Aguardando"]];
  const el = document.getElementById("filtro-status");
  el.innerHTML = opcoes.map(([v, t, c]) => `<button type="button" class="pilula" data-v="${v}" aria-pressed="${v === estado.filtroStatus}" aria-label="${t}"><span class="longo">${t}</span><span class="curto" aria-hidden="true">${c}</span></button>`).join("");
  el.querySelectorAll("button").forEach(b => b.addEventListener("click", () => { estado.filtroStatus = b.dataset.v; filtros(); fila(); }));
  const orgaos = [...new Set(estado.exemplos.map(e => e.sonnet))].sort();
  const sel = document.getElementById("filtro-orgao");
  if (!sel.options.length) {
    sel.innerHTML = `<option value="todos">Todos os órgãos</option>` + orgaos.map(o => `<option value="${o}">${o}</option>`).join("");
    sel.addEventListener("change", () => { estado.filtroOrgao = sel.value; fila(); });
  }
}
function fila() {
  const lista = visiveis(), el = document.getElementById("fila");
  if (!lista.length) { el.innerHTML = `<p class="vazio">Nenhum pedido com esses filtros.</p>`; return; }
  el.innerHTML = lista.map(e => {
    const s = statusDe(e);
    return `<button type="button" class="item" role="option" data-id="${e.id}" aria-selected="${e.id === estado.selecionado}">
      <span class="status ${s.cls}">${s.txt}</span>
      <span class="item-topo"><span class="item-orgao">${e.sonnet ?? "—"}</span><span class="item-id">${e.id}</span></span>
      <span class="item-texto">${esc(e.texto.slice(0, 220))}</span></button>`;
  }).join("");
  el.querySelectorAll(".item").forEach(b => b.addEventListener("click", () => selecionar(b.dataset.id, true)));
}
function esc(s) { return s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
function destacar(texto, trecho) {
  const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const i = trecho ? norm(texto).indexOf(norm(trecho)) : -1;
  if (i < 0) return [esc(texto), false];
  return [esc(texto.slice(0, i)) + "<mark>" + esc(texto.slice(i, i + trecho.length)) + "</mark>" + esc(texto.slice(i + trecho.length)), true];
}
function selecionar(id, abrir, animar = true) {
  estado.selecionado = id;
  document.querySelectorAll(".item").forEach(b => b.setAttribute("aria-selected", b.dataset.id === id));
  const e = estado.exemplos.find(x => x.id === id), el = document.getElementById("detalhe");
  if (!e) { el.innerHTML = ""; return; }
  const s = statusDe(e), [html, achou] = destacar(e.texto, e.trecho), erro = e.sonnet !== e.rotulo;
  const orgaos = estado.holdout.orgaos;
  el.innerHTML = `
    <button type="button" class="btn secundario voltar" id="voltar">← Voltar à fila</button>
    <div class="det-cabeca"><span class="status ${s.cls}">${s.txt}</span><span class="item-id">pedido ${e.id}${e.ao_vivo ? " · novo" : ""}</span></div>
    <p class="det-orgao">${e.sonnet ?? "—"}</p>
    <p class="det-motivo">${e.motivo}</p>
    ${erro && e.rotulo ? `<p class="det-erro"><span class="status erro">erro real da IA</span>O órgão que de fato respondeu (gabarito) foi <strong>${e.rotulo}</strong>. Este pedido está aqui de propósito.</p>` : ""}
    <div class="texto">${html}</div>
    <p class="ajuda">${achou ? "Destacado: o trecho que a IA citou como motivo." : "O trecho citado pela IA não aparece literalmente no texto."} Dados pessoais aparecem como [NOME], [CPF] etc.</p>
    <dl class="campos">
      <div><dt>Órgão sugerido</dt><dd>${e.sonnet ?? "—"}</dd></div>
      <div><dt>Confiança da IA</dt><dd>${NOME_CONF[e.confianca] ?? "—"}</dd></div>
      <div><dt>Segunda opinião (ML)</dt><dd>${e.ml} <span class="num">p = ${br(e.p_ml, 2)}</span></dd></div>
      <div><dt>Decisão</dt><dd>${e.status === "encaminhado automaticamente" ? "encaminhar sem pessoa" : "passar para um servidor"}</dd></div>
      ${e.rotulo ? `<div><dt>Órgão que de fato respondeu (gabarito)</dt><dd>${e.rotulo}</dd></div>` : ""}
      ${e.reencaminhado ? `<div><dt>Histórico</dt><dd>foi reencaminhado</dd></div>` : ""}
    </dl>
    ${e.justificativa ? `<p class="justificativa">Justificativa da IA: ${esc(e.justificativa)}</p>` : ""}
    <div class="acoes">
      <button type="button" class="btn primario" id="confirmar">Confirmar</button>
      <label class="sr" for="corrigir">Corrigir para</label>
      <select id="corrigir" class="pilula-select"><option value="">Corrigir para…</option>${orgaos.filter(o => o !== e.sonnet).map(o => `<option>${o}</option>`).join("")}</select>
      <span class="confirmacao" id="confirmacao" hidden></span>
    </div>`;
  el.scrollTop = 0;
  if (animar && el.animate && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    el.animate([{ opacity: 0.4 }, { opacity: 1 }], { duration: 120, easing: "ease-out" });
  }
  const avisa = t => { const c = document.getElementById("confirmacao"); c.hidden = false; c.textContent = t; };
  document.getElementById("confirmar").addEventListener("click", () => { estado.decisoes[e.id] = { tipo: "confirmado" }; fila(); avisa("Confirmado (demonstração: nada é salvo)."); });
  document.getElementById("corrigir").addEventListener("change", ev => {
    if (!ev.target.value) return;
    estado.decisoes[e.id] = { tipo: "corrigido", orgao: ev.target.value }; fila(); avisa(`Corrigido para ${ev.target.value} (demonstração: nada é salvo).`);
  });
  document.getElementById("voltar").addEventListener("click", () => {
    document.querySelector(".mesa").classList.remove("com-detalhe");
    const item = document.querySelector(`.item[data-id="${e.id}"]`);
    if (item) { item.scrollIntoView({ block: "center" }); item.focus({ preventScroll: true }); }
  });
  const celular = window.matchMedia("(max-width: 760px)").matches;
  if (abrir) document.querySelector(".mesa").classList.add("com-detalhe");
  if (abrir && celular) { el.setAttribute("tabindex", "-1"); el.scrollIntoView({ block: "start" }); el.focus({ preventScroll: true }); }
}
function teclado(ev) {
  if (ev.target.closest("input, textarea, select") || document.getElementById("vista-mesa").hidden) return;
  if (ev.key !== "j" && ev.key !== "k") return;
  const lista = visiveis(), i = lista.findIndex(e => e.id === estado.selecionado);
  const j = Math.min(lista.length - 1, Math.max(0, (i < 0 ? 0 : i) + (ev.key === "j" ? 1 : -1)));
  if (lista[j]) { selecionar(lista[j].id, false); document.querySelector(`.item[data-id="${lista[j].id}"]`)?.scrollIntoView({ block: "nearest" }); }
}

// ---------- abas ----------
function abas() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const mostrar = (tab, foco) => {
    tabs.forEach(t => {
      const ativo = t === tab;
      t.setAttribute("aria-selected", ativo); t.tabIndex = ativo ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !ativo;
    });
    if (foco) tab.focus();
    history.replaceState(null, "", tab.id === "aba-painel" ? "#painel" : location.pathname + location.search);
  };
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => mostrar(t, false));
    t.addEventListener("keydown", ev => {
      if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
      ev.preventDefault();
      mostrar(tabs[(i + (ev.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length], true);
    });
  });
  if (location.hash === "#painel") mostrar(document.getElementById("aba-painel"), false);
}

// ---------- modo ao vivo (só com o servidor local) ----------
async function aoVivo() {
  if (!["localhost", "127.0.0.1"].includes(location.hostname)) return;  // o site público não tem modo ao vivo
  try {
    const r = await fetch("api/status", { cache: "no-store" });
    if (!r.ok) return;
    const st = await r.json();
    if (!st.ao_vivo) return;
  } catch (e) { return; }
  document.getElementById("ao-vivo").hidden = false;
  document.getElementById("classificar").addEventListener("click", async () => {
    const texto = document.getElementById("novo-texto").value.trim(), info = document.getElementById("ao-vivo-status");
    if (!texto) return;
    info.textContent = "Mascarando e consultando o modelo…";
    try {
      const r = await fetch("api/classificar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto }) });
      const d = await r.json();
      if (!r.ok) { info.textContent = d.erro || "Erro."; return; }
      estado.exemplos.unshift(d);
      info.textContent = `Classificado. Custo desta chamada: US$ ${br(d.custo_usd, 4)}.`;
      estado.filtroStatus = "todos"; estado.filtroOrgao = "todos"; document.getElementById("filtro-orgao").value = "todos";
      filtros(); fila(); selecionar(d.id, true);
    } catch (e) { info.textContent = "Não foi possível falar com o servidor local."; }
  });
}

// ---------- início ----------
async function iniciar() {
  document.getElementById("tema").addEventListener("click", () => {
    const escuro = getComputedStyle(document.documentElement).colorScheme === "dark";
    const novo = escuro ? "light" : "dark";
    document.documentElement.dataset.theme = novo;
    try { localStorage.setItem("mesa-tema", novo); } catch (e) {}
  });
  const [h, ex] = await Promise.all([fetch("dados/holdout.json").then(r => r.json()), fetch("dados/exemplos.json").then(r => r.json())]);
  estado.holdout = h; estado.exemplos = ex.exemplos;
  const numeros = { pct_errado: pct(h.dor.pct_errado / 100), atraso: `${h.dor.atraso_dias} dias`, erro_1pct: pct(h.resultado_1pct.erro, 2),
                    n_pedidos: String(h.pedidos.length), periodo: h.periodo_texto,
                    n_exemplos: String(estado.exemplos.length) };
  document.querySelectorAll("[data-n]").forEach(el => { el.textContent = numeros[el.dataset.n]; });
  painel(); filtros(); fila();
  if (window.matchMedia("(min-width: 761px)").matches && estado.exemplos.length) selecionar(estado.exemplos[0].id, false, false);
  abas();
  document.addEventListener("keydown", teclado);
  aoVivo();
}
iniciar();
