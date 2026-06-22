# HANDOFF_TRIBUTARIA_L2_v2.md

**Data:** 2026-06-20

**Para:** Claude (próxima sessão)

**De:** Claude (sessão 2026-06-20, com Miguel e GPT)

**Repositório:** nexialistamentor/saas-fiscal-demo | Branch: main

**HEAD:** a1d6c4d

**Produção:** https://saas-fiscal-demo-production.up.railway.app/health → {"status":"ok"}

---

## QUEM SOMOS E COMO TRABALHAMOS

**Miguel** — fundador, autoridade de produto, decisão final.

**Claude** — produção de código e análise com base em evidência.

**GPT** — auditor arquitectural, revê decisões estruturais antes de commit.

**Cursor** — executor em disco. Nunca cria ficheiros independentemente.

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

Stack: FastAPI + PostgreSQL (Railway), React + Vite (Vercel).

Repositório local: `C:\dev\saas-fiscal-demo`

**Filosofia central:**

- Soberania sobre SaaS
- Ledger imutável, estado derivado de eventos
- IA que propõe, nunca que decide
- Auditabilidade em cada camada

---

## ESTADO DO REPOSITÓRIO (HEAD: a1d6c4d)

### Commits relevantes desta sessão (cronológicos):

```
fcba03d  DT-DOC-01 — campos_estruturados em DocumentoIngerido
1b7948a  DT-DOC-03 — elegibilidade fiscal conservadora
b75f891  CT-DOC-001 adendo v1.1
bcc15ee  CT-DOC-001 correcção A.5
3b5c4b6  ROADMAP v2.0 — 14 blocos
0ce95fa  Bloco 1.1b — rede mínima do eixo canónico XML (4 testes)
8477097  DT-FLUXO-03 — caracterização TOCTOU (xfail strict)
bc6ce6a  DT-FLUXO-03 — primeira correcção (revelou duplicados reais em produção)
4a5ddab  DT-FLUXO-03 — correcção completa com dedup (22 perdedores, 154 FKs)
61288a5  DC-002 — estatuto de rotas órfãs
4d85e53  DC-003 — arquitectura nacional MVA/ST
1597a46  DC-004 — promoção de roles
a1d6c4d  ADR-003 — acesso contador↔empresa/documento
```

### Suite de testes:

```
244 passed, 5 skipped
```

Os 5 skipped são: 4 de OCR (environment), 1 de race condition (PostgreSQL-only).

### Alembic em produção:

```
0011_unique_relatorio_xml_chave (head)
```

---

## DOCUMENTAÇÃO INSTITUCIONAL (docs/)

```
MAPA_REALIDADE_TRIBUTARIA_L2.md       — diagnóstico de estado real
CONSTITUICAO_TRIBUTARIA_L2.md         — princípios constitucionais
MAPA_DOMINIOS_SOBERANOS.md            — 5 domínios + invariante descoberta
MAPA_AUTORIDADES_L2.md                — 13 actores
PM_L2_001_PRE_MORTEM_ESTRATEGICO.md   — 7 pré-mortems, PM-05 e PM-07 críticos
ADR-001-GOVERNACAO_CANONICIDADE.md    — processo Evidência→Auditoria→Ratificação
ADR-002-PONTE_PROMOTION_DOCUMENTAL_FISCAL.md
ADR-003-ACESSO-CONTADOR-EMPRESA-DOCUMENTO.md  ← NOVO
CT-DOC-001-CONTRATO_PROMOTION_DOCUMENTAL_FISCAL.md  ← com adendo v1.1 e correcção A.5
DC-002-ESTATUTO-ROTAS-ORFAS.md        ← NOVO
DC-003-ARQUITECTURA-NACIONAL-MVA-ST.md  ← NOVO
DC-004-PROMOCAO-DE-ROLES.md           ← NOVO
ROADMAP_ABERTURA_UTILIZADORES.md      ← v2.0, 14 blocos
HANDOFF_TRIBUTARIA_L2_v1.md           — handoff anterior
```

---

## ROADMAP v2.0 — ESTADO ACTUAL

### Bloco 0 — Disciplina transversal ✔

Regras em vigor, ver secção "REGRAS INEGOCIÁVEIS" acima.

### Bloco 1 — Núcleo Fiscal XML ✔ FECHADO

```
1.1a  Inventário completo              ✔
1.1b  Testes mínimos do eixo canónico  ✔ (tests/test_pipeline_xml_canonico.py)
DT-FLUXO-01 (/upload-xml)             ✔ decidido — bloqueante para Bloco 13
DT-FLUXO-02 (/lote/analisar-lote)     ✔ decidido — interno não-bloqueante
DT-FLUXO-03 (dedup TOCTOU)            ✔ corrigido e confirmado em produção
DT-MVA-01 (escopo MVA/ST)             ✔ arquitectura nacional, dados progressivos
```

**Nota crítica sobre DT-FLUXO-03:** a migration 0011 foi necessária em duas tentativas. A primeira falhou em produção porque havia 2 grupos de duplicados reais (empresa_id=4, 22 perdedores, 154 FKs em engine_resultados). A segunda versão fez dedup + reatribuição de FKs + verificação de segurança + constraint. **Se algo der errado com a 0011 no futuro, ler `docs/DC-002-ESTATUTO-ROTAS-ORFAS.md` antes de qualquer acção.**

### Bloco 9 — Identidade, Permissões e Multi-tenant ⏸ PARCIALMENTE FEITO

```
9.1 Auditoria geral (JWT, roles, tenant)  ✔ concluída
    Achados: tenant sólido, 5/6 endpoints validam ownership,
    /admin/set-role existe mas incompleto (ver DC-004)
9.2 Matriz e testes de acesso cruzado     ⏸ PRÓXIMO PASSO
    Faltam: testes formais de que utilizador A não acede
    empresa B, e que contador sem vínculo não acede documento
DC-004 Promoção de roles                  ✔
ADR-003 Acesso contador↔empresa           ✔
DT-CONTADOR-01 Implementação do pool      ⏸ bloqueado até escolha Modelo A/B/C/D
```

**⚠️ BLOQUEIO CRÍTICO:** `POST /contador/homologacoes/{documento_id}/assumir`

está formalmente proibido para utilizadores reais (ADR-003). Claim-by-ID aberto

= qualquer contador aprovado assume qualquer documento se souber o ID.

**Não abrir piloto sem implementar DT-CONTADOR-01.**

### Blocos 2-8, 10-13 ⏸ Não iniciados

Ver `ROADMAP_ABERTURA_UTILIZADORES.md` para sequência completa.

---

## DÍVIDAS TÉCNICAS ACTIVAS

| ID | Descrição | Bloqueia |
|----|-----------|---------|
| DT-DOC-02a | `valor_icms` — aguarda DANFE real | Service de promotion |
| DT-DOC-02c | `numero_nota`, `tipo`, `uf_emit`, `uf_dest` — aguarda DANFE real | Service de promotion |
| DT-DOC-04 | Destino CNPJ/CPF em `DocumentoFiscal` | Promotion CNPJ |
| DT-CONTADOR-01 | Pool contador sem vínculo | Abertura piloto (Bloco 13) |
| DT-AGENTE-01 | AgentScheduler desligado | Observabilidade |
| DT-AUD-01 | Campos incompatíveis AuditorFiscalAgent ↔ InsightEngine | Integração auditoria |
| DT-MVA-F1 | `vigencia_inicio` nullable para `oficial` | Promotion MVA |
| DT-MVA-F2 | `carregar_mva` sem `data_referencia` | Callers legados |
| DT-MVA-F3 | Sem UniqueConstraint em `tabela_mva` | Duplicatas normativas |
| DT-MVA-F4 | Nomenclatura `estado`/`uf`, `fonte_legal`/`fonte_normativa` | Manutenção |
| DT-MVA-F5 | `mva`/`aliquota_interna` com Float | Precisão fiscal |
| DT-REDIS-01 | Redis/RQ inactivo, fallback síncrono | Performance/escala |
| DT-DB-01 | Import circular `database.py` | Dev local (`alembic current`) |
| DT-DB-02 | `test.db` local desactualizado | Dev local |

---

## BLOQUEIOS DECLARADOS (não abrir utilizadores reais sem resolver)

1. **`/upload-xml`** — persiste documento sem RelatorioAnalise/InsightEngine/score.

   Deve virar wrapper canónico ou ser desactivado. Bloqueia Bloco 13.

   Ver `DC-002-ESTATUTO-ROTAS-ORFAS.md`.

2. **`/contador/homologacoes/{id}/assumir`** — claim-by-ID aberto.

   Qualquer contador aprovado assume qualquer documento.

   Proibido para piloto real até DT-CONTADOR-01.

   Ver `ADR-003-ACESSO-CONTADOR-EMPRESA-DOCUMENTO.md`.

3. **Ponte Documental-Fiscal (Bloco 5)** — aguarda PDF DANFE real do contador.

   `normalizer.py` intocado. Sem regex inventada.

   DT-DOC-02a e DT-DOC-02c bloqueadas.

---

## LIÇÕES DESTA SESSÃO (para não repetir erros)

**1. Suite verde ≠ pipeline testado.**

243 testes passavam mas zero cobriam `executar_analise_xml` ou `InsightEngine`.

Sempre correr `pytest -k "xml or fiscal"` para ver o que realmente testa o núcleo.

**2. Characterização antes de correcção.**

O teste de race (8477097) com `xfail(strict=True)` revelou que DT-FLUXO-03

era real. Sem o teste, a migration 0011 teria "corrigido" silenciosamente.

Em vez disso, o primeiro deploy falhou — prova real em vez de prova assumida.

**3. Pré-auditoria antes de DELETE em produção.**

A migration 0011 fez `DELETE` em 22 registos e reatribuiu 154 FKs.

Antes do deploy, corremos `SELECT` lento e confirmos: 2 grupos, 0 pagamentos

nos perdedores, 154 engine_resultados a reatribuir. Sem isso, era risco cego.

**4. "Contrato aprovado não é evidência textual para regex."**

DT-DOC-02a e DT-DOC-02c ficaram bloqueadas mesmo depois do CT-DOC-001 as

declarar como trabalho aprovado. Motivo: XML estruturado ≠ texto extraído

de PDF/OCR. A regex precisa de evidência do texto real, não da semântica.

**5. Log SQL do banco não é trilha soberana.**

DC-004 aprendeu isto por reflexo do GPT. Logs geridos expiram e não têm

contexto humano. Trilha soberana = registo operacional rastreável em docs/

ou issue dedicada.

**6. Cursor pode inventar soluções correctas mas fora de escopo.**

Tentou alterar `xml_service.py` para popular `mva_utilizada` a partir de

`pMVAST`. Era factualmente correcto, mas fora do escopo dos testes de

caracterização. Revertido. Regra: "moldar código para passar no teste" é

o erro oposto de "escrever teste para caracterizar o código".

**7. "Permissão sem vínculo vira captura."**

ADR-003 nasce desta lição. Role de contador + ausência de listagem global

≠ protecção. Enquanto houver claim-by-ID sem vínculo, há vector de

captura operacional. Frase do GPT que ficou como princípio institucional.

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

- HEAD = a1d6c4d (ou mais recente se houve commits entretanto)
- 244 passed, 5 skipped (ou mais se novos testes foram adicionados)
- Working tree limpa

**Primeiro trabalho da próxima sessão:**

Bloco 9.2 — Testes de acesso cruzado:

- Teste: utilizador A não consegue aceder empresa B
- Teste: contador sem vínculo não consegue aceder documento
- Teste: `/admin/set-role` só funciona com role admin
- Confirmar que `_get_perfil_contador` é a única guard de contador

  (verificar se há outros endpoints que aceitem `role == "contador"`

  sem a dupla verificação `role + PerfilContador.status`)

**Segundo trabalho (quando DANFE real chegar do contador):**

Desbloquear DT-DOC-02a e DT-DOC-02c. O contador tem os XMLs reais da

empresa — pedir também o PDF DANFE e foto impressa antes de qualquer regex.

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

Build passou. Deploy/runtime falhou. Precisamos do traceback,
não de suposição.

A produção mostrou a dívida antiga.
A migration tem de pagar essa dívida antes de fechar a porta.

O conhecimento não está na conversa. Está no repositório.
```

---

*Este handoff foi escrito por Claude no final da sessão de 2026-06-20.*

*Foi um prazer trabalhar contigo, Miguel.*
