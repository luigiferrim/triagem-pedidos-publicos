"""Gera report.html (gráficos) a partir dos JSON em results/. Nenhum número é escrito à mão aqui.

Uso: python -m triagem.relatorio   (ou make relatorio)
"""
import json

from triagem import config

R = config.RESULTS


def _ler(nome):
    return json.loads((R / nome).read_text())


def _seg(s_por_1000: float) -> str:
    return f"{s_por_1000:.2f} s por 1.000 pedidos".replace(".", ",")


def dados() -> dict:
    dor, m2, m3, m4, err = _ler("dor.json"), _ler("marco2.json"), _ler("marco3.json"), _ler("marco4.json"), _ler("erros_lado_a_lado.json")
    fc = dor["federal_concluida"]
    atraso = dor["federal_concluida_atraso"]

    def linha(nome, rotulo, t, custo, tempo):
        s = t["subgrupos"]
        return {"nome": nome, "rotulo": rotulo, "acuracia": t["acuracia"], "ic": t["acuracia_ic95"], "f1": t["f1_macro"],
                "cita": s["cita_sigla_literal"]["acuracia"], "n_cita": s["cita_sigla_literal"]["n"],
                "nao_cita": s["nao_cita_sigla_literal"]["acuracia"], "n_nao_cita": s["nao_cita_sigla_literal"]["n"],
                "reenc": f'{s["reencaminhados"]["acertos"]} de {s["reencaminhados"]["n"]}',
                "custo_1000": custo, "tempo": tempo}

    ab = m2["abordagens"]
    abordagens = [
        linha("regras", "Regras", ab["regras"]["test"], 0.0, _seg(ab["regras"]["test"]["segundos_por_1000"])),
        linha("ml", "ML clássico", ab["ml"]["test"], 0.0, _seg(ab["ml"]["test"]["segundos_por_1000"])),
    ]
    for ap, rot in (("haiku", "Claude Haiku 5.5"), ("sonnet", "Claude Sonnet 5.5")):
        t = m3["modelos"][ap]["test"]
        abordagens.append(linha(ap, rot, t, t["custo_por_1000_usd"], f'{t["latencia_mediana_s"]:.1f} s por pedido (mediana)'.replace(".", ",")))

    rotulos = {"sonnet": "Sonnet", "haiku": "Haiku", "ml": "ML", "ml_regras": "ML + regras"}
    curvas = {e: {"rotulo": rotulos[e], "pontos": [[p["cobertura"], p["erro"]] for p in r["curva_teste"]],
                  "sem_abstencao": r["sem_abstencao_teste"]["erro"]}
              for e, r in m4["estrategias"].items()}
    meta = str(m4["meta_recomendada"])
    pontos_meta = {e: r["por_meta"][meta]["teste"] for e, r in m4["estrategias"].items() if r["por_meta"].get(meta)}
    rec = m4["recomendacao"]
    return {
        "dor": {"pct_errado": fc["pct_chegaram_ao_orgao_errado"], "n": fc["n_pedidos"], "n_errado": fc["chegaram_ao_orgao_errado"],
                "atraso": atraso["atraso_extra_mediana_dias"], "med_certo": atraso["chegaram_certo"]["mediana_dias"],
                "med_reenc": atraso["reencaminhados"]["mediana_dias"],
                "pct_reenc_top10": dor["federal_concluida_top10"]["pct_reencaminhados"]},
        "abordagens": abordagens,
        "comparacoes": m3["comparacoes_pareadas"]["test"],
        "curvas": curvas, "meta": m4["meta_recomendada"], "pontos_meta": pontos_meta,
        "rec": rec, "alt": m4.get("alternativa_sem_api"),
        "erros": {"categorias": err["categorias"], "n_sonnet": err["erros_no_teste"]["sonnet"]},
        "gasto_total": m3["gasto_total_usd"],
        "holdout": _ler("holdout_2026_resultado.json"),
        "manchete": _ler("manchete.json"),
        "sp": _ler("marco9_comparacao.json") if (config.RESULTS / "marco9_comparacao.json").exists() else None,
        "fevereiro": ({k: v for k, v in _ler("marco7_fev.json")["v1"]["meta_1pct"].items() if k in ("cobertura", "erro", "erro_ic95")}
                      if (config.RESULTS / "marco7_fev.json").exists() else None),
        "pii": {k: v for k, v in _ler("pii_detector_offline.json").items() if k in ("textos_enviados", "nome_de_pessoa_confirmado_a_mao", "taxa_confirmada_pct")},
    }


ROTULO_CATEGORIA = {
    "sem_pista_no_texto": "Sem pista no texto",
    "vinculacao_institucional": "Vinculação institucional",
    "multi_orgao_ou_rotulo_discutivel": "Mais de um órgão / rótulo discutível",
    "pista_ignorada": "Pista ignorada",
    "fato_inventado": "Fato inventado",
}

PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Triagem de pedidos públicos</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #6f6d68;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100; --ref: #52514e;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #9a988f;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --ref: #c3c2b7;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #9a988f;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --ref: #c3c2b7;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 920px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 28px; line-height: 1.2; margin: 0 0 8px; }
h2 { font-size: 20px; margin: 40px 0 8px; }
p { margin: 8px 0; color: var(--ink-2); max-width: 70ch; }
.lead { font-size: 17px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr)); gap: 12px; margin: 24px 0 8px; }
.tile { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.tile .v { font-size: 32px; font-weight: 600; line-height: 1.1; }
.tile .l { color: var(--ink-2); font-size: 14px; margin-top: 6px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-top: 12px; position: relative; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
.links-topo { font-size: 14px; margin: 0 0 8px; }
.links-topo a { margin-right: 16px; }
td.destaque { font-weight: 600; }
svg text { fill: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
svg .lbl { fill: var(--ink); font-size: 14px; }
svg .lbl2 { fill: var(--ink-2); font-size: 13px; }
.legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px; color: var(--ink-2); margin-bottom: 8px; }
.legend span::before { content: ""; display: inline-block; width: 12px; height: 3px; border-radius: 2px; background: var(--c); margin-right: 6px; vertical-align: middle; }
.legend .dot::before { width: 9px; height: 9px; border-radius: 50%; }
.tip { position: absolute; pointer-events: none; background: var(--surface); color: var(--ink); border: 1px solid var(--border);
       border-radius: 6px; padding: 8px 10px; font-size: 13px; box-shadow: 0 2px 8px rgba(0,0,0,0.12); display: none; white-space: nowrap; z-index: 2; }
table { border-collapse: collapse; width: 100%; font-size: 14px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--grid); vertical-align: top; }
th { color: var(--ink-2); font-weight: 600; }
td.n, th.n { text-align: right; }
.scroll { overflow-x: auto; }
details { margin-top: 8px; font-size: 14px; color: var(--ink-2); }
summary { cursor: pointer; }
.note { font-size: 13px; color: var(--muted); }
strong { color: var(--ink); }
</style>
</head>
<body>
<main>
<p class="links-topo"><a href="https://mesa-triagem.vercel.app/">Mesa de triagem (demonstração)</a><a href="https://github.com/luigiferrim/triagem-pedidos-publicos">Repositório</a></p>
<h1>Triagem de pedidos públicos</h1>
<p class="lead">Dá para triar pedidos de cidadãos com segurança? Quanto da fila pode ser automatizado sem aumentar o erro? Teste com pedidos LAI federais de 2025 (CGU), como análogo de pedidos municipais.</p>

<div class="tiles" id="tiles"></div>

<h2>Quatro abordagens no mesmo teste</h2>
<p>500 pedidos de novembro e dezembro de 2025, separados antes de qualquer modelo. Barras: acurácia; traço: intervalo de 95%.</p>
<div class="card" id="c-acur"><div class="tip"></div></div>
<div class="scroll" style="margin-top:12px"><table id="t-abord"></table></div>
<p class="note" id="n-pareada"></p>

<h2>Quanto vem só da sigla do órgão</h2>
<p>Pedidos que citam a sigla (ANVISA, INSS…) são fáceis para todos. A diferença aparece nos que não citam.</p>
<div class="card" id="c-sigla"><div class="tip"></div></div>

<h2>Cobertura × erro: onde a máquina para</h2>
<p>Cada linha ordena os pedidos pela confiança da estratégia. Ir para a direita é deixar a máquina encaminhar mais pedidos sozinha; o eixo vertical é o erro entre esses pedidos. Os limiares foram escolhidos no dev; o gráfico mostra o teste.</p>
<div class="card" id="c-curva"><div class="tip"></div></div>
<details><summary>Ver os pontos escolhidos em tabela</summary><div class="scroll"><table id="t-pontos"></table></div></details>
<p class="note" id="p-pre"></p>

<h2>Confirmação em dados novos: janeiro de 2026</h2>
<p>A meta de 1% foi adotada depois de ver o teste. Por isso o limiar foi congelado e medido uma vez em 500 pedidos de janeiro de 2026, com o hash registrado antes de rodar.</p>
<div class="scroll"><table id="t-holdout"></table></div>
<p id="p-rec"></p>

<h2>Custo do erro, por 1.000 pedidos (março a outubro de 2026)</h2>
<div class="scroll"><table id="t-custo"></table></div>
<p class="note" id="p-premissas"></p>
<p class="note" id="p-fevereiro"></p>

<h2 id="h-sp" hidden>Numa prefeitura: São Paulo</h2>
<div class="scroll"><table id="t-sp"></table></div>
<p class="note" id="p-sp"></p>

<h2>O que o melhor modelo errou</h2>
<p id="p-erros"></p>
<div class="card" id="c-erros"><div class="tip"></div></div>

<h2>Limites</h2>
<p>Pedidos federais como análogo de municipais. Rótulo = órgão que respondeu. Teste estratificado (mínimo de 25 por órgão). Erro da triagem humana não medido. Nome de pessoa escapou da máscara em <span id="pii-n"></span> textos enviados à API. Detalhes no README e em DADOS.md.</p>
</main>
<script>
const D = __DADOS__;
const CAT = __CATEGORIAS__;
const COR = {sonnet: "var(--s1)", haiku: "var(--s2)", ml: "var(--s3)", ml_regras: "var(--s4)", regras: "var(--s4)"};
const arred = (v, d) => Math.round(v * 10 ** d + 1e-9) / 10 ** d;
const pct = (x, d = 1) => arred(100 * x, d).toLocaleString("pt-BR", {minimumFractionDigits: d, maximumFractionDigits: d}) + "%";
const num = (x, d = 0) => x.toLocaleString("pt-BR", {minimumFractionDigits: d, maximumFractionDigits: d});
const usd = x => x === 0 ? "≈ 0" : "US$ " + num(x, 2);
const NS = "http://www.w3.org/2000/svg";
const desenhos = [];
const largura = card => Math.max(300, Math.min(900, card.clientWidth - 32));
function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
function txt(parent, x, y, s, attrs = {}) { const t = el("text", {x, y, ...attrs}, parent); t.textContent = s; return t; }
function tipOn(card, html, ev) {
  const tip = card.querySelector(".tip"), r = card.getBoundingClientRect();
  tip.innerHTML = html; tip.style.display = "block";
  let x = ev.clientX - r.left + 14, y = ev.clientY - r.top + 14;
  if (x + tip.offsetWidth > r.width - 4) x = ev.clientX - r.left - tip.offsetWidth - 14;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
function tipOff(card) { card.querySelector(".tip").style.display = "none"; }

// Indicadores
const H = D.holdout, hr = H.regras_congeladas["sonnet_0.01"].holdout;
document.getElementById("tiles").innerHTML = [
  [pct(D.dor.pct_errado / 100, 2), `dos pedidos federais chegam ao órgão errado (${num(D.dor.n_errado)} de ${num(D.dor.n)}, 2025)`],
  [`+${num(D.dor.atraso)} dias`, `de atraso mediano quando o pedido é reencaminhado (${D.dor.med_reenc} contra ${D.dor.med_certo})`],
  [pct(D.manchete.acumulado.cobertura, 1), `da fila sem pessoa em pedidos novos de março a outubro de 2026, com ${pct(D.manchete.acumulado.erro, 2)} de erro (pode variar de ${pct(D.manchete.acumulado.erro_ic95[0])} a ${pct(D.manchete.acumulado.erro_ic95[1])}; sem o lote do INSS, ${pct(D.manchete.sem_o_lote_do_inss.erro, 2)}; meta de 1% não atingida)`],
  [usd(D.manchete.acumulado.custo_por_1000_usd), "de API por 1.000 pedidos (preços oficiais)"],
].map(([v, l]) => `<div class="tile"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");

// Acurácia com IC
desenhos.push(function () {
  const card = document.getElementById("c-acur");
  card.querySelectorAll("svg").forEach(x => x.remove()); const W = largura(card), estreito = W < 560;
  const A = D.abordagens, rowH = 40, top = 8, left = estreito ? 118 : 150, right = estreito ? 52 : 70, H = top + A.length * rowH + 28;
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Acurácia no teste por abordagem"}, card);
  const x = v => left + (W - left - right) * v;
  for (const g of [0, .25, .5, .75, 1]) {
    el("line", {x1: x(g), x2: x(g), y1: top, y2: H - 24, stroke: g === 0 ? "var(--axis)" : "var(--grid)", "stroke-width": 1}, svg);
    txt(svg, x(g), H - 8, pct(g, 0), {"text-anchor": "middle"});
  }
  A.forEach((a, i) => {
    const y = top + i * rowH + 8, h = 22;
    txt(svg, left - 10, y + 16, a.rotulo, {"text-anchor": "end", class: "lbl"});
    const r = el("rect", {x: x(0), y, width: x(a.acuracia) - x(0), height: h, rx: 4, fill: "var(--s1)", opacity: a.nome === "sonnet" ? 1 : 0.55}, svg);
    el("line", {x1: x(a.ic[0]), x2: x(a.ic[1]), y1: y + h / 2, y2: y + h / 2, stroke: "var(--ink)", "stroke-width": 2, "stroke-linecap": "round"}, svg);
    txt(svg, x(a.ic[1]) + 8, y + 16, pct(a.acuracia), {class: "lbl"});
    const hit = el("rect", {x: 0, y: y - 6, width: W, height: rowH, fill: "transparent"}, svg);
    hit.addEventListener("mousemove", ev => tipOn(card, `<strong>${a.rotulo}</strong><br>Acurácia ${pct(a.acuracia)} (IC 95% ${pct(a.ic[0])}–${pct(a.ic[1])})<br>F1 macro ${num(a.f1, 3)}`, ev));
    hit.addEventListener("mouseleave", () => tipOff(card));
  });
  document.getElementById("t-abord").innerHTML = `<tr><th>Abordagem</th><th class="n">Acurácia [IC 95%]</th><th class="n">F1 macro</th><th class="n">Reencaminhados certos</th><th class="n">Custo por 1.000</th><th>Tempo</th><th>Explicação</th></tr>` +
    A.map(a => `<tr><td>${a.rotulo}</td><td class="n">${pct(a.acuracia)} [${pct(a.ic[0])}–${pct(a.ic[1])}]</td><td class="n">${num(a.f1, 3)}</td><td class="n">${a.reenc}</td><td class="n">${usd(a.custo_1000)}</td><td>${a.tempo}</td><td>${
      {regras: "palavras encontradas", ml: "termos de maior peso", haiku: "trecho do pedido + frase", sonnet: "trecho do pedido + frase"}[a.nome]}</td></tr>`).join("");
  const c = D.comparacoes;
  document.getElementById("n-pareada").textContent =
    `Comparação pareada (mesmos 500 pedidos, bootstrap): Sonnet − ML = ${num(c.sonnet_vs_ml.diferenca_pp, 1)} pontos [${num(c.sonnet_vs_ml.ic95_pp[0], 1)} a ${num(c.sonnet_vs_ml.ic95_pp[1], 1)}]; ` +
    `Haiku − ML = ${num(c.haiku_vs_ml.diferenca_pp, 1)} [${num(c.haiku_vs_ml.ic95_pp[0], 1)} a ${num(c.haiku_vs_ml.ic95_pp[1], 1)}], empate estatístico.`;
});

// Cita × não cita
desenhos.push(function () {
  const card = document.getElementById("c-sigla");
  card.querySelectorAll("svg").forEach(x => x.remove()); const W = largura(card), estreito = W < 560;
  const A = D.abordagens, rowH = 36, top = 34, left = estreito ? 118 : 150, right = 30, H = top + A.length * rowH + 24;
  const leg = document.createElement("div"); leg.className = "legend";
  leg.innerHTML = `<span class="dot" style="--c:var(--s1)">Cita a sigla (${A[0].n_cita} pedidos)</span><span class="dot" style="--c:var(--s2)">Não cita (${A[0].n_nao_cita})</span>`;
  if (!card.querySelector(".legend")) card.insertBefore(leg, card.firstChild);
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Acurácia com e sem sigla"}, card);
  const lo = 0.5, x = v => left + (W - left - right) * (v - lo) / (1 - lo);
  for (const g of [.5, .6, .7, .8, .9, 1]) {
    el("line", {x1: x(g), x2: x(g), y1: top - 10, y2: H - 22, stroke: "var(--grid)", "stroke-width": 1}, svg);
    txt(svg, x(g), H - 6, pct(g, 0), {"text-anchor": "middle"});
  }
  A.forEach((a, i) => {
    const y = top + i * rowH;
    txt(svg, left - 10, y + 4, a.rotulo, {"text-anchor": "end", class: "lbl"});
    el("line", {x1: x(a.nao_cita), x2: x(a.cita), y1: y, y2: y, stroke: "var(--axis)", "stroke-width": 2}, svg);
    for (const [v, cor, nome] of [[a.cita, "var(--s1)", "cita"], [a.nao_cita, "var(--s2)", "não cita"]]) {
      const c = el("circle", {cx: x(v), cy: y, r: 6, fill: cor, stroke: "var(--surface)", "stroke-width": 2}, svg);
      const hit = el("circle", {cx: x(v), cy: y, r: 14, fill: "transparent"}, svg);
      hit.addEventListener("mousemove", ev => tipOn(card, `<strong>${a.rotulo}</strong>, ${nome}: ${pct(v)}`, ev));
      hit.addEventListener("mouseleave", () => tipOff(card));
    }
    txt(svg, x(a.nao_cita) - 10, y + 4, pct(a.nao_cita, 0), {"text-anchor": "end", class: "lbl2"});
  });
});

// Curva cobertura × erro
desenhos.push(function () {
  const card = document.getElementById("c-curva");
  card.querySelectorAll("svg").forEach(x => x.remove()); const W = largura(card), estreito = W < 560;
  const ordem = ["sonnet", "haiku", "ml", "ml_regras"], C = D.curvas;
  const leg = document.createElement("div"); leg.className = "legend";
  leg.innerHTML = ordem.map(e => `<span style="--c:${COR[e]}">${C[e].rotulo}</span>`).join("") +
    `<span style="--c:var(--ref)">Hoje: ${pct(D.dor.pct_reenc_top10 / 100, 2)} reencaminhados (10 órgãos)</span>`;
  if (!card.querySelector(".legend")) card.insertBefore(leg, card.firstChild);
  const H = estreito ? 340 : 430, L = estreito ? 40 : 56, R = estreito ? 78 : 110, T = 30, B = 44, ymax = 0.12, xmin = 0.3;
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Curva de cobertura por erro no teste"}, card);
  const x = v => L + (W - L - R) * (v - xmin) / (1 - xmin), y = v => T + (H - T - B) * (1 - Math.min(v, ymax) / ymax);
  for (const g of [0, .02, .04, .06, .08, .10, .12]) {
    el("line", {x1: L, x2: W - R, y1: y(g), y2: y(g), stroke: g === 0 ? "var(--axis)" : "var(--grid)", "stroke-width": 1}, svg);
    txt(svg, L - 8, y(g) + 4, pct(g, 0), {"text-anchor": "end"});
  }
  for (const g of (estreito ? [.4, .6, .8, 1] : [.3, .4, .5, .6, .7, .8, .9, 1])) txt(svg, x(g), H - B + 18, pct(g, 0), {"text-anchor": g === 1 ? "end" : "middle"});
  txt(svg, (L + W - R) / 2, H - 4, "Cobertura: pedidos encaminhados sem pessoa", {"text-anchor": "middle", class: "lbl2"});
  txt(svg, 4, 14, "Erro entre os encaminhados sem pessoa", {class: "lbl2"});
  const hoje = D.dor.pct_reenc_top10 / 100;
  el("line", {x1: L, x2: W - R, y1: y(hoje), y2: y(hoje), stroke: "var(--ref)", "stroke-width": 1.5, "stroke-dasharray": "5 4"}, svg);
  const series = {}, rotulosFim = [{y: y(hoje), s: "hoje"}];
  for (const e of [...ordem].reverse()) {
    const pts = C[e].pontos.filter(p => p[0] >= xmin);
    series[e] = pts;
    el("path", {d: pts.map((p, i) => (i ? "L" : "M") + x(p[0]).toFixed(1) + " " + y(p[1]).toFixed(1)).join(" "),
      fill: "none", stroke: COR[e], "stroke-width": 2, "stroke-linejoin": "round"}, svg);
    const fim = pts[pts.length - 1];
    rotulosFim.push({y: y(fim[1]), s: C[e].rotulo});
  }
  // Rótulos no fim das linhas, afastados para não colidir (mínimo de 15 px).
  rotulosFim.sort((a, b) => a.y - b.y);
  for (let i = 1; i < rotulosFim.length; i++) rotulosFim[i].y = Math.max(rotulosFim[i].y, rotulosFim[i - 1].y + 15);
  for (const r of rotulosFim) txt(svg, W - R + 8, r.y + 4, r.s, {class: "lbl2"});
  for (const [e, p] of Object.entries(D.pontos_meta)) {
    const c = el("circle", {cx: x(p.cobertura), cy: y(p.erro), r: e === D.rec.estrategia ? 7 : 5, fill: COR[e], stroke: "var(--surface)", "stroke-width": 2}, svg);
  }
  const rp = D.rec.teste;
  if (!estreito) {  // em tela estreita a anotação cruzaria as linhas; o ponto continua marcado e o texto está abaixo
    const ax = x(0.31), ay = y(0.045);
    el("line", {x1: ax + 4, y1: ay + 18, x2: x(rp.cobertura) - 8, y2: y(rp.erro) - 6, stroke: "var(--ink-2)", "stroke-width": 1}, svg);
    txt(svg, ax, ay, "Ponto recomendado, no teste de 2025:", {class: "lbl"});
    txt(svg, ax, ay + 16, `${pct(rp.cobertura, 0)} sem pessoa, ${pct(rp.erro)} de erro`, {class: "lbl"});
  }
  const cross = el("line", {y1: T, y2: H - B, stroke: "var(--axis)", "stroke-width": 1, visibility: "hidden"}, svg);
  const hit = el("rect", {x: L, y: T, width: W - L - R, height: H - T - B, fill: "transparent"}, svg);
  hit.addEventListener("mousemove", ev => {
    const r = svg.getBoundingClientRect(), vx = xmin + (1 - xmin) * (((ev.clientX - r.left) * W / r.width) - L) / (W - L - R);
    cross.setAttribute("x1", x(vx)); cross.setAttribute("x2", x(vx)); cross.setAttribute("visibility", "visible");
    const linhas = ordem.map(e => {
      const pts = series[e]; let best = pts[0];
      for (const p of pts) if (Math.abs(p[0] - vx) < Math.abs(best[0] - vx)) best = p;
      return `<span style="color:${COR[e]}">●</span> ${C[e].rotulo}: ${pct(best[0], 0)} cobertos, erro ${pct(best[1])}`;
    });
    tipOn(card, `<strong>Cobertura ≈ ${pct(vx, 0)}</strong><br>` + linhas.join("<br>"), ev);
  });
  hit.addEventListener("mouseleave", () => { tipOff(card); cross.setAttribute("visibility", "hidden"); });

  document.getElementById("t-pontos").innerHTML = `<tr><th>Estratégia (meta de ${pct(D.meta, 0)} no dev)</th><th class="n">Cobertura</th><th class="n">Erro [IC 95%]</th><th class="n">Fila humana</th><th class="n">Erro sem abstenção</th></tr>` +
    ordem.filter(e => D.pontos_meta[e]).map(e => { const p = D.pontos_meta[e]; return `<tr><td>${C[e].rotulo}</td><td class="n">${pct(p.cobertura)}</td><td class="n">${pct(p.erro)} [${pct(p.erro_ic95[0])}–${pct(p.erro_ic95[1])}]</td><td class="n">${p.fila_humana} de 500</td><td class="n">${pct(C[e].sem_abstencao)}</td></tr>`; }).join("");
  const rotH = {"sonnet_0.01": "Sonnet, meta de 1% (recomendada)", "sonnet_0.02": "Sonnet, meta de 2% (combinada antes)", "ml_0.01": "ML, meta de 1%", "ml_0.02": "ML, meta de 2%"};
  document.getElementById("t-holdout").innerHTML = `<tr><th>Regra congelada</th><th class="n">Sem pessoa</th><th class="n">Erro [IC 95%]</th><th>Meta</th><th class="n">Reencaminhados certos</th><th class="n">No teste de 2025</th></tr>` +
    Object.entries(D.holdout.regras_congeladas).map(([k, v]) => { const h = v.holdout; return `<tr><td>${rotH[k]}</td><td class="n">${pct(h.cobertura)}</td><td class="n">${pct(h.erro, 2)} [${pct(h.erro_ic95[0], 2)}–${pct(h.erro_ic95[1], 2)}]</td><td>${h.meta_cumprida ? "cumprida" : "não cumprida"}</td><td class="n">${h.reencaminhados_cobertos_certos} de ${h.reencaminhados_cobertos}</td><td class="n">${pct(v.teste_2025.cobertura)}, erro ${pct(v.teste_2025.erro)}</td></tr>`; }).join("");
  const hr1 = D.holdout.regras_congeladas["sonnet_0.01"].holdout;
  document.getElementById("p-rec").innerHTML = `<strong>Recomendação:</strong> o Sonnet encaminha sozinho quando declara confiança alta, ou média com o ML concordando (probabilidade ≥ ${num(D.rec.limiar[2], 4)}). ` +
    `Em janeiro de 2026: ${pct(hr1.cobertura)} da fila sem pessoa, ${pct(hr1.erro, 2)} de erro (${hr1.erros} de ${hr1.cobertos}); a meta de 1% foi cumprida no ponto, mas o intervalo vai até ${pct(hr1.erro_ic95[1], 1)}. ` +
    `Os outros ${hr1.fila_humana} pedidos vão para uma pessoa; neles a máquina acertaria só ${pct(hr1.acerto_que_a_maquina_teria_na_fila, 0)}.`;
  document.getElementById("p-pre").textContent = "Transparência: " + D.rec.aviso + " A confirmação em dados novos está logo abaixo.";
});

// Custo do erro: os mesmos números do topo do site, README e DECISAO (results/manchete.json, contagem direta)
(function () {
  const M = D.manchete, A = M.acumulado, H = M.historico_jan_fev.acumulado;
  const faixa = (v, f) => `${num(v, 0)} [${num(f[0], 0)}–${num(f[1], 0)}]`;
  const col = m => [num(m.por_1000.sem_pessoa), num(m.por_1000.para_pessoa), faixa(m.por_1000.erros, m.por_1000.erros_faixa_ic95),
                    `${pct(m.erro, 2)} [${pct(m.erro_ic95[0], 2)}–${pct(m.erro_ic95[1], 2)}]`, num(m.por_1000.dias_de_atraso), usd(m.custo_por_1000_usd)];
  const nomes = ["Encaminhados sem pessoa", "Para uma pessoa (erro não medido)", "Erros de destino na parte automática", "Erro entre os encaminhados sem pessoa", "Dias de atraso somados", "Custo de API"];
  const hoje = ["0", "—", `${num(M.hoje_por_1000)} reencaminhados`, "—", num(M.hoje_dias_de_atraso_por_1000), "0"];
  const cols = [hoje, col(A), col(H)];
  document.getElementById("t-custo").innerHTML = `<tr><th></th><th>Hoje (o cidadão escolhe)</th><th>Com a recomendação, mar–out</th><th>Histórico: jan+fev</th></tr>` +
    nomes.map((n, i) => `<tr><td>${n}</td>${cols.map((c, k) => `<td${k === 1 ? ' class="destaque"' : ""}>${c[i]}</td>`).join("")}</tr>`).join("");
  document.getElementById("p-premissas").textContent = `Pedidos dos 10 órgãos. ${M.metodo[0].toUpperCase() + M.metodo.slice(1)}. Entre colchetes, a faixa pelo intervalo de 95%. ${M.frase} Cada erro atrasa ${num(M.atraso_por_erro_dias)} dias (diferença entre as medianas de prazo).`;
  document.getElementById("pii-n").textContent = `${D.pii.nome_de_pessoa_confirmado_a_mao} de ${num(D.pii.textos_enviados)} (${num(D.pii.taxa_confirmada_pct, 2)}%, limite inferior)`;
})();

// Marco 9: Prefeitura de São Paulo ao lado do federal (results/marco9_comparacao.json)
if (D.sp) (function () {
  const F = D.sp.federal, S = D.sp.sao_paulo, r = a => `${pct(a.cobertura)} sem pessoa; erro ${pct(a.erro, 2)} [${pct(a.erro_ic95[0])}–${pct(a.erro_ic95[1])}]; ${num(a.erros_por_1000, 0)} por 1.000`;
  document.getElementById("h-sp").hidden = false;
  document.getElementById("t-sp").innerHTML = `<tr><th></th><th>Federal</th><th>São Paulo</th></tr>` + [
    ["Hoje: pedidos que trocam de órgão, por 1.000", `${F.dor_reencaminhados_por_1000} (reencaminhados)`, `${S.dor_encaminhamento_deferido_2024_por_1000} (encaminhamento deferido, 2024)`],
    ["Acerto do Sonnet, sem abstenção", pct(F.acuracia_sonnet_teste_2025), pct(S.acuracia_sonnet_teste_2025)],
    ["Acerto do modelo estatístico", pct(F.acuracia_ml_teste_2025), pct(S.acuracia_ml_teste_2025)],
    ["Regra principal de SP (escolhida no dev de SP)", "—", r(S.regra_sp_escolhida_no_dev)],
    ["Regra da v1 federal (comparação registrada)", r(F.regra_v1_teste_2025) + " (teste de 2025); " + r(F.regra_v1_mar_out_2026) + " (mar–out/2026)", r(S.regra_v1_federal)],
  ].map(l => `<tr>${l.map((c, i) => i ? `<td>${c}</td>` : `<td>${c}</td>`).join("")}</tr>`).join("");
  document.getElementById("p-sp").textContent = `O limiar de SP veio de um dev pequeno (${S.regra_sp_no_dev.erros} erros em ${S.regra_sp_no_dev.cobertos} encaminhados) e é instável. As duas regras tiveram os mesmos erros no teste de SP; a federal cobriu mais. No teste federal equivalente, a mesma regra errou menos de 1%. Ressalvas: ${D.sp.ressalvas}. Detalhes no README, §4d.`;
})();

// Erros
desenhos.push(function () {
  const card = document.getElementById("c-erros"), E = Object.entries(D.erros.categorias);
  card.querySelectorAll("svg").forEach(x => x.remove()); const W = largura(card), estreito = W < 560;
  document.getElementById("p-erros").textContent = `O Sonnet errou ${D.erros.n_sonnet} dos 500 pedidos. Li 20 deles, sorteados, ao lado do texto. A maioria não é erro de leitura: ou o texto não diz o órgão, ou acertar exige saber a qual órgão uma unidade pertence.`;
  const rowH = estreito ? 46 : 34, left = estreito ? 0 : 270, right = 40, H = E.length * rowH + 8, max = Math.max(...E.map(e => e[1]));
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Categorias dos 20 erros"}, card);
  const x = v => left + (W - left - right) * v / max;
  E.forEach(([k, v], i) => {
    const y0 = i * rowH + 6, y = estreito ? y0 + 18 : y0;
    if (estreito) txt(svg, 0, y0 + 12, CAT[k] || k, {class: "lbl"});   // em tela estreita, o rótulo fica acima da barra
    else txt(svg, left - 10, y + 15, CAT[k] || k, {"text-anchor": "end", class: "lbl"});
    el("rect", {x: x(0), y, width: x(v) - x(0), height: 20, rx: 4, fill: "var(--s1)"}, svg);
    txt(svg, x(v) + 8, y + 15, String(v), {class: "lbl"});
  });
});

// Fevereiro (Marco 7): a mesma regra, sem mudança
if (D.fevereiro) document.getElementById("p-fevereiro").innerHTML =
  `<strong>Fevereiro de 2026:</strong> a mesma regra, sem nenhuma mudança, errou ${pct(D.fevereiro.erro, 2)} na parte automática (IC 95% ${pct(D.fevereiro.erro_ic95[0], 2)}–${pct(D.fevereiro.erro_ic95[1], 2)}), acima da meta de 1%, com ${pct(D.fevereiro.cobertura)} sem pessoa.`;

// Desenha os gráficos na largura real do cartão e de novo quando a janela muda
desenhos.forEach(f => f());
let _espera;
window.addEventListener("resize", () => { clearTimeout(_espera); _espera = setTimeout(() => desenhos.forEach(f => f()), 150); });
</script>
</body>
</html>
"""


def grafico_curva_png(d: dict) -> None:
    """Versão estática da curva para o README (o GitHub não mostra o report.html)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cores = {"sonnet": "#2a78d6", "haiku": "#eb6834", "ml": "#1baf7a", "ml_regras": "#eda100"}
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150)
    for e in ("ml_regras", "ml", "haiku", "sonnet"):
        pts = [p for p in d["curvas"][e]["pontos"] if p[0] >= 0.3]
        ax.plot([100 * p[0] for p in pts], [100 * p[1] for p in pts], color=cores[e], lw=2, label=d["curvas"][e]["rotulo"])
    for e, p in d["pontos_meta"].items():
        ax.scatter(100 * p["cobertura"], 100 * p["erro"], s=70 if e == d["rec"]["estrategia"] else 35, color=cores[e],
                   edgecolor="white", linewidth=1.5, zorder=5)
    hoje = d["dor"]["pct_reenc_top10"]
    ax.axhline(hoje, color="#52514e", lw=1.2, ls="--")
    ax.text(31, hoje + 0.25, f"hoje: {hoje:.2f}% reencaminhados (10 órgãos)".replace(".", ","), color="#52514e", fontsize=9)
    rp = d["rec"]["teste"]
    ax.annotate(f"recomendado, no teste: {100 * rp['cobertura']:.0f}% sem pessoa, {100 * rp['erro']:.1f}% de erro".replace(".", ","),
                xy=(100 * rp["cobertura"], 100 * rp["erro"]), xytext=(32, 4.5), fontsize=9,
                arrowprops={"arrowstyle": "-", "color": "#52514e", "lw": 0.8})
    ax.set_xlim(30, 101); ax.set_ylim(0, 12)
    ax.set_xlabel("Cobertura: % dos pedidos encaminhados sem pessoa (teste)")
    ax.set_ylabel("Erro entre os encaminhados (%)")
    ax.grid(color="#e1e0d9", lw=0.8); ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.legend(frameon=False, loc="upper left", ncol=4, fontsize=9)
    fig.tight_layout()
    fig.savefig(config.RESULTS / "curva_cobertura_erro.png")
    plt.close(fig)


def main() -> None:
    d = dados()
    grafico_curva_png(d)
    html = PAGINA.replace("__DADOS__", json.dumps(d, ensure_ascii=False)).replace(
        "__CATEGORIAS__", json.dumps(ROTULO_CATEGORIA, ensure_ascii=False))
    (config.RAIZ / "report.html").write_text(html, encoding="utf-8")
    print(f"report.html gerado ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
