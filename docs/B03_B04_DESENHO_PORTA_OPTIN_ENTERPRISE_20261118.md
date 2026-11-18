# SOLVERIS B03/B04 — Desenho candidato de porta Enterprise opt-in

Data: 18/11/2026. **DESENHO/CONTRATO PARA DECISÃO — ZERO IMPLEMENTAÇÃO.**

Fundamento: ratificação de Miguel para estudar e validar o delta mínimo que
permita restaurar B01/B03/B04 sem modificar o comportamento das rotas
partilhadas, especialmente MEI. Não há autorização para alterar código
de negócio nesta etapa. Ler também
`docs/B03_B04_VIABILIDADE_ADAPTADOR_ENTERPRISE_20261118.md` e
`docs/HANDOFF_B03_B04_RECUPERACAO_PARA_B06_20261118.md`.

## 1. Contrato de entrada proposto

Uma chamada **explícita** e separadamente autorizada para o circuito
Enterprise, nunca um efeito colateral de `gerar-relatorio`, upload XML,
job ou atendimento MEI. A ausência do marcador/contrato Enterprise
mantém **exatamente** a sequência, o formato, o produtor de proveniência
e as respostas legacy já existentes.

Pré-condições antes da primeira escrita:

1. Base de testes limitada a SQLite **em memória**, como exige B01 atual;
   execução em PostgreSQL/prod continua bloqueada por missão distinta.
2. Identidade do utilizador autenticado e titularidade da empresa,
   `regime_tributario` em `{real, presumido}` e **`optante_mei is False`**
   (não basta `is not True`: o campo é nullable).
3. `xml_bytes` de NF-e modelo 55, saída, competência datada com fuso,
   CNPJ emitente idêntico ao sujeito e chave de 44 dígitos coerente.
4. Rejeição antecipada de qualquer injeção de autoridade fiscal, crédito,
   autorização de pagamento ou prova SEFAZ não demonstrada.
5. Contrato de vínculo e unicidade definido antes de alterar estado:
   mesmo sujeito + chave NF-e com **bytes distintos** nunca equivale
   a uma duplicação inocente. Não aceitar prova construída sobre
   documento sintético que não foi persistido.

## 2. Ponto correto de integração

O B01 original exige um `DocumentoFiscal` efetivamente persistido,
`RelatorioAnalise` da mesma empresa/titular e `xml_sha256` idêntico.
O vínculo `_enterprise_xml_evidence` tem de ser construído **antes**
de `selar_resultado_nao_mei` e gravado com o **mesmo** fingerprint,
sem sobreposição posterior do JSON já validado.

A única hipótese de reaproveitamento com semântica próxima da origem
é abrir uma **porta opt-in limitada** no ponto de preparação/selagem do
resultado. Essa hipótese requer alteração auditada do serviço comum
`app/services/registro_analise_service.py`; não é um adaptador puramente
externo. Qualquer alteração deve preservar o comportamento exato de
chamadas sem o parâmetro Enterprise.

Não duplicar o escritor em novo módulo apenas para passar nos testes.
Não alterar `_CAPACIDADES` do I0. Não aproveitar ausência de autoridade
para inventar valor MVA por categoria do remetente.

## 3. Questão transacional adicional — dependência real do desenho

`app/xml_service.py::persistir_documento_fiscal`,
`registro_analise_service.py::{criar_registro_analise,finalizar_registro_analise}`
e `usage_service.py::incrementar_uso_analise` possuem `db.commit()`
internos. `insights_engine.py` também possui commit na `main`
(patch `912cb309` ainda fora dela).

Portanto **uma porta opcional no escritor não garante, por si só,
atomicidade do ciclo completo**. É preciso decidir separadamente se
o requisito é apenas vínculo documental íntegro no momento de selar
ou **transação única** que só confirma todos os efeitos após os gates.
Se for transação única, a reutilização segura possivelmente exige
contratos de persistência do tipo `flush` sem `commit` interno **apenas
no modo Enterprise** e commit único no limite autorizado. Isto afeta
mais de um módulo partilhado e aumenta a superfície de regressão;
**não foi demonstrado nem autorizado**.

A implementação posterior deve identificar a ordem exata dos commits,
provar idempotência/rollback sob colisão por chave e por hash,
e impedir que uma falha após persistir documento produza relatório
aparentemente completo. Não tentar simular transação global com
`begin_nested`, monkeypatch de `commit` ou reescrita retroativa do
resultado sem prova independente do comportamento SQLAlchemy.

## 4. Envelope e saídas exigidos

| Estado | Comportamento exigido |
| --- | --- |
| Chamada legacy sem opt-in | Retorno e produtor `analysis_orchestrator` originais, sem chave Enterprise nova |
| Sujeito MEI, `optante_mei=NULL`, titular divergente ou regime inválido | Rejeição antes de writes e sem emissão de prova |
| NF-e/chave/bytes/documento incoerentes | Falha fechada, nenhuma promoção de autoridade |
| Relatório válido Enterprise | Um único resultado empresarial selado com documento, fingerprint, identificadores e prova verificáveis |
| Capacidade normativa/MVA sem categoria jurídica provada | `não apurado - pendente categoria do remetente`, nunca atacadista presumido |
| Falha em produtor G12/G13/I2 ou custódia | Estado auditável e não publicável; não converter erro em crédito/pagamento |

## 5. Provas exigidas antes de qualquer commit de código

1. Os **25 testes originais B01 (12) + B03 (7) + B04 (6)**, já fixados
   pela catraca, permanecem intactos e todos passam.
2. Regressões do **mesmo escritor** pelos consumidores existentes:
   `app/main.py`, `app/routes/relatorio_router.py`,
   `app/jobs/analysis_job.py` e `app/services/assistente_service.py`
   (este último usa os auxiliares de criar/finalizar relatório).
3. Casos negativos: `optante_mei=True`, `NULL`, outro titular,
   regime diferente, chave igual/bytes diferentes, documento de outra
   empresa, falha antes/depois de cada ponto de confirmação, retry
   concorrente e documento duplicado com mesmo SHA.
4. Comparação do contrato legacy antes/depois: argumentos aceites,
   `resultado_json`, produtor de proveniência, status e contagem de uso.
5. Sem alterar quatro testes RED congelados; os **4.102 casos da
   baseline** íntegros, as **13 falhas originais com assinatura igual**
   e nenhum novo RED/skip. Executar no Windows isolado com Docker,
   comparar via `tools/enterprise_recovery_test_gate.py`.
6. `tools/check_duplicacao.py` fail-closed, `git diff --check`,
   blobs de proveniência preservados, sem migração Alembic nem deploy.

## 6. Recomendação e autorização necessária

**Não aprovar uma implementação em um único ficheiro como se a
atomicidade estivesse resolvida.** A hipótese de porta opt-in merece
um *contrato test-only* e revisão do limite transacional antes de
alterar produção. O delta real pode exigir `registro_analise_service`,
`xml_service`, `usage_service` e, conforme a ordem do patch 912cb309,
`insights_engine`. Cada alteração deve ter sua intenção, teste e recibo.

**Estado:** proposta de desenho preparada; implementação, commits de
código, merge, push de código, migração, Railway e Vercel bloqueados.
Miguel deve ratificar **explicitamente** qualquer alteração a funções
compartilhadas, pois a ratificação atual cobre apenas desenho e
validação documental.
