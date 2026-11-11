"""Modo ao vivo da Mesa (só local): cola-se um pedido novo, ele é mascarado, vai ao Sonnet e passa pela política v1.

Uso: make mesa-ao-vivo  ->  abre http://127.0.0.1:8765 (a chave vem do .env; nada disso vai para o site público).

- Escuta só em 127.0.0.1.
- Máscara: a mesma de todo o projeto (pii.mascarar) e, depois, a checagem de dados pessoais (llm.checar_pii).
  Se a checagem achar CPF, e-mail ou telefone no texto já mascarado, o pedido não é enviado.
- Sonnet: o mesmo prompt e o mesmo cache local (cache/); o mesmo pedido não é cobrado duas vezes.
- ML: o mesmo modelo do Marco 2, treinado uma vez e guardado em cache/ (fora do git).
- Teto por sessão: TETO_SESSAO_USD.
"""
import hashlib
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from triagem import config, llm, pii
from triagem.marco3 import _sistema
from triagem.mesa import DIR_MESA, limiares, politica

PORTA = 8765
TETO_SESSAO_USD = 0.50
MAX_CARACTERES = 5000
_estado = {"gasto": 0.0, "ml": None, "cliente": None, "sistema": None}
_trava = threading.Lock()


def _modelo_ml():
    if _estado["ml"] is None:
        import joblib
        arq = config.CACHE / "ml_v1.joblib"
        if arq.exists():
            _estado["ml"] = joblib.load(arq)
        else:
            from triagem.holdout import modelo_ml
            mdl = modelo_ml()
            config.CACHE.mkdir(exist_ok=True)
            joblib.dump(mdl, arq)
            _estado["ml"] = mdl
    return _estado["ml"]


def classificar(texto: str, cliente=None) -> dict:
    """Mascara, consulta Sonnet e ML, aplica a política v1. Devolve o registro no formato dos exemplos da Mesa."""
    from triagem import ml
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("texto vazio")
    if len(texto) > MAX_CARACTERES:
        raise ValueError(f"texto com mais de {MAX_CARACTERES} caracteres")
    [mascarado] = pii.mascarar([texto])
    llm.checar_pii(mascarado)  # levanta ValueError se sobrar CPF, e-mail etc.
    if _estado["sistema"] is None:
        _estado["sistema"] = _sistema()
    modelo = llm.MODELOS["sonnet"]
    corpo = llm.corpo_requisicao(modelo, _estado["sistema"], mascarado)
    id_ = "novo-" + hashlib.sha256(mascarado.encode("utf-8")).hexdigest()[:10]
    cache = llm.Cache(modelo)
    if cliente is None:
        if _estado["cliente"] is None:
            import anthropic
            _estado["cliente"] = anthropic.Anthropic(max_retries=2)
        cliente = _estado["cliente"]
    # Uma chamada por vez: a checagem do teto e o registro do gasto ficam juntos.
    with _trava:
        ja_tinha = cache.get(llm.chave_cache(corpo, id_)) is not None
        if not ja_tinha and _estado["gasto"] >= TETO_SESSAO_USD:
            raise ValueError(f"teto da sessão atingido (US$ {TETO_SESSAO_USD:.2f})")
        rec = llm.chamar(cliente, corpo, id_, cache)
        custo = 0.0 if ja_tinha else rec.get("custo_usd", 0.0)
        _estado["gasto"] += custo
    dados_, erro = llm.interpretar(rec["resposta"])
    pred, prob = ml.prever(_modelo_ml(), [mascarado])
    p = dict(zip(_modelo_ml().classes_, map(float, prob[0])))
    sonnet = dados_["orgao"] if dados_ else None
    conf = dados_["confianca"] if dados_ else None
    auto, motivo = politica(conf, sonnet, pred[0], p.get(sonnet, 0.0), limiares()["0.01"])
    return {"id": id_, "ao_vivo": True, "tipo": "automático" if auto else "para pessoa",
            "status": "encaminhado automaticamente" if auto else "aguardando servidor",
            "rotulo": None, "sonnet": sonnet, "confianca": conf, "ml": pred[0], "p_ml": round(p.get(sonnet, 0.0), 4),
            "motivo": motivo if not erro else f"resposta inválida do modelo ({erro}), foi para pessoa",
            "reencaminhado": False, "texto": mascarado, "trecho": (dados_ or {}).get("trecho", ""),
            "justificativa": (dados_ or {}).get("justificativa", ""), "custo_usd": round(custo, 5),
            "gasto_sessao_usd": round(_estado["gasto"], 4)}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIR_MESA), **kw)

    def _json(self, status: int, obj: dict) -> None:
        corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path.startswith("/api/status"):
            return self._json(200, {"ao_vivo": True, "gasto_sessao_usd": round(_estado["gasto"], 4), "teto_usd": TETO_SESSAO_USD})
        return super().do_GET()

    def _origem_local(self) -> bool:
        """Só aceita pedidos da própria Mesa local (evita que outra página do navegador gaste a chave)."""
        locais = {f"127.0.0.1:{PORTA}", f"localhost:{PORTA}"}
        if self.headers.get("Host", "") not in locais:
            return False
        origem = self.headers.get("Origin")
        return origem is None or origem in {f"http://{h}" for h in locais}

    def do_POST(self):
        if not self.path.startswith("/api/classificar"):
            return self._json(404, {"erro": "não encontrado"})
        if not self._origem_local() or not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._json(403, {"erro": "pedido recusado: só a Mesa local pode classificar"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            texto = json.loads(self.rfile.read(min(n, 4 * MAX_CARACTERES)).decode("utf-8")).get("texto", "")
            return self._json(200, classificar(texto))
        except ValueError as e:
            return self._json(400, {"erro": f"Não enviado: {e}"})
        except Exception as e:  # erro de API etc.
            return self._json(502, {"erro": f"Falha ao consultar o modelo: {type(e).__name__}"})

    def log_message(self, *a):
        pass


def main() -> None:
    _modelo_ml()
    srv = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    print(f"Mesa ao vivo em http://127.0.0.1:{PORTA}  (teto da sessão: US$ {TETO_SESSAO_USD:.2f}; Ctrl+C para sair)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\nfim. gasto da sessão: US$ {_estado['gasto']:.4f}")


if __name__ == "__main__":
    main()
