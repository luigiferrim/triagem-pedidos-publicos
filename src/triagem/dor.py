"""Mede a dor: quantos pedidos chegam hoje ao órgão errado e quanto isso atrasa a resposta.

Definições (detalhes em DADOS.md):
- reencaminhado: FoiReencaminhado == "Sim". O pedido foi aberto num órgão e passado a outro.
- sem competência: Decisao == "Órgão não tem competência...". O órgão recusou e o pedido morreu ali.
- chegou ao órgão errado = reencaminhado OU sem competência.
- parcialmente de outro órgão: parte da informação era de outro órgão. Reportado à parte (limite superior).

Universo principal: base completa (todos os pedidos, sem texto), esfera federal, situação "Concluída".
"""
import json

import pandas as pd

from triagem import config, dados, orgaos


def _marcadores(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "reencaminhado": df["FoiReencaminhado"] == "Sim",
        "sem_competencia": df["Decisao"] == config.DECISAO_SEM_COMPETENCIA,
        "parcial_outro_orgao": df["EspecificacaoDecisao"] == config.ESPEC_PARCIAL_OUTRO_ORGAO,
    }, index=df.index)


def _pct(x: float) -> float:
    return round(100 * float(x), 2)


def resumo_dor(df: pd.DataFrame) -> dict:
    m = _marcadores(df)
    errado = m.reencaminhado | m.sem_competencia
    return {
        "n_pedidos": int(len(df)),
        "reencaminhados": int(m.reencaminhado.sum()),
        "pct_reencaminhados": _pct(m.reencaminhado.mean()),
        "sem_competencia": int(m.sem_competencia.sum()),
        "pct_sem_competencia": _pct(m.sem_competencia.mean()),
        "sobreposicao_reenc_e_sem_comp": int((m.reencaminhado & m.sem_competencia).sum()),
        "chegaram_ao_orgao_errado": int(errado.sum()),
        "pct_chegaram_ao_orgao_errado": _pct(errado.mean()),
        "parcial_outro_orgao": int(m.parcial_outro_orgao.sum()),
        "pct_errado_incluindo_parcial": _pct((errado | m.parcial_outro_orgao).mean()),
    }


def atraso(df: pd.DataFrame) -> dict:
    """Dias entre registro e resposta, reencaminhados x pedidos que chegaram certo.

    Premissa: DataRegistro é a data em que o cidadão abriu o pedido, não a do reencaminhamento.
    Se fosse a do reencaminhamento, o atraso abaixo estaria subestimado.
    """
    m = _marcadores(df)
    reg = pd.to_datetime(df["DataRegistro"], format="%d/%m/%Y", errors="coerce")
    resp = pd.to_datetime(df["DataResposta"], format="%d/%m/%Y", errors="coerce")
    dias = (resp - reg).dt.days
    certo = ~(m.reencaminhado | m.sem_competencia | m.parcial_outro_orgao)

    def desc(mask):
        d = dias[mask].dropna()
        return {"n": int(len(d)), "media_dias": round(float(d.mean()), 1), "mediana_dias": float(d.median()),
                "pct_prorrogados": _pct((df.loc[mask, "FoiProrrogado"] == "Sim").mean())}

    r, c = desc(m.reencaminhado), desc(certo)
    return {
        "reencaminhados": r,
        "chegaram_certo": c,
        "sem_competencia": desc(m.sem_competencia),
        "atraso_extra_media_dias": round(r["media_dias"] - c["media_dias"], 1),
        "atraso_extra_mediana_dias": r["mediana_dias"] - c["mediana_dias"],
    }


def por_orgao(df: pd.DataFrame, lista: list[str]) -> list[dict]:
    """Atenção à leitura: para reencaminhados, o órgão é o DESTINO final (quem recebeu o pedido
    de outro). Para "sem competência", o órgão é quem recebeu errado e recusou."""
    m = _marcadores(df)
    linhas = []
    for nome in lista:
        sel = df["OrgaoDestinatario"] == nome
        linhas.append({
            "orgao": orgaos.sigla(nome),
            "n_pedidos": int(sel.sum()),
            "pct_recebidos_por_reencaminhamento": _pct(m.reencaminhado[sel].mean()),
            "pct_sem_competencia": _pct(m.sem_competencia[sel].mean()),
        })
    return linhas


def main() -> None:
    completa = dados.ler_completa()
    filtrada = dados.ler_filtrada()

    fed_concl = completa[(completa["Esfera"] == "Federal") & (completa["Situacao"] == "Concluída")]
    lista = orgaos.top_orgaos(filtrada)

    resultado = {
        "ano": config.ANO,
        "universo_principal": "base completa, esfera Federal, situação Concluída",
        "base_completa_total_linhas": int(len(completa)),
        "base_completa_por_esfera": completa["Esfera"].value_counts().to_dict(),
        "federal_concluida": resumo_dor(fed_concl),
        "federal_concluida_atraso": atraso(fed_concl),
        "federal_concluida_top10": resumo_dor(fed_concl[fed_concl["OrgaoDestinatario"].isin(lista)]),
        "federal_concluida_por_orgao_top10": por_orgao(fed_concl, lista),
        "base_com_texto": {
            "n_pedidos": int(len(filtrada)),
            "pct_da_base_completa": _pct(len(filtrada) / len(completa)),
            "ids_contidos_na_completa": bool(filtrada["IdPedido"].isin(completa["IdPedido"]).all()),
            "dor": resumo_dor(filtrada),
        },
        "top10_base_completa_federal": [
            {"orgao": orgaos.sigla(k), "n": int(v)}
            for k, v in fed_concl["OrgaoDestinatario"].value_counts().head(10).items()
        ],
    }
    config.RESULTS.mkdir(exist_ok=True)
    out = config.RESULTS / "dor.json"
    out.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")

    d, a = resultado["federal_concluida"], resultado["federal_concluida_atraso"]
    print(f"Pedidos LAI federais concluídos em {config.ANO}: {d['n_pedidos']:,}")
    print(f"  reencaminhados:            {d['pct_reencaminhados']:5.2f}%  ({d['reencaminhados']:,})")
    print(f"  sem competência:           {d['pct_sem_competencia']:5.2f}%  ({d['sem_competencia']:,})")
    print(f"  chegaram ao órgão errado:  {d['pct_chegaram_ao_orgao_errado']:5.2f}%  ({d['chegaram_ao_orgao_errado']:,})")
    print(f"  + parcialmente de outro:   {d['pct_errado_incluindo_parcial']:5.2f}%")
    print(f"  atraso extra (mediana):    {a['atraso_extra_mediana_dias']} dias; média {a['atraso_extra_media_dias']} dias")
    print(f"resultado em {out}")


if __name__ == "__main__":
    main()
