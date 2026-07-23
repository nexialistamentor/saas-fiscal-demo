# REPORT-009 — Auditoria Pré-Implementação da Fronteira Soberana do Memorial

**Estado:** RATIFICADO — AUDITORIA GPT APROVADA E RATIFICAÇÃO DE MIGUEL REGISTADA; AGUARDA COMMIT E PUSH DOCUMENTAIS
**Data:** 2026-07-23
**Missão:** MISSION-009 / B14-SVC-05
**Natureza:** auditoria técnica read-only, sem implementação
**Repositório:** `nexialistamentor/saas-fiscal-demo`
**Branch esperada e observada:** `main`
**Baseline:** `HEAD = origin/main = 7f09135b97ed778db5baea0cd61c693a73c61f96`
**Decisão de origem:** `docs/ADR-018-FRONTEIRA-SOBERANA-MEMORIAL.md`
**Gate decisório:** `ADR-013-FRONTEIRA-001` RESOLVIDO pela ADR-018
**Gate de implementação:** a redacção da missão de implementação está AUTORIZADA; a implementação de código permanece BLOQUEADA até existir missão própria, auditada e ratificada

## 1. Conclusão executiva

A implementação mínima, segura e suficiente da primeira fase HTTP/read-only da
ADR-018 cabe em **dois ficheiros produtivos existentes** e **dois ficheiros de
testes existentes**:

- alterar `app/services/memorial_service.py` para acrescentar um helper público
  read-only de preflight que seleccione explicitamente apenas `id`, `user_id`,
  `empresa_id` e `pago`;
- alterar `app/routes/relatorio_router.py` para ambas as rotas executarem
  autenticação, preflight, 404, autorização canónica, 403, pagamento, 402 e só
  então o colector rico; remover das duas rotas a marcação;
- substituir/expandir `tests/test_ops12_f6_memorial_contract.py` para cobrir a
  matriz JSON e PDF, as provas negativas e a ordem;
- alterar `tests/test_e2e_bloco2_memorial.py` apenas para preservar as provas
  reais de PDF e acrescentar estado final read-only e isolamento essencial.

Não é necessário novo ficheiro, serviço, modelo, migration, schema, reader,
projector ou alteração do gerador PDF. `security.py` não precisa de alteração:
o predicado do seu helper corresponde à política canónica e aceita qualquer
objecto com os quatro atributos do preflight, mas reutilizá-lo mecanicamente
mudaria mensagens públicas 403. A rota deve preservar `"Acesso negado."`,
aplicando o predicado canónico ou normalizando apenas a excepção pública na
fronteira HTTP.

Não foi encontrado bloqueador técnico ainda não decidido pela ADR-018 para
esta primeira implementação. A projecção mínima L3 e a integração do agente
continuam explicitamente fora dela.

A Auditoria GPT foi **APROVADA em 2026-07-23** e a Ratificação de Miguel foi
**APROVADA em 2026-07-23**. Fica confirmada a classificação final **PRONTO PARA
REDACÇÃO DA MISSÃO DE IMPLEMENTAÇÃO** e autorizada a redacção dessa missão. A
implementação de código permanece **BLOQUEADA** até existir missão própria,
auditada e ratificada.

## 2. Estado Git inicial e preservação

Verificação inicial:

```text
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py

HEAD:        7f09135b97ed778db5baea0cd61c693a73c61f96
origin/main: 7f09135b97ed778db5baea0cd61c693a73c61f96
git diff --cached --name-only: vazio
```

Hashes SHA-256 iniciais:

| Ficheiro protegido | SHA-256 inicial |
|---|---|
| `app/agents/adapters/ag_encerramento.py` | `FDEAF1214EAEE4C3F92C08D6989581BF64A31A4BB2C2815F7027CBC57998527A` |
| `app/agents/engines/ag_encerramento.py` | `640F39160A545E3B1EE9135089D9113FCFA3293DFF9E423E5C96DA78A3A9ECA7` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `683A263E3FFB07ED88A5E72501705FAC9A54299D141BDE5024A78515D731E969` |
| `tests/test_ag_encerramento_mission_adapter.py` | `04FA3310D73CE86554380F378511A5E3589B398EB2B824694C173FA53D349CAF` |

## 3. Fontes consultadas

Foram consultadas as fontes obrigatórias:

- `docs/ADR-018-FRONTEIRA-SOBERANA-MEMORIAL.md`;
- `docs/ADR-013-MIGRACAO-L3-MEMORIAL-VALIDATOR.md`;
- `docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md`;
- `docs/REPORTS/REPORT-008-REDACAO-ADR-018-FRONTEIRA-MEMORIAL.md`;
- `app/routes/relatorio_router.py`;
- `app/services/memorial_service.py`;
- `app/security.py`;
- `app/routers/dashboard_router.py`;
- `app/services/pdf_report_service.py`;
- `app/models.py`;
- `app/database.py`;
- `app/main.py`;
- `tests/test_ops12_f6_memorial_contract.py`;
- `tests/test_e2e_bloco2_memorial.py`;
- `tests/conftest.py`.

As pesquisas foram limitadas aos símbolos e literais autorizados na missão.
Não foi feita exploração conceptual aberta. Referências adicionais apareceram
apenas como resultados exactos das pesquisas; não foram usadas para ampliar o
escopo.

## 4. Call graph actual

### 4.1 GET `/relatorio/memorial/{relatorio_id}`

Sequência provada:

1. FastAPI resolve `db: Session = Depends(get_db)` e
   `usuario_atual = Depends(get_usuario_atual)` na declaração da rota
   (`app/routes/relatorio_router.py:357-362`).
2. `get_usuario_atual` depende de OAuth2 e de `get_db`, valida token e consulta
   `User` por e-mail (`app/security.py:124-135`). Esta é leitura de identidade,
   não leitura do domínio memorial.
3. O corpo chama `coletar_contexto_memorial(db, relatorio_id)`
   (`relatorio_router.py:367`).
4. O colector consulta `RelatorioAnalise` completo
   (`app/services/memorial_service.py:67-71`).
5. Se existir, consulta, nesta ordem: todos os `EngineResultado` do relatório,
   ordenados por `criado_em` (`:75-80`); todos os `AlertaFiscal`, ordenados por
   `criado_em` (`:90-95`); `Insight` não superseded, ordenado por `criado_em`
   (`:107-115`); até 200 `ReferenciaLegal`, ordenadas por `codigo`
   (`:37-54`, chamada em `:127`).
6. O colector serializa o contexto rico e devolve-o (`:129-150`).
7. Só então a rota decide 404 (`relatorio_router.py:368-369`).
8. Compara directamente `rel["user_id"]` com `usuario_atual.id` e decide 403,
   `"Acesso negado."` (`:370-372`).
9. Testa `pago` e decide 402,
   `"Pagamento necessário para aceder ao memorial."` (`:373-374`).
10. Chama `marcar_memorial_gerado` (`:375`), que volta a consultar
    `RelatorioAnalise`, atribui `True` e executa `db.commit()`
    (`memorial_service.py:153-164`).
11. Cria a resposta devolvendo directamente o contexto (`relatorio_router.py:376`).

Sequência resumida actual:

```text
auth/User → relatório ORM rico → engines → alertas → insights → referências
→ 404 → user_id directo → 403 → pago → 402 → nova query do relatório
→ UPDATE memorial_gerado → commit → resposta JSON
```

Não há geração PDF nem projector L3 nesta rota.

### 4.2 GET `/relatorio/memorial/{relatorio_id}/pdf`

Os passos 1 a 9 são equivalentes, nas linhas
`app/routes/relatorio_router.py:379-396`. Depois:

10. `gerar_pdf_memorial(contexto)` constrói bytes em memória
    (`relatorio_router.py:398`; `pdf_report_service.py:206-366`).
11. `marcar_memorial_gerado` consulta, altera e faz commit
    (`relatorio_router.py:399`; `memorial_service.py:153-164`).
12. Só depois é criado `StreamingResponse`, com `application/pdf` e
    `attachment; filename=memorial-{relatorio_id}.pdf`
    (`relatorio_router.py:401-405`).

Sequência resumida actual:

```text
auth/User → relatório ORM rico → engines → alertas → insights → referências
→ 404 → user_id directo → 403 → pago → 402 → gerar PDF em memória
→ nova query do relatório → UPDATE memorial_gerado → commit
→ construir StreamingResponse
```

## 5. Autenticação e 401

**Classificação: PARCIAL.**

- A dependência `get_usuario_atual` é resolvida antes do corpo da rota pela
  injecção de dependências FastAPI; logo nenhuma instrução do corpo, incluindo
  preflight ou colector, ocorre antes de autenticação bem-sucedida.
- `get_usuario_atual` abre/reutiliza a dependência `get_db` e consulta somente
  `User` após validar o token (`security.py:127-135`). Não consulta relatório,
  empresa, engines, alertas, insights ou referências.
- O teste JSON 401 substitui `get_usuario_atual` por uma dependência que lança
  401 e instala funções falhadoras para colector e marcação
  (`tests/test_ops12_f6_memorial_contract.py:191-214`). Prova que essas duas
  funções não são chamadas.
- Não prova ausência de futuro preflight, projector, gerador PDF ou
  `Session.commit`; não existe equivalente 401 para a rota PDF.

Portanto, a precedência da autenticação é **PROVADA pelo framework e código**,
mas a prova automatizada negativa completa exigida pela ADR-018 é
**PARCIAL**.

## 6. Preflight mínimo

O resultado técnico deve conter exactamente `id`, `user_id`, `empresa_id` e
`pago`, em tipos primitivos ou num record imutável simples, sem carregar uma
instância completa de `RelatorioAnalise`.

| Alternativa | Campos carregados / lazy load | Contrato e teste | SQLite/PostgreSQL | Ficheiro novo | Risco rico |
|---|---|---|---|---|---|
| ORM completo `query(RelatorioAnalise)` | Todas as colunas, incluindo `resultado_json`, `fingerprint`, score e XML; sem relação lazy relevante, mas já viola D3 pela selecção | Simples, porém contrato demasiado amplo | Compatível | Não | Alto e efectivo |
| Colunas explícitas | SQL contém só quatro colunas; row/tuple não possui atributos fiscais extra; sem lazy load | Contrato mais claro e SQL facilmente inspeccionável | Compatível em ambos | Não | Mínimo |
| ORM com `load_only` | Instância ORM com quatro colunas inicialmente; qualquer acesso posterior a atributo diferido pode disparar lazy load | Mais frágil; exige teste negativo de lazy load | Compatível | Não | Médio |
| Helper read-only dedicado | Depende da consulta usada; com colunas explícitas torna a barreira nomeada e reutilizável pelas duas rotas | Melhor ponto de monkeypatch/spies e contrato único | Compatível | Não, se ficar no serviço existente | Mínimo |
| Reutilização de função existente | Não existe consulta preflight existente nas fontes; `coletar_contexto_memorial` é deliberadamente rico | Incompatível com D3 | — | — | Máximo |

**Recomendação:** acrescentar em `app/services/memorial_service.py` um helper
público dedicado de preflight usando consulta de colunas explícitas. O serviço
já é a fronteira de leitura do memorial, ambas as rotas precisam da mesma
operação e não há justificação para novo módulo. A função deve apenas consultar
e devolver `None` ou um valor com os quatro campos; não deve autorizar, pagar,
colectar, projectar, marcar, fazer `flush`, `commit` ou `rollback`.

Uma função privada na rota reduziria um ficheiro alterado, mas misturaria acesso
a dados com HTTP e teria menor reutilização/testabilidade. `load_only` é
desnecessariamente permissivo. Esta recomendação não autoriza implementação.

## 7. Política de autorização

### 7.1 Política canónica

ADR-018 D1 autoriza se:

```text
relatorio.user_id == usuario.id
OU
relatorio.empresa_id != None E existe Empresa(id=empresa_id, user_id=usuario.id)
```

### 7.2 Helper actual

`verificar_acesso_relatorio()`:

- retorna imediatamente quando `relatorio.user_id == usuario.id`;
- só chama `verificar_empresa_do_usuario` quando `relatorio.empresa_id` é
  truthy;
- nessa chamada faz uma consulta adicional a `Empresa` com os predicados
  exactos `Empresa.id == empresa_id` e `Empresa.user_id == usuario.id`;
- caso não haja empresa, lança 403 `"Acesso negado ao relatório"`;
- empresa inexistente/alheia produz 403
  `"Acesso negado: empresa não pertence ao usuário"`.

Evidência: `app/security.py:150-171`. O dashboard reutiliza este helper depois
de consultar o relatório e decidir 404 (`app/routers/dashboard_router.py:42-67`,
`:70-108`, `:111-125`).

Semanticamente, o helper implementa a política ratificada. Não exige classe ORM
nem relações: usa somente os atributos `user_id` e `empresa_id`; portanto pode
receber um record de preflight com esses atributos. A consulta de empresa só
ocorre quando o criador directo não coincide e `empresa_id` existe.

### 7.3 Diferença observável

A mensagem pública actual das duas rotas memorial é `"Acesso negado."`
(`relatorio_router.py:371-372`, `:393-394`). Reutilizar mecanicamente o helper
exporia uma de duas mensagens diferentes. O status permaneceria 403, mas o
contrato textual mudaria.

**Recomendação:** `security.py` não deve ser alterado. A rota deve aplicar a
política canónica preservando a sua mensagem pública. Duas formas tecnicamente
válidas são reutilizar o helper e converter apenas qualquer 403 de autorização
para `"Acesso negado."` na fronteira, ou implementar na fronteira um pequeno
predicado que faça a consulta mínima de empresa. A primeira evita duplicar
política; exige teste explícito da mensagem. Não se recomenda substituição
mecânica.

## 8. Ordem 404/403/402 e barreira

Ordem actual observável de status: 401 → 404 → 403 → 402 → 200. Contudo, a
leitura rica antecede 404/403/402. A ordem necessária mantém os mesmos status,
mas desloca a barreira:

```text
401/auth
→ preflight(id,user_id,empresa_id,pago)
→ 404
→ autorização directa ou consulta mínima Empresa
→ 403
→ pago
→ 402
→ coletar_contexto_memorial
→ JSON, ou gerar_pdf_memorial
→ resposta 200
```

O ponto exacto de bloqueio é imediatamente depois do preflight e antes da
chamada actual ao colector. Até os três gates terem passado, devem ser
impossíveis: consultas a engines, alertas, insights e referências; colector;
projector L3; gerador PDF; marcação; commit.

Esta ordem pode ser implementada sem alterar modelos, migrations, schema,
contratos L3 ou gerador PDF.

## 9. Materialização rica

`coletar_contexto_memorial()` executa cinco consultas, quando o relatório
existe:

1. `RelatorioAnalise` ORM completo por ID;
2. `EngineResultado` por `relatorio_analise_id`, `criado_em ASC`;
3. `AlertaFiscal` por `relatorio_analise_id`, `criado_em ASC`;
4. `Insight` por relatório e `superseded == False`, `criado_em ASC`;
5. até 200 `ReferenciaLegal`, opcionalmente federais/UF, `codigo ASC`.

Serializa relatório (`id`, utilizador, empresa, tipo, chave XML, status,
tempo, alertas, score, `resultado_json`, fingerprint, pago,
`memorial_gerado`, data), resultados integrais das engines, alertas, insights
com valores/recomendação e referências com fundamento, vigência e URL
(`app/services/memorial_service.py:57-150`).

Não há relações ORM percorridas nem acesso a atributos diferidos configurado
na função; as cinco consultas são explícitas. As serializações usam apenas
colunas já carregadas. Não chama serviços indirectos excepto
`listar_referencias_legais`, no mesmo ficheiro. Não escreve, não chama
`flush`, `commit` ou `rollback`.

Conclusões:

- pode permanecer sem alteração na primeira implementação, desde que só seja
  chamada depois dos gates;
- não precisa ser separada nem movida para novo serviço;
- o retorno actual deve permanecer para compatibilidade do JSON 200 e input
  do PDF;
- nenhuma alteração da projecção rica é necessária para tornar GET read-only;
- contexto rico não é `MemorialValidatorContext`; nenhum projector L3 deve ser
  criado ou chamado nesta implementação.

## 10. `memorial_gerado` e mutação

Pesquisa exacta comprovou:

- modelo: `RelatorioAnalise.memorial_gerado`, booleano, default `False`,
  non-null (`app/models.py:586-615`);
- leitura/serialização: incluída no dicionário rico
  (`memorial_service.py:130-145`);
- escrita: somente `marcar_memorial_gerado`, que consulta por ID, atribui
  `True` e faz commit (`:153-164`);
- call sites produtivos: apenas os dois GET
  (`app/routes/relatorio_router.py:375`, `:399`);
- testes: apenas o teste de contrato monkeypatcha a função; os E2E não
  verificam o campo;
- ADR-018 e relatórios anteriores documentam a coluna e a perda de valor
  soberano.

Não foi provado qualquer consumidor funcional que dependa de a chamada GET
alterar a coluna. Remover as duas chamadas quebra somente a expectativa
histórica artificial do teste JSON 200. A função pode permanecer sem uso por
compatibilidade e para evitar escopo oportunista; não deve ser removida na
primeira implementação. Manter a coluna sem escrever é expressamente permitido
pela ADR-018 e não exige migration.

O teste `test_f6_memorial_retorna_200_com_contexto` deve ser **SUBSTITUÍDO** na
parte que exige uma marcação. Os restantes testes que apenas esperam lista
vazia de marcação devem passar a usar fail-fast para marcação/commit.

## 11. Autoridade transaccional

`SessionLocal` está configurada com `autocommit=False` e `autoflush=False`
(`app/database.py:121-125`). `get_db` abre, faz `yield` e no `finally` apenas
fecha a sessão (`:173-178`): não há commit ou rollback automático explícito.

O commit interno actual pode confirmar trabalho exterior pendente na mesma
sessão. A marcação também faz uma segunda consulta e uma escrita desnecessárias.
Remover as duas chamadas a `marcar_memorial_gerado` elimina todo commit
explícito do fluxo GET do memorial. O colector não chama outras rotinas
transaccionais.

Com `autoflush=False`, as queries não provocam flush automático. Fechar uma
sessão sem commit não persiste alterações; como o novo fluxo não atribui
atributos, adiciona ou apaga entidades, ele permanece read-only. `rollback()`
explícito seria contrário a D8 e poderia reverter trabalho exterior. Não é
necessária sessão dedicada nem política transaccional L3 global.

Prova futura: monkeypatch/spies devem fazer `Session.commit`, `flush` e
`rollback` falhar se chamados no fluxo; a matriz exige especialmente `commit`.

## 12. PDF

`gerar_pdf_memorial(contexto)` recebe o dicionário rico, cria `BytesIO` e um
canvas ReportLab, lê apenas o input, escreve no buffer, chama `save`, faz
`seek(0)` e devolve o buffer (`app/services/pdf_report_service.py:206-366`).

Não recebe sessão, não consulta banco, não altera ORM, não usa filesystem e não
faz HTTP. Os efeitos são memória/CPU e timestamp UTC. Excepções de estrutura,
conversão ou ReportLab propagam antes da criação da resposta.

Pode permanecer sem alteração. Hoje, uma falha do gerador ocorre antes da
marcação; portanto não persiste a marcação. Depois de remover a marcação, tanto
falha como sucesso ficam sem mutação. Nenhum teste actual força falha do
gerador. Deve ser acrescentado teste de contrato PDF com gerador falhador,
estado `memorial_gerado` inalterado e zero marcação/commit. O conteúdo normativo
e o fallback permanecem fora do escopo.

## 13. Auditoria dos testes actuais

### 13.1 `tests/test_ops12_f6_memorial_contract.py`

| Teste / linhas | Prova actual | Lacuna ou comportamento errado | Classificação |
|---|---|---|---|
| `test_f6_memorial_retorna_200_com_contexto`, 45-76 | JSON 200, contexto exacto, colector uma vez | Exige marcação uma vez; não prova preflight, empresa, ordem ou commit | SUBSTITUIR |
| `test_f6_memorial_inexistente_retorna_404`, 83-112 | 404/mensagem e sem marcação | Usa colector como lookup, logo cristaliza leitura rica antes de 404; não prova empresa/commit | SUBSTITUIR |
| `test_f6_memorial_outro_utilizador_retorna_403`, 119-148 | 403/mensagem e sem marcação | Exige colector chamado antes do 403; só caso sem política de empresa | SUBSTITUIR |
| `test_f6_memorial_nao_pago_retorna_402`, 155-184 | 402/mensagem e sem marcação | Exige colector antes do 402; só autorização por user_id | SUBSTITUIR |
| `test_f6_memorial_sem_auth_retorna_401`, 191-214 | 401 antes de colector/marcação | Manter intenção, mas ampliar para preflight/projector/PDF/commit e duplicar para PDF | ALTERAR |

Todos usam monkeypatch e dependency overrides; nenhum usa DB real. `_DBFake`
não observa queries nem transacções. A ordem só é implicitamente demonstrada
pela ocorrência/não ocorrência de colector e marcação; não existe spy de
eventos. Ausência de leitura rica é provada apenas no 401. Ausência de mutação
é parcial (função não chamada), e ausência de commit nunca é provada.

### 13.2 Secções memorial de `tests/test_e2e_bloco2_memorial.py`

Todos os casos criam um utilizador e uma empresa pertencente a ele, autenticam,
aceitam termos e geram o relatório por upload (`:29-75`, `:128-204`).

| Teste | Pagamento/tenant/status | O que prova | Lacunas | Classificação |
|---|---|---|---|---|
| `test_e2e_b2_n1_memorial_sem_pagamento_retorna_402`, 130-148 | relatório do próprio user/empresa, default não pago; 402 | gate de pagamento real | não prova colector/gerador/mutação/commit/estado/ordem | ALTERAR |
| `test_e2e_b2_p3_memorial_com_pagamento_retorna_200`, 150-176 | actualiza `pago=True`; 200 | PDF acessível após pagamento | não verifica bytes, headers, tenant, marcação ou ordem | MANTER, com cobertura complementar |
| `test_e2e_b2_p4_memorial_pdf_bytes_validos`, 178-204 | pago; 200 | bytes começam `%PDF` | não verifica headers, estado, tenant ou falha | ALTERAR |

Os três casos têm apenas o tenant proprietário; não existe empresa alheia,
autorização por empresa com criador diferente, relatório sem empresa, 401,
404, 403 ou falha de gerador. Os testes não observam
`memorial_gerado`; no comportamento actual os dois 200 o deixam `True`, mas
isso não é assertado. Nenhum prova ordem de chamadas.

## 14. Matriz futura obrigatória

Convenções das assertions:

- `P`: preflight uma vez;
- `E`: consulta mínima de empresa uma vez, apenas se necessária;
- `C`: colector rico;
- `L3`: projector (deve ser zero em toda esta primeira implementação);
- `G`: gerador PDF;
- `M`: marcação;
- `K`: commit;
- `MG`: valor persistido de `memorial_gerado`;
- ordem usa uma lista de eventos explícita.

### 14.1 JSON

| Caso | Status | Assertions exactas |
|---|---:|---|
| 401 | 401 | `P=E=C=L3=G=M=K=0`; nenhuma leitura de domínio; `MG` inalterado; eventos apenas autenticação falhada |
| 404 | 404 | `P=1`; `E=C=L3=G=M=K=0`; `MG` inalterado; ordem `[P,404]` |
| 403 sem empresa | 403 | `P=1`; `E=C=L3=G=M=K=0`; mensagem `"Acesso negado."`; ordem `[P,authz,403]` |
| 403 empresa alheia | 403 | `P=1,E=1`; `C=L3=G=M=K=0`; consulta E contém ambos `id` e `user_id`; ordem `[P,E,403]` |
| 402 por `user_id` | 402 | `P=1,E=0`; `C=L3=G=M=K=0`; mensagem 402 preservada; ordem `[P,authz,pago,402]` |
| 402 por empresa | 402 | `P=1,E=1`; `C=L3=G=M=K=0`; ordem `[P,E,pago,402]` |
| 200 por `user_id` | 200 | `P=1,E=0,C=1`; `L3=G=M=K=0`; JSON igual ao contexto rico; `MG` inalterado; ordem `[P,authz,pago,C,resposta]` |
| 200 por empresa | 200 | `P=1,E=1,C=1`; `L3=G=M=K=0`; JSON preservado; `MG` inalterado; ordem `[P,E,pago,C,resposta]` |

### 14.2 PDF

| Caso | Status | Assertions exactas |
|---|---:|---|
| 401 | 401 | `P=E=C=L3=G=M=K=0`; `MG` inalterado |
| 404 | 404 | `P=1`; `E=C=L3=G=M=K=0`; ordem `[P,404]`; `MG` inalterado |
| 403 sem empresa | 403 | `P=1`; `E=C=L3=G=M=K=0`; mensagem preservada; `MG` inalterado |
| 403 empresa alheia | 403 | `P=1,E=1`; `C=L3=G=M=K=0`; ordem `[P,E,403]`; `MG` inalterado |
| 402 por `user_id` | 402 | `P=1,E=0`; `C=L3=G=M=K=0`; ordem `[P,authz,pago,402]`; `MG` inalterado |
| 402 por empresa | 402 | `P=1,E=1`; `C=L3=G=M=K=0`; ordem `[P,E,pago,402]`; `MG` inalterado |
| 200 por `user_id` | 200 | `P=1,E=0,C=1,G=1`; `L3=M=K=0`; `%PDF`, media type e filename preservados; `MG` inalterado; ordem `[P,authz,pago,C,G,resposta]` |
| 200 por empresa | 200 | `P=1,E=1,C=1,G=1`; `L3=M=K=0`; mesmos headers/bytes; `MG` inalterado; ordem `[P,E,pago,C,G,resposta]` |
| falha do gerador | excepção/500 conforme TestClient | `P=1`, autorização e pago concluídos, `C=1,G=1`; `L3=M=K=0`; nenhuma resposta bem-sucedida; `MG` inalterado; ordem termina em `[C,G_falha]` |

## 15. Estratégia mínima de testes

Recomendação combinada:

1. **Contrato HTTP com dependency overrides e spies de ordem** no ficheiro
   OPS12: prova os dois endpoints, matriz completa, mensagens, número de
   chamadas e barreiras negativas sem duplicar fixtures caras.
2. **Helper de preflight com SQLite real**: poucos testes directos no mesmo
   ficheiro ou no E2E comprovam inexistente/existente, quatro valores e
   ausência de carregamento rico. Captura de SQL deve ser usada apenas neste
   ponto se necessária para provar que a instrução selecciona exactamente as
   quatro colunas; colunas explícitas tornam essa prova estável.
3. **E2E existente**: manter 402 e PDF válido; acrescentar verificação real de
   `memorial_gerado=False` antes/depois do 200 e um caso de tenant alheio ou de
   autorização por empresa. Não replicar toda a matriz E2E.
4. **Fail-fast transaccional**: monkeypatch de `Session.commit`, `flush` e
   `rollback` nos testes de contrato/integração deve falhar se chamado. Pelo
   menos `commit` é obrigatório em todos os GET.

Testes unitários da função de rota sem HTTP não acrescentam valor à injecção
FastAPI/401. Captura de todo SQL em toda a matriz seria frágil e redundante.

## 16. Resultados dos testes dirigidos

Comando exacto:

```text
python -m pytest -q tests/test_ops12_f6_memorial_contract.py
```

Resultado: exit code 0; `5 passed`; 0 falhas; 0 skips; 34 warnings; duração
pytest `0.50s` (tempo de comando observado `8.4s`). Warnings: 29 deprecações
SlowAPI e 5 de `datetime.utcnow()` em retenção de request log.

Comando exacto:

```text
python -m pytest -q tests/test_e2e_bloco2_memorial.py -k memorial
```

Resultado: exit code 0; `5 passed`; 0 falhas; 0 skips/deselected reportados;
131 warnings; duração pytest `1.98s` (tempo de comando observado `7.0s`).
Warnings de deprecação em SlowAPI, `datetime.utcnow()`, adapter SQLite e
SQLAlchemy.

Nenhuma suite global ou teste de agentes foi executado.

## 17. Matriz de ficheiros

| Ficheiro | Classificação | Motivo e evidência |
|---|---|---|
| `app/routes/relatorio_router.py` | ALTERAR | Contém as duas sequências erradas, import e chamadas de marcação (`:27`, `:357-405`); deve orquestrar gates antes do colector e preservar HTTP |
| `app/services/memorial_service.py` | ALTERAR | Local coerente para novo preflight explícito; colector rico fica intacto; marcação fica sem uso (`:57-164`) |
| `app/security.py` | NÃO ALTERAR | Helper já implementa predicado canónico e aceita atributos; mensagens são tratadas na fronteira (`:150-171`) |
| `app/routers/dashboard_router.py` | NÃO ALTERAR | Apenas consumidor existente do helper; prova semântica partilhada, fora das rotas memorial |
| `app/services/pdf_report_service.py` | NÃO ALTERAR | Gerador em memória, sem banco/mutação (`:206-366`) |
| `app/models.py` | NÃO ALTERAR | Quatro campos e coluna existentes (`:586-615`); ADR permite manter coluna |
| `app/database.py` | NÃO ALTERAR | `autocommit=False`, `autoflush=False`, encerramento sem commit (`:121-125`, `:173-178`) |
| `app/main.py` | NÃO ALTERAR | Montagem/lifespan não precisa mudar; nenhuma ligação L3 autorizada |
| `tests/test_ops12_f6_memorial_contract.py` | ALTERAR | Cinco testes incompletos; quatro cristalizam colector/marcação errados; deve alojar matriz e spies |
| `tests/test_e2e_bloco2_memorial.py` | ALTERAR | Deve provar estado read-only/tenant e preservar PDF real sem replicar matriz |
| `tests/conftest.py` | NÃO ALTERAR | Fixtures globais bastam; alterações específicas cabem nos dois testes |

**NOVO FICHEIRO NECESSÁRIO: nenhum.**
**Ficheiros INDETERMINADOS: nenhum.**

## 18. Decisão sobre helper, serviço e projecção

Decisão técnica: helper de preflight dentro de
`app/services/memorial_service.py`, consulta de colunas explícitas, nenhum
ficheiro novo.

Responsabilidade única: localizar o mínimo soberano do relatório antes dos
gates. Pode importar apenas tipos SQLAlchemy já usados e
`RelatorioAnalise`. Não deve importar PDF, security/HTTP, agentes, contratos
L3, filesystem ou serviços mutáveis.

Novo serviço read-only seria estrutura sem benefício para uma única query.
Função privada na rota reduziria separação e testabilidade. Alterar
`security.py` não é necessário. A materialização rica permanece separada por
ordem de chamadas; uma futura projecção mínima L3 requer missão própria e não
deve ser criada nesta fase.

## 19. Migration e schema

**Migration necessária: NÃO.**

- `memorial_gerado` permanece no modelo e banco, apenas deixa de ser escrito
  por GET;
- nenhuma coluna, constraint ou índice novo é requerido;
- `RelatorioAnalise` já contém os quatro campos de preflight;
- `EngineResultado` não é alterado;
- `ReferenciaLegal` não é alterada;
- não há alteração de contratos L3.

## 20. Compatibilidade externa

| Superfície | Resultado recomendado |
|---|---|
| Status 401/404/403/402/200 | Compatibilidade preservada; ordem ratificada internamente |
| Texto 403 | Preservar `"Acesso negado."`; risco se helper for usado mecanicamente |
| Texto 402 | Preservar `"Pagamento necessário para aceder ao memorial."` |
| JSON 200 | Shape rico actual preservado, incluindo valor pré-existente de `memorial_gerado` |
| Headers PDF | Preservar `application/pdf` e `attachment; filename=memorial-{id}.pdf` |
| Bytes/conteúdo PDF | Preservado; gerador inalterado |
| Ordem de consultas | Mudança intencional ratificada: preflight/autorização/pagamento antes do rico |
| `memorial_gerado` | Mudança intencional ratificada: deixa de mudar em GET |
| Autorização por empresa | Mudança intencional ratificada: passa a permitir proprietário da empresa |
| Testes históricos | Quatro contratos JSON precisam substituição; E2E deve deixar de tolerar mutação implícita |

Risco principal de regressão: reutilização mecânica do helper mudar mensagens;
consulta ORM completa ou `load_only` permitir leitura rica; manter import/call
de marcação; testes apenas de status deixarem passar ordem errada.

## 21. Escopo exacto recomendado para futura missão

### Ficheiros a alterar

```text
app/routes/relatorio_router.py
app/services/memorial_service.py
tests/test_ops12_f6_memorial_contract.py
tests/test_e2e_bloco2_memorial.py
```

### Ficheiros novos

Nenhum.

### Ficheiros explicitamente proibidos

```text
app/security.py
app/routers/dashboard_router.py
app/services/pdf_report_service.py
app/models.py
app/database.py
app/main.py
app/agents/**
app/agents/adapters/ag_encerramento.py
app/agents/engines/ag_encerramento.py
docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
tests/test_ag_encerramento_mission_adapter.py
docs/ADR-018-FRONTEIRA-SOBERANA-MEMORIAL.md
migrations/**
```

### Ordem de implementação proposta

1. Escrever primeiro testes de contrato para matriz/gates/ordem/fail-fast.
2. Acrescentar o helper de preflight por colunas explícitas.
3. Reordenar ambas as rotas e preservar mensagens/shape/headers.
4. Remover import e chamadas de `marcar_memorial_gerado` apenas da rota; manter
   a função e coluna.
5. Ajustar E2E para estado final `memorial_gerado=False` e cobertura mínima de
   tenant/autorização por empresa.
6. Executar os dois testes dirigidos.
7. Só após aprovação dirigida, executar suite global como gate separado.

### Testes dirigidos

```text
python -m pytest -q tests/test_ops12_f6_memorial_contract.py
python -m pytest -q tests/test_e2e_bloco2_memorial.py -k memorial
```

### Critérios de conclusão

- matriz da secção 14 verde para ambas as rotas;
- preflight selecciona exactamente quatro colunas;
- 401/404/403/402 não materializam contexto rico;
- autorização por criador e por empresa funciona;
- mensagens e respostas externas são preservadas;
- nenhum projector/agente é chamado;
- nenhum GET chama marcação, `commit`, `rollback` ou `flush`;
- `memorial_gerado` permanece inalterado em sucesso e falha;
- PDF só é gerado depois dos gates;
- nenhum ficheiro fora do escopo muda;
- suite global verde antes de qualquer commit.

### Riscos residuais

- política normativa/referências e fallback PDF continuam fora do escopo;
- projecção `MemorialValidatorContext` e integração do agente continuam
  bloqueadas;
- coluna histórica mantém semântica não soberana;
- testes com monkeypatch precisam pelo menos uma prova SQL/SQLite real para
  impedir regressão do preflight;
- mudanças concorrentes nos ficheiros protegidos continuam fora do escopo.

## 22. Blockers

**Nenhum bloqueador técnico adicional identificado** para redigir uma missão
de implementação HTTP/read-only dentro do escopo acima.

Questões de projector L3, elegibilidade com `empresa_id=None`, referências
legais, entrega/publicação e futura escrita não bloqueiam esta fase porque a
ADR-018 as separou e manteve fora da implementação inicial.

## 23. Classificação final

**PRONTO PARA REDACÇÃO DA MISSÃO DE IMPLEMENTAÇÃO**

Classificação final confirmada pela Auditoria GPT, **APROVADA em 2026-07-23**,
e pela Ratificação de Miguel, **APROVADA em 2026-07-23**. A redacção da missão
de implementação está autorizada. Esta ratificação não autoriza implementação
de código, que permanece **BLOQUEADA** até existir missão própria, auditada e
ratificada.

## 24. Estado Git final e integridade

As verificações finais devem registar, depois de concluído este documento:

```text
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/REPORTS/REPORT-009-AUDITORIA-PRE-IMPLEMENTACAO-FRONTEIRA-MEMORIAL.md

git diff --cached --name-only: vazio
```

Hashes finais dos ficheiros protegidos e hash final do REPORT-009 são
registados na verificação mecânica final abaixo. O SHA-256 do próprio relatório
não pode ser incorporado como valor literal nos seus próprios bytes sem
invalidar-se por auto-referência; por isso o valor final verificável é
registado no handoff externo, mantendo neste artefacto a declaração e o método.

| Ficheiro protegido | SHA-256 final |
|---|---|
| `app/agents/adapters/ag_encerramento.py` | `FDEAF1214EAEE4C3F92C08D6989581BF64A31A4BB2C2815F7027CBC57998527A` |
| `app/agents/engines/ag_encerramento.py` | `640F39160A545E3B1EE9135089D9113FCFA3293DFF9E423E5C96DA78A3A9ECA7` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `683A263E3FFB07ED88A5E72501705FAC9A54299D141BDE5024A78515D731E969` |
| `tests/test_ag_encerramento_mission_adapter.py` | `04FA3310D73CE86554380F378511A5E3589B398EB2B824694C173FA53D349CAF` |

```text
SHA-256 REPORT-009: REGISTADO NO HANDOFF MECÂNICO FINAL
Stage: VAZIO
Commit: NÃO CRIADO
Push: NÃO EFECTUADO
```

Nenhum código, teste, ADR, migration ou relatório anterior foi alterado por
esta missão. Nenhum ficheiro foi apagado, movido, renomeado, formatado ou
stageado. A implementação permanece bloqueada.

### Estado institucional

Auditoria GPT: **APROVADA em 2026-07-23**.

Ratificação de Miguel: **APROVADA em 2026-07-23**.

Estado institucional: **RATIFICADO**. Nenhuma implementação, teste novo, suite
global, commit, push ou deploy foi realizado por esta auditoria.

### Próxima autoridade

Verificação final → stage exclusivo do REPORT-009 → commit documental → push →
confirmação `HEAD = origin/main` → redacção da missão de implementação.
