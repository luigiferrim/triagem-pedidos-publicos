"""Abordagens 3 e 4: Claude Haiku 5.5 e Claude Sonnet 5.5, com o mesmo prompt.

- Prompt fixo (instruções + descrição dos 10 órgãos + 2 exemplos por órgão tirados da amostra de treino),
  marcado para cache de prompt. Só o pedido muda de uma chamada para outra.
- Saída JSON validada por schema: órgão, trecho do pedido que justifica, justificativa curta, confiança.
- Todo texto enviado é o texto mascarado de data/*.jsonl. Antes de cada envio, as regex de dados pessoais
  são aplicadas de novo; se acharem algo, o pedido não é enviado.
- Cache local em cache/<modelo>.jsonl, chave = sha256(corpo da requisição) + id do pedido.
  Rodar de novo não chama a API para o que já está no cache.
- A API não aceita mais `temperature`: a reprodutibilidade vem do cache, não de uma seed.

Preços: https://platform.claude.com/docs/en/about-claude/pricing.md, conferidos em 09/11/2026.
"""
import hashlib
import json
import random
import re
import threading
import time
from datetime import datetime, timezone

from triagem import config
from triagem.pii import encontrar_pii_regex
from triagem.texto import normalizar

MODELOS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"}

# US$ por milhão de tokens. Haiku: preço para prompts de até 100 mil tokens (os nossos têm ~5 mil).
PRECOS = {
    "claude-haiku-5-5": {"entrada": 0.10, "escrita_cache_5m": 0.125, "leitura_cache": 0.01, "saida": 0.50},
    "claude-sonnet-5-5": {"entrada": 2.00, "escrita_cache_5m": 2.50, "leitura_cache": 0.10, "saida": 10.00},
}
FONTE_PRECOS = "https://platform.claude.com/docs/en/about-claude/pricing.md (conferido em 09/11/2026)"

# Descrição neutra de cada órgão (conhecimento público, não tirado do teste).
ORGAOS = {
    "ANEEL": "Agência Nacional de Energia Elétrica: regula geração, transmissão e distribuição de energia elétrica, tarifas, distribuidoras, usinas.",
    "ANVISA": "Agência Nacional de Vigilância Sanitária: registro e fiscalização de medicamentos, alimentos, cosméticos, produtos para saúde, importação sanitária.",
    "BACEN": "Banco Central do Brasil: sistema financeiro, bancos, Pix, câmbio, crédito, Registrato, valores a receber, política monetária.",
    "INSS": "Instituto Nacional do Seguro Social: aposentadorias, pensões, auxílios, benefícios previdenciários e assistenciais, perícias.",
    "MEC": "Ministério da Educação: política educacional, ensino superior e básico, programas educacionais, instituições federais de ensino.",
    "MF": "Ministério da Fazenda (inclui Receita Federal e PGFN): tributos, arrecadação, dívida ativa, política econômica e fiscal, apostas.",
    "MGI": "Ministério da Gestão e da Inovação em Serviços Públicos: servidores federais, concursos (CNU), carreiras, imóveis da União (SPU), gestão pública.",
    "MS": "Ministério da Saúde: SUS, políticas de saúde, vacinação, medicamentos do SUS, programas e dados de saúde pública.",
    "PETROBRAS": "Petróleo Brasileiro S.A.: contratos, licitações, operações de petróleo e gás, refinarias, combustíveis da empresa.",
    "PF": "Polícia Federal: passaportes, investigações e apreensões, armas (porte/registro), migração, segurança privada, antecedentes criminais.",
}
SIGLAS = sorted(ORGAOS)
CONFIANCAS = ["alta", "media", "baixa"]

SCHEMA = {
    "type": "object",
    "properties": {
        "orgao": {"type": "string", "enum": SIGLAS},
        "trecho": {"type": "string", "description": "Trecho copiado literalmente do pedido que justifica a escolha."},
        "justificativa": {"type": "string", "description": "Uma frase curta explicando a escolha."},
        "confianca": {"type": "string", "enum": CONFIANCAS},
    },
    "required": ["orgao", "trecho", "justificativa", "confianca"],
    "additionalProperties": False,
}

EXEMPLOS_POR_ORGAO = 2
MAX_TOKENS = 400


def escolher_exemplos(amostra: list[dict]) -> list[dict]:
    """2 pedidos por órgão da amostra de treino, de tamanho médio, sorteados com seed fixa."""
    rng = random.Random(config.SEED)
    exemplos = []
    for org in SIGLAS:
        candidatos = sorted((r for r in amostra if r["orgao_sigla"] == org and 150 <= len(r["texto"]) <= 600),
                            key=lambda r: int(r["id"]))
        exemplos += rng.sample(candidatos, EXEMPLOS_POR_ORGAO)
    rng.shuffle(exemplos)
    return exemplos


def prompt_sistema(exemplos: list[dict]) -> str:
    linhas = [
        "Você faz a triagem de pedidos de acesso à informação enviados por cidadãos a órgãos do governo federal.",
        "Sua tarefa: indicar para qual destes 10 órgãos o pedido deve ser encaminhado.",
        "",
        "Órgãos:",
        *[f"- {s}: {d}" for s, d in ORGAOS.items()],
        "",
        "Regras:",
        "- Escolha sempre um dos 10 órgãos, o mais provável.",
        "- Em 'trecho', copie literalmente um trecho curto do pedido (até 20 palavras) que justifica a escolha.",
        "- Em 'justificativa', explique em uma frase curta, para um servidor público.",
        "- Em 'confianca', use 'alta' se o pedido é claramente do órgão, 'media' se há outro órgão plausível,"
        " 'baixa' se é um chute.",
        "- Marcadores como [NOME], [CPF] e [EMAIL] substituem dados pessoais removidos.",
        "",
        "Exemplos de pedidos já encaminhados:",
    ]
    for i, e in enumerate(exemplos, 1):
        linhas += [f"<exemplo {i}>", f"Pedido: {e['texto']}", f"Órgão: {e['orgao_sigla']}", f"</exemplo {i}>"]
    return "\n".join(linhas)


def corpo_requisicao(modelo: str, sistema: str, texto: str) -> dict:
    """Corpo da chamada. O prefixo (sistema) é idêntico em todas as chamadas, para o cache de prompt."""
    corpo = {
        "model": modelo,
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": f"Pedido:\n{texto}"}],
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}, "effort": "low"},
    }
    # Sem raciocínio estendido nos dois: classificação curta, mesmo tratamento para os dois modelos.
    corpo["thinking"] = {"type": "between_tools"} if modelo == MODELOS["sonnet"] else {"type": "disabled"}
    return corpo


def chave_cache(corpo: dict, id_pedido: str) -> str:
    bruto = json.dumps(corpo, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest() + ":" + id_pedido


def interpretar(texto_resposta: str | None) -> tuple[dict | None, str | None]:
    """Lê a resposta do modelo. Devolve (dados, erro). Tolera JSON dentro de ```...``` ou com texto em volta.
    Órgão fora da lista, ou campo faltando, é erro (a previsão vira None)."""
    if not texto_resposta or not texto_resposta.strip():
        return None, "vazia"
    t = texto_resposta.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        dados = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if not m:
            return None, "sem_json"
        try:
            dados = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None, "json_invalido"
    if not isinstance(dados, dict):
        return None, "nao_objeto"
    org = str(dados.get("orgao", "")).strip().upper()
    if org not in SIGLAS:
        return None, "orgao_invalido"
    confianca = str(dados.get("confianca", "")).strip().lower().replace("é", "e")
    return {
        "orgao": org,
        "trecho": str(dados.get("trecho", "")).strip(),
        "justificativa": str(dados.get("justificativa", "")).strip(),
        "confianca": confianca if confianca in CONFIANCAS else None,
    }, None


def trecho_esta_no_pedido(trecho: str, texto: str) -> bool:
    """O trecho citado pelo modelo existe mesmo no pedido? (ignora caixa, acento e espaços)"""
    t = normalizar(trecho).strip(" .\"'“”")
    return len(t) >= 5 and t in normalizar(texto)


def custo_usd(modelo: str, uso: dict) -> float:
    p = PRECOS[modelo]
    return (uso.get("input_tokens", 0) * p["entrada"]
            + uso.get("cache_creation_input_tokens", 0) * p["escrita_cache_5m"]
            + uso.get("cache_read_input_tokens", 0) * p["leitura_cache"]
            + uso.get("output_tokens", 0) * p["saida"]) / 1_000_000


class Cache:
    """Cache em disco, só acrescenta linhas. Uma linha por chamada bem-sucedida."""

    def __init__(self, modelo: str):
        config.CACHE.mkdir(exist_ok=True)
        self.caminho = config.CACHE / f"{modelo}.jsonl"
        self.dados = {}
        if self.caminho.exists():
            for linha in self.caminho.read_text(encoding="utf-8").splitlines():
                if linha.strip():
                    r = json.loads(linha)
                    self.dados[r["chave"]] = r
        self._trava = threading.Lock()

    def get(self, chave):
        return self.dados.get(chave)

    def put(self, registro: dict):
        with self._trava:
            self.dados[registro["chave"]] = registro
            with open(self.caminho, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")


def checar_pii(texto: str) -> None:
    achados = encontrar_pii_regex(texto)
    if achados:
        raise ValueError(f"dado pessoal estruturado no texto a enviar: {[t for t, _ in achados]}")


def chamar(cliente, corpo: dict, id_pedido: str, cache: Cache, tentativas: int = 4) -> dict:
    """Uma chamada com cache. Erros 429/5xx/conexão: espera e tenta de novo. Outros erros sobem."""
    import anthropic

    chave = chave_cache(corpo, id_pedido)
    if (r := cache.get(chave)) is not None:
        return r | {"do_cache": True}
    checar_pii(corpo["system"][0]["text"])
    checar_pii(corpo["messages"][0]["content"])
    espera = 5.0
    for tentativa in range(tentativas):
        try:
            ini = time.perf_counter()
            resp = cliente.messages.create(**corpo)
            latencia = time.perf_counter() - ini
            break
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError):
            if tentativa == tentativas - 1:
                raise
            time.sleep(espera)
            espera *= 2
    texto = next((b.text for b in resp.content if b.type == "text"), None)
    uso = {k: getattr(resp.usage, k, 0) or 0 for k in
           ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}
    registro = {
        "chave": chave, "id": id_pedido, "modelo": corpo["model"], "resposta": texto,
        "stop_reason": resp.stop_reason, "uso": uso, "custo_usd": round(custo_usd(corpo["model"], uso), 8),
        "latencia_s": round(latencia, 3), "request_id": getattr(resp, "_request_id", None),
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    cache.put(registro)
    return registro | {"do_cache": False}
