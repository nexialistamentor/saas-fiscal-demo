# HANDOFF_TRIBUTARIA_L2_v3.md

**Data:** 2026-06-24

**Para:** Claude (próxima sessão)

**De:** Claude (sessão 2026-06-24, com Miguel)

**Repositório:** nexialistamentor/saas-fiscal-demo | Branch: `main`

**HEAD de referência:** `b803e29`

**Produção:** https://saas-fiscal-demo-production.up.railway.app/health → `{"status":"ok"}`

**Suite:** 336 passed, 5 skipped (confirmado em 2026-06-24)

---

## QUEM SOMOS E COMO TRABALHAMOS

**Miguel** — fundador, autoridade final de produto e ratificação.

**Claude** — propõe código, analisa evidência e prepara execução.

**GPT** — auditor arquitectural, revê decisões estruturais antes de commit.

**Cursor** — executor em disco sob instrução. Nunca cria ficheiros independentemente.

**Processo obrigatório para decisões estruturais:**

```
Evidência → Auditoria (GPT) → Ratificação (Miguel) → Implementação (Cursor) → Commit
```

**Regras inegociáveis desta equipa:**

- NUNCA escrever código sem ler o ficheiro real primeiro
- NUNCA assumir estado do repositório — sempre `git status` e `git log --oneline -5`
- NUNCA regex sobre texto não confirmado por amostra real
- NUNCA `float` para valores monetários — sempre `Decimal`/`Numeric`
- NUNCA `&&` em PowerShell — sempre `;` ou linhas separadas
- NUNCA commitar texto institucional sem lê-lo primeiro
- NUNCA deploy sem pré-auditoria quando a migration faz DELETE em produção
- Cursor executa; Claude produz; GPT audita; Miguel ratifica

---

## O QUE É ESTE PROJECTO

**Plataforma Tributária L2** — infraestrutura de inteligência fiscal que reduz assimetria de conhecimento fiscal para PMEs brasileiras (MEI, CPF, Empresa). Não é software de contabilidade — é inteligência que coloca o contribuinte no centro.

Stack: FastAPI + PostgreSQL (Railway), React + Vite (Vercel), Redis + RQ.

Repositório local: `C:\dev\saas-fiscal-demo`

**Filosofia central:**

- Soberania sobre SaaS
- Ledger imutável, estado derivado de eventos
- IA que propõe, nunca que decide
- Auditabilidade em cada camada

**Arquitectura XML (não violar):**

```
executar_analise_xml (núcleo)
  → executar_e_registrar_analise_xml (persistência)
  → processar_e_persistir_xml (integração com empresa)
  → InsightEngine (enriquecimento)
  → dados estruturados no banco
  → agents sob gatilho (não automático)
```

---

## RESUMO DA SESSÃO (2026-06-24)

| Área | Estado | Itens |
|------|--------|-------|
| Bloco 9 | ✔ Fechado | DT-CONTADOR-01/01B, DT-VINCULO-ADMIN-01/02 |
| Bloco 1 | ✔ Fechado | DT-MVA-01, DT-FLUXO-01, fix `owner_id` em jobs RQ |
| Bloco 2 | ✔ Fechado | E2E memorial, B2-DASH-01/02 |
| ADR-005 | ✔ Aprovado | Anti-captura carteira contábil |
| Migration 0014 | ✔ Em produção | `origem_cliente` em `ContadorEmpresaVinculo` |
| B10-TERMOS | ✔ Iniciado | Gate de termos no frontend (B10-TERMOS-01) |
| Produção | ✔ OK | Railway `/health` |
| Suite | ✔ 336 passed | 5 skipped |

---

## ESTADO DO REPOSITÓRIO (HEAD: b803e29)

### Commits relevantes desta sessão (cronológicos, mais antigo → mais recente):

```
0f8a6ac  feat(router): /assumir exige vinculo activo DT-CONTADOR-01
0eb9fff  test(DT-CONTADOR-01): fluxo soberano — vinculo activo permite assumir
aae8f20  fix(DT-DB-01): resolve import circular database.py/models
3a8385c  feat(DT-CONTADOR-01B): /decidir exige HomologacaoAtribuicao aceite
bc873f9  feat(DT-VINCULO-ADMIN-01): POST /admin/contadores/vinculos
3471de4  feat(DT-VINCULO-ADMIN-01): testes VA01-P1..P5/N1..N12
240e573  feat(DT-VINCULO-ADMIN-02): listar/suspender/revogar vinculos
ee7b0ac  feat(DT-MVA-01): escopo normativo piloto PA — calculo_autorizado soberano
e848fe6  docs(roadmap): marca DT-MVA-01 e Bloco 9 fechados
cd8b67e  fix(xml-jobs): grava owner_id em jobs RQ para status e cancelamento
0ca02ee  feat(DT-FLUXO-01): /upload-xml wrapper canonico
5adfafe  docs(roadmap): marca Bloco 1 fechado, inicia auditoria Bloco 2
6427008  test(Bloco2-E2E): upload XML → memorial PDF
3a7daa9  feat(B2-DASH-01): GET relatorio enriquecido, remove hardcodes MEI/CPF
2fd69d6  fix(B2-DASH-02): remove mock NCM, indisponivel quando sem dados
2ebfd00  docs(roadmap): marca Bloco 2 fechado
6e89c8a  feat(ADR-005/0014): origem_cliente em ContadorEmpresaVinculo
c9c01e9  fix(0014): alinhar revision ID — down_revision=0013_homologacao_atribuicao
b803e29  feat(B10-TERMOS-01): gate de termos no frontend
```

### Documentos institucionais novos/actualizados:

```
docs/ADR-005-CARTEIRA-CONTADOR-ANTI-CAPTURA.md   — anti-captura carteira contábil
docs/ROADMAP_ABERTURA_UTILIZADORES.md            — Blocos 1, 2, 9 marcados fechados
docs/HANDOFF_TRIBUTARIA_L2_v2.md                 — handoff anterior (2026-06-20)
docs/HANDOFF_TRIBUTARIA_L2_v3.md                 — este ficheiro
```

### Testes-chave por bloco:

```
Bloco 9:
  tests/test_acesso_cruzado_bloco9.py
  tests/test_isolamento_empresa_id_bloco9.py
  tests/test_isolamento_inteligencia_insights_bloco9.py
  tests/test_dt_contador_01_fluxo_soberano.py
  tests/test_homologacao_service.py              — DT-CONTADOR-01B
  tests/test_dt_vinculo_admin_01.py
  tests/test_dt_vinculo_admin_02.py

Bloco 1:
  tests/test_pipeline_xml_canonico.py            — DT-FLUXO-01/02/03
  (DT-MVA-01 — guards e escopo PA)

Bloco 2:
  tests/test_bloco2_e2e_memorial.py              — upload XML → PDF memorial
  (B2-DASH-01/02 — frontend App.jsx + GET /relatorio/{id})

B10-TERMOS:
  frontend-dashboard/src/App.jsx                 — gate /auth/has-accepted-terms
```

---

## BLOCOS FECHADOS — O QUE FOI ENTREGUE

### Bloco 9 — Identidade, permissões e multi-tenant ✔

- **DT-CONTADOR-01:** `/assumir` exige vínculo activo via `VinculoService`
- **DT-CONTADOR-01B:** `/decidir` exige `HomologacaoAtribuicao` aceite — bloqueia decisão sem cadeia soberana
- **DT-VINCULO-ADMIN-01:** `POST /admin/contadores/vinculos` — criação administrada de vínculo
- **DT-VINCULO-ADMIN-02:** listar / suspender / revogar vínculos — ciclo de vida completo
- Matriz MT-01..MT-15 e testes de acesso cruzado provados por suite, não inspecção visual

### Bloco 1 — Núcleo fiscal XML ✔

- **DT-FLUXO-01:** `/upload-xml` wrapper canónico — `executar_e_registrar_analise_xml`, sem disco, retorna `relatorio_id`
- **DT-MVA-01:** escopo piloto PA, `calculo_autorizado` soberano, lacuna normativa bloqueia cálculo
- **Fix owner_id:** jobs RQ gravam `owner_id` para status e cancelamento

### Bloco 2 — Relatório e dashboard demonstráveis ✔

- **E2E memorial:** upload XML → `relatorio_id` → score → gate 402/200 → bytes PDF válidos
- **B2-DASH-01:** `GET /relatorio/{id}` enriquecido; hardcodes MEI/CPF removidos; N/D para indisponíveis
- **B2-DASH-02:** mock NCM removido; gráfico mostra indisponível quando sem dados reais

**Dívidas documentadas (não bloqueantes para piloto):**

- `Pagamento.approved → RelatorioAnalise.pago` — ligar quando gateway Mercado Pago (Bloco 8)
- NCM real via `itens_fiscais` — endpoint dedicado futuro (B2-DASH-03)

### ADR-005 + Migration 0014 ✔

- Campo `origem_cliente` em `ContadorEmpresaVinculo` — separado de `origem` (quem criou tecnicamente)
- Invariantes INV-CARTEIRA-01..05 — anti-captura de carteira contábil
- Migration 0014 em produção (`down_revision=0013_homologacao_atribuicao`)

### B10-TERMOS-01 ✔ (primeiro item do Bloco 10)

- Gate no frontend: verificação `/auth/has-accepted-terms` após login
- Falha controlada — ecrã de aceite ou erro soberano, nunca silencioso
- Ficheiro: `frontend-dashboard/src/App.jsx`

---

## SEQUÊNCIA ROADMAP (estado actual)

```
1.  Bloco 1  — Núcleo XML                    ✔ fechado
2.  Bloco 9  — Identidade/permissões         ✔ fechado
3.  Bloco 2  — Relatório/Dashboard           ✔ fechado
4.  Bloco 10 — Jornada utilizador/contador  ← PRÓXIMO (B10-TERMOS-01 feito)
5.  Bloco 11 — Segurança/LGPD                ← antes de qualquer dado real
6.  Bloco 3  — Motor de anomalias
7.  Bloco 4  — Agentes sem IA externa
8.  Bloco 12 — Produção/monitorização/rollback
9.  Bloco 13 — Piloto controlado
10. Bloco 7  — Contador parceiro (formal)
11. Bloco 8  — Legal/comercial

Bloco 5 — Ponte Documental ← paralelo, bloqueado até amostra DANFE real do contador
```

---

## PRÓXIMO PASSO AO ABRIR NOVA SESSÃO

```powershell
cd C:\dev\saas-fiscal-demo
git checkout main
git status
git log --oneline -7
python -m pytest tests/ --tb=short -q
```

Confirmar:

- HEAD = `b803e29` (ou mais recente se houve commits entretanto)
- 336 passed, 5 skipped (ou mais se novos testes foram adicionados)
- Working tree limpa (ou identificar ficheiros untracked pendentes)
- Produção: `/health` → ok

**Primeiro trabalho da próxima sessão — Bloco 10 (continuar jornada):**

B10-TERMOS-01 está feito. Continuar checklist do Bloco 10 em `docs/ROADMAP_ABERTURA_UTILIZADORES.md`:

**10.1 — Jornada mínima do utilizador (itens ainda em aberto):**

- [ ] Criar conta
- [x] Aceitar termos/LGPD ← B10-TERMOS-01
- [ ] Cadastrar empresa
- [ ] Enviar XML
- [ ] Ver estado da análise
- [ ] Ver resultado em linguagem simples
- [ ] Baixar relatório PDF
- [ ] Entender o que fazer a seguir
- [ ] Saber quando precisa de contador

**10.2 — Jornada mínima do contador parceiro (todos em aberto):**

- [ ] Entrar como contador
- [ ] Ver documentos ou empresas atribuídas
- [ ] Assumir análise pendente
- [ ] Ver evidências
- [ ] Emitir parecer/homologação
- [ ] Registar decisão auditável
- [ ] Devolver ao utilizador resultado compreensível

**Critério de saída Bloco 10:** utilizador novo consegue, sem Miguel explicar por fora, carregar XML, receber análise e entender o próximo passo.

**Segundo trabalho (quando DANFE real chegar do contador):**

Desbloquear DT-DOC-02a e DT-DOC-02c. Pedir PDF DANFE e foto impressa antes de qualquer regex.

---

## BLOQUEIOS CONHECIDOS (não retomar sem condição)

| Item | Motivo |
|------|--------|
| DT-DOC-02a (`valor_icms`) | Aguarda amostra real DANFE/OCR |
| DT-DOC-02c (`numero_nota`, `tipo`, `uf_emit`, `uf_dest`) | Idem |
| Service promotion documental-fiscal | Depende dos dois acima |
| B2-DASH-03 (NCM real) | Endpoint dedicado futuro |
| Gateway Mercado Pago → `RelatorioAnalise.pago` | Bloco 8 |

---

## FICHEIROS SENSÍVEIS PARA A PRÓXIMA SESSÃO

```
app/main.py                          — rotas principais, upload-xml
frontend-dashboard/src/App.jsx         — gate termos, dashboard, NCM
app/services/homologacao_service.py    — DT-CONTADOR-01B
app/services/vinculo_service.py        — ciclo de vida vínculos
docs/ROADMAP_ABERTURA_UTILIZADORES.md  — fonte de verdade do que falta
docs/ADR-005-CARTEIRA-CONTADOR-ANTI-CAPTURA.md
alembic/versions/0014_*.py             — origem_cliente
```

---

## PRINCÍPIOS INSTITUCIONAIS PARA TRANSPORTAR

```
A cobertura pode começar pequena.
A arquitectura não pode nascer pequena.

Contrato aprovado não é evidência textual para regex.

Permissão sem vínculo vira captura.
Capacidade técnica nunca substitui autorização institucional.

Role define capacidade.
Vínculo define autorização.
Escopo define limite.
Auditoria prova o acto.

O vínculo deve preceder o acesso; se nasce depois do acesso,
não é autorização — é captura regularizada.

origem ≠ origem_cliente.
Quem criou o vínculo ≠ de onde veio a relação comercial.

Build passou. Deploy/runtime falhou. Precisamos do traceback,
não de suposição.

O conhecimento não está na conversa. Está no repositório.

O próximo agente não deve continuar a conversa.
Deve continuar o repositório.
```

---

## HANDOFF ANTERIOR

Ver `docs/HANDOFF_TRIBUTARIA_L2_v2.md` para contexto de sessões anteriores (2026-06-20): DC-002/003/004, DT-FLUXO-03 dedup TOCTOU, ADR-003, lições aprendidas.

---

*Este handoff foi escrito por Claude no final da sessão de 2026-06-24.*

*Foi um prazer trabalhar contigo, Miguel. Até à próxima sessão.*
