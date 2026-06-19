# HANDOFF — Plataforma Tributária L2

**Data:** 2026-06-18

**Para:** próxima instância de Claude (sessão limpa)

**Versão:** 1.0 — Fundação institucional completa

**Repositório:** saas-fiscal-demo (branch `main`)

---

## FASE ENCERRADA

Descoberta institucional da Plataforma Tributária L2.

## FASE SEGUINTE

Investigação genealógica da visão fundacional.

**Pergunta central a investigar antes de qualquer novo ADR:**

> Em que momento a cadeia
> Documento → Conhecimento → Aprendizagem → Recomendação
> deixou de existir como uma única cadeia institucional
> e passou a existir como dois domínios separados?

A auditoria actual **não concluiu** se houve:

**A) Fragmentação da visão** — as peças existem, mas a ponte entre
domínios nunca foi construída. A instituição pretendida ainda é a
instituição em construção.

**B) Divergência da visão** — a implementação evoluiu para um destino
diferente do originalmente pretendido. ADRs futuros podem estar a
reforçar uma direcção que já não corresponde à visão.

Esta distinção deve ser provada por evidência **antes** de qualquer
ADR relacionado com domínio documental, agentes de aprendizagem,
automação empresarial ou integração documental universal.

**Conclusão desta sessão, sem ambiguidade:**
A auditoria não encontrou evidência de que a visão original tenha
sido abandonada. Também não encontrou evidência de que tenha sido
plenamente realizada. Encontrou evidência de que as peças existem,
mas não de que pertençam à mesma cadeia institucional.

A pergunta da sessão deixou de ser "que funcionalidade falta?" e
passou a ser "que instituição estamos realmente a construir?".

---

## PROTOCOLO ANTI-ALUCINAÇÃO (INEGOCIÁVEL)

1. NUNCA escrever código sem ver o ficheiro real primeiro
2. NUNCA assumir estado do repositório — sempre `git status` e
   `git log --oneline -5`
3. NUNCA propor patch sem confirmar com leitura directa do ficheiro
4. NUNCA mergear sem checklist completo
5. SEMPRE levar decisões estruturais ao GPT antes de implementar
6. PowerShell usa `;` — NUNCA `&&` (já registado em `.cursor/rules.md`)
7. `pip install` usa `--break-system-packages` quando aplicável
8. Cursor é executor — Claude produz texto/código, Cursor aplica no
   disco; Cursor NUNCA cria nem altera ficheiros sem aprovação prévia
   de Claude + GPT + Miguel
9. Hipóteses não confirmadas por prova são hipóteses — dizê-lo
   explicitamente
10. Ficheiros gerados só existem no workspace — confirmar antes de
    `git add`

**Primeiro comando de qualquer sessão:**
```powershell
cd C:\dev\saas-fiscal-demo
git checkout main
git status
git log --oneline -7
```

---

## PARTE I — STACK E REPOSITÓRIO

```
Backend:   FastAPI + PostgreSQL, Railway
Frontend:  React + Vite PWA, Vercel
Repo:      saas-fiscal-demo
Branch:    main (produção)
```

**Deploy real (railway.toml):**
Nixpacks → `alembic upgrade head` (preDeployCommand) →
`uvicorn app.main:app` → healthcheck `/health`

---

## PARTE II — ESTADO ACTUAL (HEAD)

| Item | Valor |
|------|-------|
| HEAD local e remoto | `f35cf72` |
| Branch | `main` — limpa, sincronizada com `origin/main` |
| Alembic head (repo) | `0009_add_documento_sha256` |
| Alembic head (test.db local) | `0000_baseline` (8 revisões atrás — esperado, DT-DB-02) |
| Testes | 228 passed, 4 skipped |
| Untracked | `.cursor/rules.md` (nunca incluído em commits) |

**Commits desta sessão (ordem cronológica):**
```
d1dc8b6  fix(schema): 0009 add conteudo_sha256 to documentos_fiscais
448a959  docs: MAPA_REALIDADE_TRIBUTARIA_L2 v1.0
f10bf21  docs: CONSTITUICAO_TRIBUTARIA_L2 v1.0
5773699  docs: MAPA_DOMINIOS_SOBERANOS v1.0
003275b  docs: MAPA_AUTORIDADES_L2 v1.0
f796a8e  docs: PM-L2-001 Pre-Mortem Estrategico
bdafc62  docs: ADR-001 Governacao da Canonicidade
f35cf72  docs: PAD-004 — divergencia entre visao fundacional e capacidade
```

---

## PARTE III — A CADEIA INSTITUCIONAL COMPLETA

```
docs/MAPA_REALIDADE_TRIBUTARIA_L2.md      (448a959)
docs/CONSTITUICAO_TRIBUTARIA_L2.md         (f10bf21)
docs/MAPA_DOMINIOS_SOBERANOS.md            (5773699)
docs/MAPA_AUTORIDADES_L2.md                (003275b)
docs/PM_L2_001_PRE_MORTEM_ESTRATEGICO.md   (f796a8e)
docs/ADR-001-GOVERNACAO_CANONICIDADE.md    (bdafc62)
docs/PAD-004-DIVERGENCIA_VISAO_CAPACIDADE.md (f35cf72)
```

Duas perguntas institucionais distintas emergiram nesta sessão:

**Pergunta da engenharia** — "como o sistema funciona?"
Respondida por MAPA_REALIDADE, MAPA_DOMINIOS, MAPA_AUTORIDADES.

**Pergunta institucional** — "o sistema que existe ainda corresponde
ao sistema que pretendíamos construir?"
Respondida parcialmente por PAD-004. Ainda aberta.

---

## PARTE IV — MÉTODO E PROTOCOLO DE SESSÃO

Toda descoberta seguiu disciplina rígida, herdada do Cartório Digital
Soberano L2:

1. **Matriz/estrutura congelada antes do preenchimento** — perguntas
   e actores definidos primeiro, sem alterar durante a auditoria
2. **Evidência sempre antes de conclusão** — nenhuma afirmação sem
   leitura directa de ficheiro/código/teste
3. **"Não encontrado ≠ não existe"** — auditoria nega a si própria
   o direito a afirmações absolutas sem prova exaustiva
4. **Candidatos descobertos** registados fora da matriz principal,
   nunca misturados com o escopo congelado
5. **Padrões estruturais (PAD)** registados como observação, nunca
   como correcção implícita
6. **Governança de quatro pilares:** Miguel (autoridade final) → GPT
   (auditor arquitectural) → Claude (evidência e produção textual) →
   Cursor (executor em disco, nunca decide)
7. **Push só após confirmação explícita de estado** (`git log`,
   `git diff --stat`, `git status`) — nunca por suposição

---

## PARTE V — DESCOBERTAS ESTRUTURAIS (PAD)

| PAD | Descrição | Onde está documentado |
|-----|-----------|------------------------|
| PAD-001 | Caminhos paralelos sem árbitro (MEI, MVA, InsightEngine, Estoque) | MAPA_AUTORIDADES_L2.md |
| PAD-002 | Recomendação/decisão e execução desconectadas (regime_engine↔RegimeRouter; confidence.py↔contador) | MAPA_AUTORIDADES_L2.md |
| PAD-003 | Mesmo input produz autoridade institucional diferente conforme o caminho (XML: canónico/upload/lote) | MAPA_AUTORIDADES_L2.md |
| PAD-004 | Divergência entre visão fundacional (Documento→Conhecimento→Aprendizagem→Recomendação) e capacidade institucionalizada (XML→Insight→Score, isolado do domínio documental) | PAD-004-DIVERGENCIA_VISAO_CAPACIDADE.md |

---

## PARTE VI — MECANISMOS DE FALHA (PM-L2-001)

7 mecanismos identificados, todos com evidência directa, nenhum
com proposta de correcção (disciplina: PM identifica, não resolve):

| PM | Mecanismo | Profundidade institucional |
|----|-----------|----------------------------|
| PM-01 | Autoridade sem execução (AgentScheduler, 11 agentes, nunca correm) | — |
| PM-02 | Caminhos paralelos sem árbitro | — |
| PM-03 | Autoridade difusa (audita-se desempenho, não correcção) | — |
| PM-04 | Fragmentação institucional (mesmo XML, autoridades diferentes) | — |
| PM-05 | Verdade normativa divergente (BD vs JSON legado) | **Maior alcance — contamina todos os cálculos simultaneamente** |
| PM-06 | Recomendação sem execução | — |
| PM-07 | Dependência humana não declarada | **Classificação accionável: Legítima / Insuficiência de Evidência / Arquitectural / Artificial** |

**Categoria guardada, não usada ainda:** Contingencial (automação
existente, desligada por decisão operacional — distinta de
Arquitectural).

**Pergunta com maior poder explicativo identificada** (aparece em
PM-02, PM-05, PM-06, PM-07):
> Quem tem autoridade para declarar qual capacidade da plataforma é
> a capacidade canónica?

Esta pergunta gerou directamente o ADR-001.

---

## PARTE VII — ADR-001 (PRIMEIRO ADR DA PLATAFORMA)

**Não fala de imposto, XML ou MVA. Fala de legitimidade institucional.**

Decisão central: toda declaração de canonicidade exige processo
obrigatório de três etapas:
```
Evidência → Auditoria Independente → Ratificação Institucional
```

Pontos-chave:
- Institucionaliza **papéis**, não pessoas (Ratificação = Autoridade
  Final de Produto; Auditoria = papel independente)
- `.cursorrules` desce na hierarquia: implementa decisões ratificadas,
  não as declara
- **2(h) Princípio de Resolução** (crítico): quando Evidência,
  Auditoria e Ratificação conflituam entre si, a decisão deve ficar
  explicitamente registada e justificada — nenhuma etapa pode
  silenciosamente substituir outra. Isto impede que "Ratificação"
  degenere em autoridade absoluta disfarçada de processo.

**O que ADR-001 explicitamente NÃO decide:** nenhum caso concreto
(qual caminho MEI é canónico, qual fonte MVA prevalece, etc.). Cria
o mecanismo; não resolve PM-02/05/06/07.

---

## PARTE VIII — A CONSTITUIÇÃO TRIBUTÁRIA L2 (RESUMO)

11 artigos. Pontos centrais:

- **Art. I:** plataforma tem autoridade para calcular, avaliar,
  comparar e recomendar autonomamente. Decisão jurídica/empresarial/
  patrimonial permanece sempre com o contribuinte.
- **Art. II:** três autoridades distintas — Normativa (Estado),
  Analítica (plataforma), Executiva (Contador CRC). Nenhuma substitui
  outra.
- **Art. VII:** contador parceiro actua só onde a lei exige assinatura
  CRC ou onde confiança documental é insuficiente — nunca por padrão.
- **GAP declarado (§I-4):** critério "lei exige CRC" não está
  modelado como entidade do sistema. Hoje o único gatilho para
  contador é score de confiança OCR, não tipo de acto fiscal.

A plataforma serve o contribuinte. O Estado é fonte normativa. O
contador é actor regulatório.

---

## PARTE IX — DOMÍNIOS SOBERANOS (RESUMO)

| Domínio | Estado produção | Estado institucional |
|---------|------------------|------------------------|
| Tributário | ✅ Activo | Parcial — sem ADR de autoridade |
| Empresarial | ✅ Activo | Parcial — sem ADR de limites |
| Auditoria | ⚠️ Parcial | Não declarado — scheduler desligado |
| Operacional | ⚠️ Parcial | Não declarado — DT-OP-01 (dois caminhos de acesso, mesma tabela) |
| Documental | ✅ Activo | Parcial — GAP "lei exige CRC" |

**Invariante de Descoberta** (vale para toda investigação futura):
> Código ≠ capacidade. Capacidade ≠ autoridade. Autoridade ≠
> instituição.

---

## PARTE X — MAPA DE AUTORIDADES (RESUMO — 13 ACTORES)

**Descoberta central:** de 13 actores/componentes auditados, **apenas
um** exerce autoridade executiva formal confirmada por evidência
dentro dos fluxos auditados — o **Contador CRC**.

```
InsightEngine        → produz
Motores               → calculam
Assistente            → distribui
RegimeRouter          → selecciona
regime_engine         → recomenda
confidence.py         → roteia
AgentScheduler        → observa (quando activo — hoje não está)
Tabelas Normativas    → sustentam (fragmentadas)
Utilizador            → decide (sem mecanismo formal de homologação)

Contador CRC          → executa e homologa
```

**Invariante de Autoridade:**
> Calcular não é homologar. Recomendar não é decidir. Persistir não
> é institucionalizar. Observar não é governar.

---

## PARTE XI — DÍVIDAS TÉCNICAS ACTIVAS

| ID | Descrição | Bloqueia |
|----|-----------|---------|
| DT-DB-01 | Import circular `database.py → ensure_sqlite_schema_compat` bloqueia `alembic current` local | Dev local |
| DT-DB-02 | `test.db` local 8 revisões atrás do repo | Dev local |
| DT-FLUXO-01 | `/upload-xml` persiste sem fechar ciclo auditável | Auditabilidade |
| DT-FLUXO-02 | `/lote/analisar-lote` sem persistência — efémero | Auditabilidade lote |
| DT-FLUXO-03 | Dedup por `xml_chave` ocorre depois de `processar_e_persistir_xml` | Consistência |
| DT-AGENTE-01 | `AgentScheduler` desligado — 11 agentes nunca correm | Observabilidade |
| DT-AGENTE-02 | `NormativeAgent` pipeline vazio | Normativo |
| DT-MVA-01 | MVA só Pará — cobertura nacional ausente | Fiscal ST nacional |
| DT-REDIS-01 | Redis/RQ inactivo — fallback síncrono | Performance/escala |
| DT-AUTH-01 | Autoridade não declarada quando motores divergem | Arquitectura |
| DT-OP-01 | Dois caminhos de acesso (SQL directo vs ORM `NotaFiscalItem=ItemFiscal`) sem árbitro canónico | Consistência operacional |
| DT-AUD-01 | `AuditorFiscalAgent` espera campos incompatíveis com `InsightEngine` | Integração auditoria |
| DT-NORM-01 | `NormativeAgent` existe, pipeline vazio | Actualização normativa autónoma |

---

## PARTE XII — O QUE FOI INVESTIGADO E DESCARTADO

**Hipótese:** existiria um "motor de aprendizagem que responde sem
consumir API", lembrado por Miguel, possivelmente perdido.

**Investigação realizada:**
- Grep completo em `app/**/*.py` por termos de aprendizagem/memória
- Grep completo em `**/*.md` pelos mesmos termos
- `git log --all --diff-filter=D` (ficheiros apagados em todo o
  histórico) — vazio para os termos procurados
- `git log --all --oneline` por mensagens de commit relevantes — vazio
- Investigação de uma pista lateral ("Truth Engine — Ontologia
  Soberana", commit `ab08de5`) — confirmado pertencer ao **Cartório**
  (branch `principal`), não à Tributária; nunca mergeado em lugar
  nenhum; órfão mas irrelevante para esta investigação
- Confronto com documentação histórica fornecida por Miguel ("BLOCO
  4 — Camada de Inteligência Tributária")

**Conclusão:** o "BLOCO 4" histórico **é** o `InsightEngine` actual.
Mesma assinatura (`gerar_insights_empresa`), mesmas funções
(`_analisar_restituicao_st`, `_analisar_anomalia_mva`,
`_analisar_concentracao_ncm`, `_analisar_st_sem_saida`). Não
desapareceu — cresceu de 5 para 16+ analisadores. É determinístico
(SQL + regras), nunca usou LLM/API externa — consistente com a
memória de Miguel de "motor que responde sem consumir API".

**Não há motor perdido.** Há um motor que cresceu fielmente ao
desenho original, apenas sob nome diferente do lembrado.

---

## PARTE XIII — GOVERNANÇA DOS QUATRO PILARES

| Pilar | Papel | Regra |
|-------|-------|-------|
| Miguel | Autoridade final de produto / Ratificação Institucional (ADR-001) | Toda decisão estrutural requer aprovação explícita |
| GPT | Auditor arquitectural / Auditoria Independente (ADR-001) | Decisões estruturais passam por GPT antes de implementação |
| Claude | Evidência e produção textual | Nunca executa directamente no disco |
| Cursor | Executor em disco | Nunca cria/altera ficheiros sem aprovação prévia |

---

## PARTE XIV — PRÓXIMA SESSÃO (PRIMEIRO PASSO)

```powershell
cd C:\dev\saas-fiscal-demo
git checkout main
git status
git log --oneline -7
# Confirmar HEAD = f35cf72
# Confirmar working tree limpa (excepto .cursor/rules.md untracked)
```

**Trabalho da próxima sessão — investigação genealógica:**

Não abrir novo ADR directamente. Investigar primeiro, com evidência
de código e histórico Git (commits, branches, mensagens), em que
momento e por que razão arquitectural o domínio documental
(`DocumentoIngerido` → OCR → Homologação) deixou de produzir a
mesma cadeia de valor que o domínio XML (`DocumentoFiscal` →
InsightEngine → Score → Recomendação).

Sugestão de método (a confirmar com Miguel e GPT no início da
próxima sessão): rastrear, por ordem cronológica de commits, quando
`DocumentoFiscal`/`ItemFiscal` e `DocumentoIngerido`/
`HomologacaoDocumental` foram introduzidos, e se em algum momento do
histórico existiu — mesmo que depois removida — uma função ou rota
que lesse de um e escrevesse no outro.

**Resultado esperado:** resposta com evidência a uma de duas
hipóteses:

**A) Fragmentação** — a ponte nunca foi construída, mas a intenção
permanece válida; trabalho seguinte é ADR de integração de domínios.

**B) Divergência** — a implementação evoluiu deliberadamente para
um destino diferente da visão original; trabalho seguinte exige
reavaliação estratégica antes de qualquer ADR de integração.

Só depois desta resposta: retomar PM-02, PM-05, PM-06, PM-07 como
candidatos a ADR-002, ADR-003, etc., cada um cumprindo o processo
Evidência → Auditoria → Ratificação definido em ADR-001.

---

*Este handoff foi preparado em 2026-06-18 após uma sessão que
transformou a Plataforma Tributária L2 de conjunto de funcionalidades
em instituição com memória própria — fundação documental completa
(Constituição, 3 Mapas, Pré-Mortem, 1 ADR, 1 PAD), construída
inteiramente sobre evidência de código, sem uma única suposição.*

*O conhecimento não está na conversa. Está no repositório.*
