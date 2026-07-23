# ADR-018 — Fronteira Soberana de Autorização, Pagamento, Projecção e Mutação do Memorial

**Estado:** RATIFICADA — APROVADA POR GPT E MIGUEL; AGUARDA COMMIT E PUSH DOCUMENTAIS
**Data:** 2026-07-23
**Bloco:** MISSION-008 / B14-SVC-04
**Repositório:** nexialistamentor/saas-fiscal-demo
**Branch de redacção:** `main`
**Baseline:** `HEAD = origin/main = c0b6337887b7313bcc3168ff8d654d43fe15e9e2`
**Gate tratado:** `ADR-013-FRONTEIRA-001`
**Depende de:** ADR-013 v1.3 e REPORT-002

---

## 1. Natureza e autoridade

Esta ADR é uma decisão arquitectural ratificada. Não implementa as decisões aqui
formuladas e não altera código, testes, migrations, modelo de dados,
semântica HTTP em produção, gerador PDF ou integração do
`MemorialValidatorAgent`.

As decisões foram determinadas pela autoridade GPT na MISSION-008,
transcritas neste artefacto, aprovadas em auditoria GPT em 2026-07-23 e
ratificadas expressamente por Miguel em 2026-07-23. O commit documental
isolado e o push permanecem pendentes.

A decisão arquitectural `ADR-013-FRONTEIRA-001` foi **RESOLVIDA** pela
ADR-018. A implementação produtiva continua **BLOQUEADA** e exige
missão separada.

## 2. Contexto e evidências

Foram interpretadas, sem alteração, as seguintes fontes:

- `docs/ADR-013-MIGRACAO-L3-MEMORIAL-VALIDATOR.md`;
- `docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md`;
- `app/routes/relatorio_router.py`;
- `app/services/memorial_service.py`;
- `app/security.py`;
- `app/routers/dashboard_router.py`;
- `app/services/pdf_report_service.py`;
- `app/models.py`;
- `tests/test_ops12_f6_memorial_contract.py`;
- `tests/test_e2e_bloco2_memorial.py`.

A ADR-013 v1.3 fechou B14.3E como canário contratual isolado. A
implementação do commit
`2042d5291a303e0abe67fe7f7184b363e1121167` não criou reader,
projector, ligação a rota, autorização produtiva, política de
pagamento, mutação, publicação, scheduler, registry ou executor
produtivo.

O REPORT-002 demonstrou que a fronteira produtiva continua aberta. Os
dois endpoints:

```text
GET /relatorio/memorial/{relatorio_id}
GET /relatorio/memorial/{relatorio_id}/pdf
```

executam actualmente, em essência:

```text
coletar_contexto_memorial(...)
→ 404
→ comparação directa de user_id
→ 403
→ verificação de pago
→ 402
→ geração/retorno
→ marcar_memorial_gerado(...)
```

Assim, o contexto fiscal rico é materializado antes da autorização e
do pagamento. `coletar_contexto_memorial()` inclui relatório rico,
resultados integrais de engines, alertas, insights e referências legais
gerais.

O memorial autoriza apenas pela igualdade directa de `user_id`. Em
contraste, `verificar_acesso_relatorio()` aceita o criador ou o
proprietário da empresa associada. O helper é substituível; a política
institucional precisa de existir independentemente dele.

`marcar_memorial_gerado()` consulta somente por ID, altera
`memorial_gerado=True` e executa `db.commit()` internamente. Não recebe
actor ou tenant, não reconfirma empresa ou pagamento e pode confirmar
trabalho exterior pendente na mesma `Session`.

Os testes HTTP existentes exigem colector antes de 403 e 402 e
marcação no GET 200; somente provam ausência de colector no 401. Os
testes PDF provam 402, 200 e cabeçalho `%PDF`, mas não provam isolamento
de tenant, ausência de leitura rica, geração e mutação nos caminhos
negados, ordem dos gates, ausência de commit ou estado final de
`memorial_gerado`.

## 3. Problema

A fronteira actual mistura localização, autorização, pagamento,
materialização fiscal, representação e mutação. Isso permite leitura
fiscal rica antes dos gates, diverge da política partilhada, transforma
GET em operação de escrita e entrega autoridade transaccional a um
helper sem contexto soberano.

Também existe incompatibilidade entre o dicionário rico do serviço e o
contrato mínimo `MemorialValidatorContext` v1. Uma ligação mecânica
entre ambos violaria a fronteira ratificada em B14.3E.

## 4. D1 — Política canónica de autorização

Um actor autenticado está autorizado quando:

```text
relatorio.user_id == usuario.id

OU, quando relatorio.empresa_id não é None:

existe Empresa.id == relatorio.empresa_id
E Empresa.user_id == usuario.id
```

Consequências:

- o criador directo continua autorizado;
- o proprietário da empresa associada também fica autorizado;
- relatório sem empresa só pode ser acedido pelo criador;
- actor sem qualquer vínculo recebe 403;
- `pago=True` nunca substitui autorização;
- possuir ou conhecer o ID nunca concede autorização.

Esta política corresponde semanticamente ao comportamento actual de
`verificar_acesso_relatorio()`, mas não depende desse helper. A
política é canónica; o helper é uma implementação substituível.

Não são decididos aqui acesso administrativo, partilha, delegação,
contabilista externo, transferência de empresa, token público ou
suporte.

## 5. D2 — Ordem canónica dos gates

Depois da autenticação, a ordem obrigatória é:

1. preflight mínimo do relatório;
2. 404 — relatório inexistente;
3. autorização;
4. 403 — actor sem vínculo;
5. pagamento;
6. 402 — actor autorizado, mas relatório não pago;
7. materialização rica;
8. projecção mínima L3, quando solicitada por missão futura;
9. geração JSON ou PDF;
10. resposta.

A semântica proposta é:

| Estado | Significado |
|---|---|
| 401 | autenticação ausente ou inválida |
| 404 | relatório não existe |
| 403 | relatório existe, mas o actor não está autorizado |
| 402 | actor autorizado, mas o relatório não está pago |
| 200 | actor autorizado, relatório pago e representação concluída |

É proibido materializar engines, alertas, insights ou referências antes
da autorização e do pagamento. Também é proibido gerar PDF, criar
missão L3 ou mutar estado antes desses gates.

A distinção entre 404 e 403 revela estados diferentes do recurso. Esta
ADR preserva o contrato observado; eventual resposta uniforme para
mitigar enumeração fica fora do escopo.

## 6. D3 — Preflight mínimo

Antes de concluir 404, 403 e 402, a única leitura de domínio permitida
é um preflight com:

```text
id
user_id
empresa_id
pago
```

Quando necessário para provar vínculo, pode existir consulta adicional
a `Empresa`, limitada a:

```text
Empresa.id == relatorio.empresa_id
Empresa.user_id == usuario.id
```

O preflight não pode materializar `resultado_json`, `fingerprint`,
`score_resultante`, `tempo_execucao`, `xml_chave`, engines, resultados
de engine, alertas, insights, `valor_estimado`, recomendação,
referências legais, fundamentos, URLs, conteúdo XML, PDF ou contexto
L3.

As provas negativas futuras são:

| Resposta | Leitura permitida | Proibições |
|---|---|---|
| 401 | nenhuma leitura de domínio | preflight, contexto, PDF e mutação |
| 404 | somente preflight | empresa, contexto rico, PDF e mutação |
| 403 | preflight e prova mínima de empresa, quando aplicável | contexto rico, PDF e mutação |
| 402 | preflight e autorização | contexto rico, PDF e mutação |

“Sem leitura” significa sem materialização fiscal rica. A abertura da
`Session`, por si só, não constitui leitura fiscal.

## 7. D4 — Barreira de materialização

`coletar_contexto_memorial()` ou qualquer substituto rico somente pode
ser chamado quando as três condições já forem verdadeiras:

```text
relatório existente
E actor autorizado
E pago == True
```

A materialização não decide autorização, e a autorização não
materializa contexto. A rota deve separar preflight, autorização,
pagamento, materialização e representação.

É proibida uma função única que consulte tudo, decida acesso e
pagamento, gere saída, altere estado e faça commit.

## 8. D5 — Contexto rico e projecção mínima L3

Fica conceptualmente autorizada uma futura projecção para o
`MemorialValidatorAgent`, sem autorizar a sua implementação nesta
missão.

Essa projecção não é o dicionário rico nem o payload do PDF. Não
transporta `resultado_json`, valores fiscais, descrições, URLs ou
objectos ORM e não executa agente legado nem adapter automaticamente.

A saída deve corresponder exactamente a `MemorialValidatorContext` v1:

```text
empresa_id
relatorio_id

relatorio:
  id
  empresa_id
  status
  total_alertas

engines:
  engine_nome

referencias_legais:
  fundamento
```

A projecção futura deve:

- ocorrer somente depois dos gates 404/403/402;
- seleccionar campos explicitamente;
- devolver apenas tipos primitivos;
- ser read-only e determinística;
- não executar `commit`, `rollback` ou `flush`;
- não chamar PDF, adapter, agente legado, LLM, filesystem ou HTTP.

São proibidos defaults silenciosos, incluindo:

```text
empresa_id ausente  → 0
status ausente      → "desconhecido"
total_alertas ausente → 0
engine_nome vazio   → string substituta
fundamento ausente  → texto inventado
```

Uma fonte incapaz de formar o contrato estrito deve falhar com erro
sanitizado da fronteira. Esta ADR não define o código público.

Como o contrato exige `empresa_id` positivo, relatório com
`empresa_id=None` continua sujeito à política HTTP, mas não é elegível
para missão L3 v1. Não recebe ID fabricado e exige evolução contratual
ou ADR própria.

O determinismo futuro exige engines ordenadas por `criado_em` e `id`,
referências ordenadas por `codigo` e `id` na fonte, tuplos em ordem
estável e empates desfeitos por ID. Engines duplicadas por nome devem
ser detectadas pela projecção, nunca silenciosamente deduplicadas. Esta
ADR não cria constraint de banco.

## 9. D6 — GET é read-only

As duas rotas GET do memorial devem ser semanticamente read-only. A
implementação futura deve remover delas:

- `marcar_memorial_gerado(...)`;
- `db.commit()`, `db.rollback()` e `db.flush()`;
- `UPDATE`, `INSERT` e `DELETE`.

O retorno JSON não marca geração. Gerar bytes em memória não marca
publicação. Criar `StreamingResponse` não prova entrega.

### 9.1 Semântica não soberana de `memorial_gerado`

O significado actual é ambíguo: consulta, construção, início da
resposta, entrega, download ou publicação.

Até existir comando ou evento explícito:

- GET não altera `memorial_gerado`;
- `memorial_gerado` não prova entrega;
- `memorial_gerado` não prova publicação;
- `memorial_gerado` não prova consumo.

A coluna pode permanecer por compatibilidade, mas não constitui
evidência soberana.

## 10. D7 — Escrita futura exige comando explícito

Qualquer marcação futura de exportação, publicação ou entrega exige ADR
e comando separado de GET. Esse comando deverá:

- identificar actor, tenant e relatório;
- reconfirmar existência, autorização e pagamento;
- declarar tipo de evento e instante;
- declarar `idempotency key`;
- possuir fronteira transaccional própria;
- não depender de `Session` com trabalho exterior pendente;
- produzir evidência auditável;
- não afirmar entrega sem prova.

Esta ADR não cria endpoint e não escolhe POST, outbox, evento ou tabela.
Determina apenas que a escrita não pode permanecer escondida em GET.

## 11. D8 — Autoridade transaccional

Serviços read-only não podem executar `commit`, `rollback` ou `flush`.
Um serviço que recebe `Session` externa não confirma nem reverte
trabalho que não criou.

Numa escrita futura:

- a unidade de aplicação controla a transacção;
- autorização e pagamento são reconfirmados;
- rollback fica limitado à unidade criada;
- commit interno genérico em helper é proibido;
- savepoint ou `Session` dedicada exigem decisão de implementação.

Esta ADR decide somente a fronteira transaccional do memorial e não
institui política transaccional L3 global.

## 12. D9 — Integração do agente continua bloqueada

Mesmo depois da ratificação documental, continua proibido:

- ligar o adapter à rota;
- criar missão automaticamente;
- registar no registry;
- ligar ao scheduler;
- executar em modo activo;
- publicar diagnóstico;
- bloquear exportação pelo agente;
- escrever resultado;
- alterar `publication_allowed=False`.

A sequência posterior obrigatória é:

```text
ADR-018 ratificada
→ missão de implementação HTTP/read-only
→ testes dirigidos
→ suite global
→ commit
→ push
→ missão própria para projector/reader L3
→ testes do projector
→ commit
→ avaliar integração produtiva em sombra
```

A ADR-018 resolve uma decisão; não autoriza implementação.

## 13. Provas obrigatórias futuras

Os testes deverão cobrir ambas as rotas, JSON e PDF.

### 13.1 Matriz HTTP

- **401:** status 401; nenhum preflight, colector, projector, PDF,
  marcação ou commit.
- **404:** status 404; somente preflight; nenhum acesso a empresa,
  contexto rico, projector, PDF, mutação ou commit.
- **403:** relatório existente, criador diferente e empresa ausente ou
  alheia; apenas preflight e prova mínima; nenhum contexto rico,
  projector, PDF, mutação ou commit.
- **402:** autorização tanto por `user_id` como por empresa; autorização
  concluída; nenhum colector, projector, PDF, mutação ou commit.
- **200 JSON:** autorização por `user_id` e por empresa; preflight
  primeiro; autorização e pagamento antes do colector; colector uma
  vez; nenhum projector automático, marcação ou commit;
  `memorial_gerado` inalterado.
- **200 PDF:** autorização por `user_id` e por empresa; colector antes
  do gerador; gerador uma vez; bytes válidos; nenhuma marcação ou
  commit; `memorial_gerado` inalterado; falha do gerador sem alteração
  de estado.

### 13.2 Ordem

Spies ou fakes devem provar:

```text
preflight
→ autorização
→ pagamento
→ colector
→ gerador, apenas no PDF
→ resposta
```

Os testes devem falhar se o colector for chamado antes da autorização
ou pagamento, se o PDF for gerado antes do pagamento, ou se houver
marcação ou commit em GET.

### 13.3 Projecção mínima

Uma missão futura deve provar:

- shape exacto;
- ausência de extras e ORM;
- ausência de `resultado_json`, valores fiscais e URLs;
- `empresa_id=None` bloqueia elegibilidade;
- nenhum default para `status`, `total_alertas` ou `engine_nome`;
- ordem estável e desempate por ID;
- duplicação de engine detectada;
- nenhum adapter, legado, escrita ou commit.

## 14. Exclusões e riscos não resolvidos

### 14.1 Referências legais

Ficam registados, sem resolução:

- convenção `Insight.tipo == ReferenciaLegal.codigo`;
- ausência de FK;
- selecção geral de até 200 referências;
- ausência de filtro por vigência efectiva;
- ausência de snapshot imutável;
- ausência de cobertura por insight;
- fallback PDF “base normativa em actualização”;
- alteração retroactiva de fundamento mutável.

Esses problemas exigem ADR normativa própria. Esta ADR não corrige o
fallback PDF nem declara cobertura jurídica.

### 14.2 Schema de `EngineResultado`

Ficam registados, sem resolução:

- `empresa_id` sem FK;
- `relatorio_analise_id` nullable;
- ausência de unique `(relatorio_analise_id, engine_nome)`;
- risco de duplicação e incoerência.

A projecção futura detectará ambiguidades. Migration pertence a missão
própria.

### 14.3 Entrega e publicação

Esta ADR não decide como provar recepção integral, download concluído,
armazenamento externo, publicação institucional, assinatura, timestamp
confiável, hash persistido ou identidade criptográfica.

## 15. Consequências

### 15.1 Positivas

- autorização e pagamento passam a preceder materialização fiscal rica;
- a política de vínculo torna-se institucional e independente de helper;
- GET recupera semântica read-only;
- a transacção deixa de ser confirmada por helper genérico;
- contexto de representação e contrato L3 deixam de ser confundidos;
- os caminhos de falha ganham provas negativas explícitas;
- `memorial_gerado` deixa de ser tratado como prova soberana.

### 15.2 Custos e incompatibilidades

- testes que cristalizam colector antes de 403/402 e marcação em GET
  terão de ser substituídos numa missão autorizada;
- a implementação exigirá preflight dedicado e separação explícita de
  fases;
- relatórios sem empresa continuam acessíveis pela política HTTP ao
  criador, mas não são elegíveis para `MemorialValidatorContext` v1;
- integração produtiva do agente continua adiada;
- riscos normativos, de schema e de entrega permanecem abertos.

## 16. Gate produtivo

```text
ADR-013-FRONTEIRA-001
decisão arquitectural RESOLVIDA pela ADR-018
estado documental: RATIFICADA
implementação produtiva: BLOQUEADA — exige missão separada
```

Nem a redacção nem a ratificação fecham a execução produtiva. O fecho
operacional dependerá de missão separada,
implementação autorizada, testes dirigidos, suite global, commit, push
e evidência posterior.

## 17. Critério de ratificação

O critério de ratificação foi satisfeito em 2026-07-23 por:

1. auditoria GPT aprovada;
2. ratificação expressa de Miguel aprovada.

A ADR-018 está ratificada. O commit documental isolado, o push e a
confirmação `HEAD = origin/main` permanecem pendentes e não autorizam,
por si, implementação produtiva.

## 18. Assinaturas

| Autoridade | Estado | Data |
|---|---|---|
| GPT — auditoria documental | APROVADA | 2026-07-23 |
| Miguel — ratificação final de produto | APROVADA | 2026-07-23 |
