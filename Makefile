PY := .venv/bin/python
RUN := PYTHONPATH=src $(PY) -m

.PHONY: all setup dados dor preparar test ref auditoria-pii varredura

all: dados dor preparar test

setup:
	python3.11 -m venv .venv
	$(PY) -m pip install -r requirements.txt

# Baixa os zips da CGU só se ainda não existirem (a CGU atualiza os arquivos todo dia).
dados:
	$(RUN) triagem.dados

# Marco 1: quantos pedidos chegam hoje ao órgão errado.
dor:
	$(RUN) triagem.dor

# Marco 1: treino/dev/teste com dados pessoais mascarados. O teste é congelado.
preparar:
	$(RUN) triagem.preparar

test:
	$(PY) -m pytest -q

# Listas de referência do filtro de nomes (já versionadas em data/ref/):
# prenomes do IBGE e palavras comuns do corpus.
ref:
	$(PY) -c "import sys; sys.path.insert(0, 'src'); from triagem.pii import gerar_lista_prenomes; gerar_lista_prenomes()"
	PYTHONPATH=src $(PY) -c "from triagem import dados, pii; f = dados.ler_filtrada(); pii.gerar_palavras_comuns((f.ResumoSolicitacao + ' ' + f.DetalhamentoSolicitacao).tolist())"

# Auditoria da máscara (dev + teste). A amostra gerada tem nomes reais e fica fora do git.
auditoria-pii:
	$(RUN) triagem.auditoria_pii

# Antes de cada commit: procura dados pessoais nos arquivos que vão para o repositório.
varredura:
	$(RUN) triagem.varrer_versionados
