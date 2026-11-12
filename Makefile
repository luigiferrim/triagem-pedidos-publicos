PY := .venv/bin/python
RUN := PYTHONPATH=src $(PY) -m

.PHONY: all setup dados dor preparar test ref auditoria-pii varredura baselines revisao estimar-custo llm-dev llm-teste abstencao relatorio pii-detector holdout-preparar holdout mesa mesa-publicar mesa-ao-vivo unidades marco7-estimar marco7-piloto marco7-dev marco7-congelar marco7-fev manchete marco8-preparar marco8-avaliar marco9-avaliar

all: dados dor preparar baselines llm-dev llm-teste abstencao manchete relatorio mesa test

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

# Marco 2: regras e ML clássico (escolha no dev, medição no teste).
baselines:
	$(RUN) triagem.marco2 --teste

# Concordância da revisão manual (data/revisao_manual_50.csv preenchido pelo Luigi).
revisao:
	$(RUN) triagem.revisao

# Marco 3: LLMs. A chave vem do ambiente ou de um arquivo .env (fora do git) com ANTHROPIC_API_KEY=...
CARREGA_ENV := if [ -f .env ]; then set -a; . ./.env; set +a; fi;

estimar-custo:
	$(CARREGA_ENV) $(RUN) triagem.estimar_custo --contar

llm-dev:
	$(CARREGA_ENV) $(RUN) triagem.marco3 rodar --modelo haiku --conjunto dev
	$(CARREGA_ENV) $(RUN) triagem.marco3 rodar --modelo sonnet --conjunto dev
	$(RUN) triagem.marco3 avaliar

# Teste dos LLMs: roda uma vez (o cache evita gastar de novo) e avalia com registro.
llm-teste:
	$(CARREGA_ENV) $(RUN) triagem.marco3 rodar --modelo haiku --conjunto test
	$(CARREGA_ENV) $(RUN) triagem.marco3 rodar --modelo sonnet --conjunto test
	$(RUN) triagem.marco3 avaliar --teste
	$(RUN) triagem.erros
	$(RUN) triagem.pii_dirigida

# Marco 4: abstenção (só lê results/predicoes/; não chama a API)
abstencao:
	$(RUN) triagem.marco4

# Marco 5: report.html e results/curva_cobertura_erro.png (só lê results/)
relatorio:
	$(RUN) triagem.relatorio

# Detector offline de nomes sem máscara em tudo que foi enviado à API (só ids no resultado)
pii-detector:
	$(RUN) triagem.pii_detector

# Holdout de 2026 (confirmação do limiar congelado). Baixe e extraia o arquivo filtrado de 2026 em data/raw/filtrada_2026/
holdout-preparar:
	$(RUN) triagem.holdout preparar

# Holdout: uma rodada do Sonnet (API, com cache) e avaliação com os limiares congelados
holdout:
	$(CARREGA_ENV) $(RUN) triagem.holdout rodar
	$(RUN) triagem.holdout avaliar

# Marco 6: Mesa de Triagem (site estático em mesa/)
mesa:
	$(RUN) triagem.mesa dados

# Depois da revisão manual dos exemplos (data/revisao_exemplos_mesa*.csv): grava mesa/dados/exemplos.json e os hashes aprovados
mesa-publicar:
	$(RUN) triagem.mesa publicar

# Modo ao vivo, só local (http://127.0.0.1:8765): mascara, chama o Sonnet com a chave do .env e aplica a política
mesa-ao-vivo:
	$(CARREGA_ENV) $(RUN) triagem.mesa_ao_vivo

# Marco 7: tabela unidade -> órgão a partir do SIORG (dados abertos) e estimativa de custo da v2
unidades:
	$(RUN) triagem.unidades

marco7-estimar:
	$(CARREGA_ENV) $(RUN) triagem.marco7 estimar

marco7-piloto:
	$(CARREGA_ENV) $(RUN) triagem.marco7 piloto

marco7-dev:
	$(CARREGA_ENV) $(RUN) triagem.marco7 dev
	$(RUN) triagem.marco7 avaliar-dev

# Antes de rodar fevereiro: congela prompt, ferramenta, tabela, limiares e o hash do holdout
marco7-congelar:
	$(RUN) triagem.marco7 congelar

# Fevereiro: uma rodada de v1 e v2 com tudo congelado, e a avaliação
marco7-fev:
	$(CARREGA_ENV) $(RUN) triagem.marco7 fev
	$(RUN) triagem.marco7 avaliar-fev
	$(RUN) triagem.marco7 diagnostico

# Números de manchete (fonte única do site, README, DECISAO e relatório)
manchete:
	$(RUN) triagem.manchete

# Marco 8: regra corrigida (só jan+fev), amostra mensal, modelo estatístico no volume todo, congelamento
marco8-preparar:
	$(RUN) triagem.marco8 regra
	$(RUN) triagem.marco8 amostra
	$(RUN) triagem.marco8 ml
	$(RUN) triagem.marco8 congelar
	$(RUN) triagem.marco8 estimar

# Marco 8 depois das chamadas (aprovadas): investigação do INSS, ML com e sem o lote, avaliação (só lê as respostas do cache; não chama a API)
marco8-avaliar:
	$(RUN) triagem.marco8 inss
	$(RUN) triagem.marco8 ml-sem-lote
	$(RUN) triagem.marco8 avaliar
	$(RUN) triagem.mesa dados

# Marco 9 (Prefeitura de São Paulo), sem custo: refaz tudo a partir do cache das respostas.
# Os brutos ficam em data/raw/sp/ (`python -m triagem.marco9 baixar`); rodar a API é `marco9 rodar --conjunto ...`.
marco9-avaliar:
	$(RUN) triagem.marco9 dor
	$(RUN) triagem.marco9 auditar
	$(RUN) triagem.marco9 ml
	$(RUN) triagem.marco9 avaliar --conjunto dev
	$(RUN) triagem.marco9 avaliar --conjunto teste
	$(RUN) triagem.marco9 analisar
	$(RUN) triagem.marco9 comparar
