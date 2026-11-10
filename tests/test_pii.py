from collections import Counter

import pytest

from triagem.pii import encontrar_pii_regex, mascarar, mascarar_regex, parece_nome_de_pessoa


@pytest.mark.parametrize("texto, tipo", [
    ("meu e-mail é fulano.silva+lai@gmail.com obrigado", "EMAIL"),
    ("CPF 123.456.789-09", "CPF"),
    ("cpf: 12345678909.", "CPF"),
    ("ligue (48) 99999-8888", "TELEFONE"),
    ("telefone: 48 3333 4444", "TELEFONE"),
    ("whatsapp 48999998888", "CPF"),  # 11 dígitos soltos: mascarado como CPF, o que basta
    ("fone 3333-4444", "TELEFONE"),
    ("celular 98888-7777", "TELEFONE"),
    ("CEP 88040-900", "CEP"),
    ("cep: 88.040-900", "CEP"),
    ("RG nº 9.087.112 SSP/SC", "RG"),
    ("moro na Rua das Flores, 123, centro", "ENDERECO"),
    ("Av. Paulista, nº 1000", "ENDERECO"),
    ("Número do passaporte: XZ0001234", "DOCUMENTO"),
    ("advogada OAB/SC 000.123", "DOCUMENTO"),
    ("NIS 10293847561", "DOCUMENTO"),
    ("cartão SUS 898001234567890", "DOCUMENTO"),
])
def test_regex_mascara_dado_pessoal(texto, tipo):
    c = Counter()
    saida = mascarar_regex(texto, c)
    assert f"[{tipo}]" in saida
    assert c[tipo] >= 1
    assert encontrar_pii_regex(saida) == []


@pytest.mark.parametrize("texto", [
    "dados de 2019-2023 por município",
    "anos 2022 2023 e 2024",
    "processo NUP 54800.001332/2025-81",
    "protocolo 00118000504202579",
    "obras na BR-101 e na Rodovia BR-116",
    "com base na Lei nº 12.527/2011 e no Decreto 7.724/2012",
    "pedido registrado em 01/12/2025",
    "CNPJ 00.000.000/0001-91 da empresa",
    "valor de R$ 1.234.567,89 em 2024",
    "Portaria 1.234/2025",
    "dados do PIS 2023 e da CNH",
    # Números longos sem rótulo costumam ser GTIN, registro Anvisa, CNPJ, contrato ou processo SEI.
    "GTIN: 07897076919355 Lote: PTG2459A",
    "registrado na Anvisa sob o nº 1223400580011",
    "CNPJ: 60691250000147",
    "ICJs nº 59000124368232",
    "Processo SEI nº 202400005008151",
])
def test_regex_nao_mascara_informacao_util(texto):
    assert mascarar_regex(texto) == texto


def test_ner_mascara_nome_de_pessoa():
    c = Counter()
    [saida] = mascarar(["Meu nome é Valdemar Quintanilha Brito e solicito ao Ministério da Saúde dados de vacinação."], c)
    assert "Carlos" not in saida and "Pereira" not in saida
    assert "[NOME]" in saida
    assert "Ministério da Saúde" in saida
    assert c["NOME"] == 1


@pytest.mark.parametrize("trecho, esperado", [
    ("Valdemar Quintanilha Brito", True),
    ("Ana Souza", True),
    ("Zoraldo Quintanilha Brevi", True),  # prenome raro, mas nome completo
    ("Agradeço", False),
    ("Bacen", False),
    ("Selic", False),
    ("Prouni", False),
    ("MEI", False),
    ("CPF:[CPF", False),
    ("§3º", False),
    ("Analista de Infraestrutura", False),
])
def test_filtro_de_nomes(trecho, esperado):
    assert parece_nome_de_pessoa(trecho) is esperado


def test_ner_nao_apaga_termos_do_dominio():
    texto = "Agradeço. Solicito dados do Bacen sobre a Selic e o Pix, e do Prouni."
    [saida] = mascarar([texto])
    assert saida == texto


def test_nome_em_maiusculas_e_sobrenome_restante():
    [saida] = mascarar(["A consulta foi assinada por OTAVIO RENAN TASSINARI BRUM, Chefe da Divisão."])
    assert "OTAVIO" not in saida and "BRUM" not in saida
    [saida] = mascarar(["Histórico da paciente Maria Helena do Vale Tormenta no INCA."])
    assert "Tormenta" not in saida and "Vale" not in saida


def test_maiusculas_que_nao_sao_nome_ficam():
    texto = "PEDIDO DE ACESSO sobre o MEI e a LEI GERAL, em SAO PAULO, no INSS e na ANVISA."
    assert mascarar([texto])[0] == texto


def test_mascarar_preserva_ordem_e_marcadores():
    textos = ["Att, Ana Souza. CPF 123.456.789-09", "Sem dado pessoal aqui."]
    saida = mascarar(textos)
    assert len(saida) == 2
    assert "[CPF]" in saida[0] and "Ana Souza" not in saida[0]
    assert saida[1] == "Sem dado pessoal aqui."


# Padrões de vazamento apontados pela verificação do Marco 1 (nomes inventados, mesmo formato).
@pytest.mark.parametrize("texto, nao_pode_ficar", [
    ("Bom dia, Meu nome é Lisandre Bortoval, mestranda do programa.", ["Lisandre", "Bortoval"]),
    ("glosas pelo auditor do SUS  JULIANA PAULA FERREIRA", ["JULIANA", "FERREIRA"]),
    ("ADI 1234/STF ODETE KRAMER, CPF: 123.456.789-09 | AO ILMO. SR. DIRETOR", ["ODETE", "KRAMER", "123.456"]),
    ("Envio em xlsx.  Atenciosamente, Ardiel Mendrano", ["Ardiel", "Mendrano"]),
    ("Obrigada,\nKassiely Tormena\nPesquisadora", ["Kassiely", "Tormena"]),
    ("Eu, Jeyson Faccioli, brasileiro, solicito", ["Jeyson", "Faccioli"]),
    ("Data de nascimento: 12/03/1987, solicito meu extrato", ["12/03/1987"]),
    ("nascida em 07.05.1990 no Ceará", ["07.05.1990"]),
    ("advogados: Felipe Travenzi Rodrigo Mancebo Francine Lobato Quesada", ["Travenzi", "Mancebo", "Lobato"]),
    ("casos: Osmar Quintela Brandão Filho Felipe Travenzi Rodrigo Mancebo Beatriz Zalfarini", ["Travenzi", "Zalfarini"]),
])
def test_vazamentos_da_verificacao(texto, nao_pode_ficar):
    [saida] = mascarar([texto])
    for trecho in nao_pode_ficar:
        assert trecho not in saida, saida


def test_absorve_sobrenomes_vizinhos():
    from triagem.pii import _absorver_vizinhos
    assert _absorver_vizinhos("[NOME] DE ARRUDA  LIRA DORALICE DE SOUSA TAVEIRA") == "[NOME]"
    assert _absorver_vizinhos("Jeyson [NOME] solicita") == "[NOME] solicita"
    assert _absorver_vizinhos("dados do INSS [NOME]") == "dados do INSS [NOME]"
    assert _absorver_vizinhos("[NOME] e Ministério da Saúde") == "[NOME] e Ministério da Saúde"


@pytest.mark.parametrize("termo", [
    "Registro de Operações Financeiras",
    "Casa da Moeda do Brasil",
    "Certidão Negativa de Naturalização",
    "Coqueluche Sarampo Tuberculose",
    "Hepatites Virais",
    "Certificação de Boas Práticas de Fabricação",
    "Registrato",
    "Atributos e Indicadores",
    "Fator VII Recombinante",
])
def test_termos_do_dominio_nao_sao_nome(termo):
    assert parece_nome_de_pessoa(termo) is False


@pytest.mark.parametrize("texto", [
    "Solicito o Registro de Operações Financeiras (ROF) e o Registrato.",
    "Atenciosamente, Ministério da Saúde",
    "Obrigado, Anvisa, pela atenção.",
    "Dados de Coqueluche Sarampo Tuberculose por estado.",
    "Contrato com a Casa da Moeda do Brasil.",
])
def test_mascara_nao_apaga_dominio(texto):
    assert mascarar([texto])[0] == texto


@pytest.mark.parametrize("texto", [
    "Pedido sobre obras em São Paulo e Santa Catarina.",
    "Dados do Rio Grande do Sul e de Mato Grosso.",
])
def test_lugares_nao_viram_nome(texto):
    assert mascarar([texto])[0] == texto


@pytest.mark.parametrize("texto", [
    "Códigos da Plataforma Nilo Peçanha para cotas.",
    "Pesquisa da Fundação Oswaldo Cruz (Fiocruz) sobre vacinas.",
    "Obras no município de Frederico Westphalen e em São Gabriel da Cachoeira.",
])
def test_nome_que_batiza_instituicao_ou_lugar_fica(texto):
    assert mascarar([texto])[0] == texto


# Ressalva da 3a verificação: sobrenome que também é palavra comum, depois de Sr./Sra. (nomes inventados).
@pytest.mark.parametrize("texto, nao_pode_ficar", [
    ("O Sr. Marcos Valente Torres requer acesso.", ["Marcos", "Valente", "Torres"]),
    ("A Sra. Priscila Campos da Silva atuou no comitê.", ["Priscila", "Campos", "Silva"]),
    ("Prezado Ivan, bom dia.", ["Ivan"]),
    ("Dra. Helena Rosa Prado assinou o parecer.", ["Helena", "Rosa", "Prado"]),
])

def test_nome_depois_de_tratamento(texto, nao_pode_ficar):
    [saida] = mascarar([texto])
    for trecho in nao_pode_ficar:
        assert trecho not in saida, saida


def test_tratamento_para_em_nome_de_instituicao():
    [saida] = mascarar(["Atendido pelo Dr. Ricardo Alves Hospital Santa Casa de Misericórdia."])
    assert "Ricardo" not in saida and "Alves" not in saida
    assert "Hospital Santa Casa" in saida


@pytest.mark.parametrize("texto", [
    "Sr. Diretor da Anvisa, solicito dados.",
    "Prezados Senhores, solicito dados do INSS.",
    "Prezada Ouvidoria, peço informações.",
])
def test_tratamento_sem_nome_fica(texto):
    assert mascarar([texto])[0] == texto


def test_varredura_acha_trecho_de_pedido(tmp_path, monkeypatch):
    """A varredura marca 8 palavras seguidas copiadas de um pedido, mas não frase comum a muitos pedidos."""
    from triagem import varrer_versionados as v
    monkeypatch.setattr(v.config, "RAIZ", tmp_path)
    (tmp_path / "doc.md").write_text("Exemplo: solicito a lista completa dos contratos de manutenção predial do bloco Z em 2024.\n"
                                     "Com base na Lei de Acesso à Informação, solicito informações sobre o assunto.")
    brutos = ["Prezados, solicito a lista completa dos contratos de manutenção predial do bloco Z em 2024. Obrigado"] + \
             ["Com base na Lei de Acesso à Informação, solicito informações sobre o assunto x"] * 5
    achados = v.trechos_de_pedido([tmp_path / "doc.md"], brutos)
    assert any("manutencao predial" in t for t in achados)
    assert not any("lei de acesso" in t for t in achados)
