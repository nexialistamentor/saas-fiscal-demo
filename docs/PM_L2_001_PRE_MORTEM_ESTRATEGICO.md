# PM-L2-001 — PRÉ-MORTEM ESTRATÉGICO DA PLATAFORMA TRIBUTÁRIA L2

**Versão:** 1.0

**Data:** 2026-06-18

**Natureza:** Documento de descoberta estratégica. Não corrige. Não propõe.

  Identifica mecanismos de falha institucional, com base exclusivamente
  em evidência já provada no MAPA_AUTORIDADES_L2.md v1.0.

**Pré-requisito cumprido:** MAPA_AUTORIDADES_L2.md v1.0 concluído.

---

## REGRA FUNDACIONAL DO DOCUMENTO

Um Pré-Mortem não pergunta:

> "Como corrigir?"

Pergunta:

> "Se isto falhar totalmente dentro de 10 anos, qual foi o mecanismo real da falha?"

Cada PM segue a estrutura:

Descrição → Evidência da matriz → Classificação (quando aplicável) → Pergunta que o ADR terá de responder

Sem correcção. Sem refactor. Sem proposta de agente, tabela ou ADR dentro do próprio PM.

Este documento identifica mecanismos de falha — não os resolve.

---

## PM-01 — AUTORIDADE SEM EXECUÇÃO

**Descrição:**

Componentes têm autoridade declarada e codificada, mas nunca a exercem em produção. A instituição existe no código; não existe em runtime.

**Evidência da matriz:**

- `AgentScheduler` — loop comentado em `main.py` (linhas 134-136)
- 11 agentes registados em `AgentRegistry` — nenhum corre autonomamente
- `AuditorFiscalAgent` — classifica severidade, mas nunca executa
- `normative_validation_agent` — corre apenas dentro de um ciclo que está desligado

**Mecanismo de falha a 10 anos:**

A plataforma acumula camadas de "capacidade planeada" sem nunca activar a primeira. Cada nova funcionalidade assume implicitamente que a anterior já funciona — porque o código existe. Ninguém verifica se está a correr. O sistema fica institucionalmente mais complexo sem ficar operacionalmente mais capaz.

**Pergunta que o ADR terá de responder:**

Qual é o critério para considerar um agente "operacional" — existir no registry, ou existir evidência de execução contínua em produção?

---

## PM-02 — CAMINHOS PARALELOS SEM ÁRBITRO

**Descrição:**

Múltiplos caminhos de código resolvem o mesmo facto de forma independente, sem mecanismo que decida qual prevalece quando divergem.

**Evidência da matriz (PAD-001):**

- MEI: motor legado (`mei_engine.py`, DEPRECATED) vs motor oficial (`mei_tax_engine.py`, registado)
- Estoque: `agent_estoque` via SQL directo vs `InsightEngine` via alias ORM `NotaFiscalItem`
- InsightEngine: pipeline canónico vs `analysis_orchestrator._gerar_insights_por_xml()` paralelo
- Normas: `buscar_mva` (BD, sem fallback) vs `carregar_mva` (BD + fallback `mva.json`)

**Mecanismo de falha a 10 anos:**

Cada caminho evolui de forma independente porque ninguém tem mandato de manter os dois sincronizados. Com o tempo, os caminhos divergem silenciosamente — pequenas correcções aplicadas só num dos lados. O sistema não tem um momento de "quebra" visível; tem uma erosão lenta de consistência interna que só se manifesta quando dois utilizadores recebem respostas diferentes para a mesma pergunta.

**Pergunta que o ADR terá de responder:**

Para cada par de caminhos paralelos identificados, qual é canónico e qual é legado — e quem tem autoridade para o declarar?

---

## PM-03 — AUTORIDADE DIFUSA

**Descrição:**

A plataforma audita disponibilidade e desempenho dos seus componentes, mas não audita a correcção do que eles decidem ou calculam.

**Evidência da matriz:**

- InsightEngine: "Nenhum auditor identificado durante a auditoria actual"
- Motores Tributários: "Auditoria de desempenho: sim. Auditoria de correcção fiscal: não identificada"
- Tabelas Normativas: "Não foi identificada verificação normativa activa em produção"
- `metrics_alert_service`/`engine_recovery_service`/`StateRecoveryAgent` monitoram tempo de execução e falhas técnicas — não verificam se o resultado calculado está correcto

**Mecanismo de falha a 10 anos:**

Um motor pode estar rápido, disponível e a correr sem erros técnicos — e ainda assim produzir valores fiscais incorrectos indefinidamente, porque "saudável" e "correcto" são medidos por sistemas diferentes, e só o primeiro está implementado. A confiança institucional na plataforma cresce com o tempo de uptime, não com verificação de exactidão.

**Pergunta que o ADR terá de responder:**

Quem — ou o quê — verifica que um cálculo fiscal está correcto, distintamente de verificar que ele foi executado sem erro técnico?

---

## PM-04 — FRAGMENTAÇÃO INSTITUCIONAL

**Descrição:**

O mesmo input pode atravessar caminhos distintos da plataforma e produzir níveis completamente diferentes de autoridade institucional, sem que o utilizador saiba qual caminho está a usar.

**Evidência da matriz (PAD-003):**

- XML via Pipeline Canónico → análise auditável, com score, insights e registo persistente
- XML via `/upload-xml` → persistido, mas sem InsightEngine, sem score, sem registo auditável
- XML via `/lote` → calculado, mas nunca persistido — desaparece após TTL de 1h

**Mecanismo de falha a 10 anos:**

Um utilizador (ou integração externa) escolhe o endpoint errado por razões triviais — documentação desactualizada, exemplo de código antigo, preferência de UX — e perde silenciosamente auditabilidade. Não há erro, não há aviso. A plataforma declara-se "auditável" na Constituição, mas a auditabilidade depende de qual porta de entrada foi usada.

**Pergunta que o ADR terá de responder:**

A plataforma deve garantir o mesmo nível de autoridade institucional independentemente do caminho de entrada — e se sim, como?

---

## PM-05 — VERDADE NORMATIVA DIVERGENTE

**Descrição:**

A base normativa (MVA, PMPF, alíquotas) que sustenta todos os cálculos fiscais está fragmentada entre base de dados e ficheiro estático legado, sem reconciliação declarada.

**Evidência da matriz:**

- `buscar_mva` consulta `tabela_mva` (BD), sem fallback
- `carregar_mva` consulta a mesma tabela, mas cai silenciosamente para `app/data/mva.json` quando UF está ausente
- `insights_engine` importa **ambas** as funções no mesmo módulo
- Cobertura nacional de MVA ausente — só Pará (DT-MVA-01)

**Mecanismo de falha a 10 anos:**

Se a norma na BD for actualizada (legislação muda) mas o JSON legado não for sincronizado — ou vice-versa — dois cálculos tecnicamente correctos, executados pelo mesmo sistema, produzem resultados fiscais diferentes para o mesmo contribuinte. Isto é o risco mais grave identificado em toda a auditoria: não é um motor com bug, é a **própria definição de verdade fiscal** que se torna ambígua dentro do sistema.

**Pergunta que o ADR terá de responder:**

Existe uma única fonte de verdade normativa na plataforma, ou a coexistência de BD e JSON legado é uma decisão arquitectural deliberada com regras de precedência explícitas?

---

## PM-06 — RECOMENDAÇÃO SEM EXECUÇÃO

**Descrição:**

Componentes que recomendam ou decidem um encaminhamento não têm ponte automática para o componente que executaria essa recomendação. A ponte depende de acção humana posterior, não notificada.

**Evidência da matriz (PAD-002):**

- `regime_engine.comparar_regimes` recomenda regime óptimo — `RegimeRouter` continua a usar `empresa.regime_tributario`, persistido manualmente, sem validação cruzada
- `confidence.py` decide `fila_homologacao` — o contador descobre o documento manualmente via `GET /contador/homologacoes/pendentes`, sem notificação automática

**Mecanismo de falha a 10 anos:**

A plataforma recomenda correctamente, mas a recomendação fica suspensa no ar. Uma empresa pode operar anos sob um regime tributário subóptimo, com a plataforma a "saber" qual seria melhor desde o primeiro dia, sem nunca fechar essa lacuna porque a arquitectura nunca construiu a ponte entre saber e agir.

**Pergunta que o ADR terá de responder:**

Quando a plataforma produz uma recomendação accionável, que mecanismo garante que ela chega a quem pode agir sobre ela — e em que prazo?

---

## PM-07 — DEPENDÊNCIA HUMANA NÃO DECLARADA

**Descrição:**

A plataforma usa intervenção humana em múltiplos pontos, mas não distingue se essa intervenção é exigida por lei, compensa insuficiência de evidência do sistema, ou compensa uma capacidade institucional ainda incompleta.

**Classificação aplicada aos casos já identificados na matriz:**

| Caso | Classificação | Evidência |
|------|---------------|-----------|
| Contador CRC — homologação documental | **Legítima** | Constituição Art. VII — lei exige assinatura habilitada |
| Documento em `fila_homologacao` (score 70-94) | **Por insuficiência de evidência** | confidence.py — score algorítmico insuficiente para decisão autónoma |
| Utilizador — persistir regime tributário manualmente | **Arquitectural** | PAD-002 — falta ponte entre recomendação (regime_engine) e execução (RegimeRouter) |
| Observação de agentes/scheduler (humano tem de monitorar manualmente) | **Artificial** | DT-AGENTE-01 — scheduler desligado; não é exigência regulatória, é lacuna operacional actual |

**Mecanismo de falha a 10 anos:**

Sem esta distinção declarada, a plataforma corre dois riscos opostos e simultâneos: (a) automatizar prematuramente um domínio onde a lei exige assinatura humana, criando exposição jurídica; ou (b) manter dependência humana artificial indefinidamente porque ninguém percebeu que era apenas uma lacuna temporária, normalizando-a como se fosse permanente. Ambos os erros nascem da mesma causa raiz: a plataforma nunca declarou explicitamente por que cada humano está onde está.

**Pergunta que o ADR terá de responder:**

Para cada ponto de intervenção humana na plataforma, qual categoria se aplica — Legítima, por Insuficiência de Evidência, Arquitectural ou Artificial — e quem tem autoridade para reclassificar um caso quando a capacidade institucional evolui?

---

## SÍNTESE — RELAÇÃO ENTRE OS SETE MECANISMOS

Nenhum dos sete PMs é independente dos outros. Formam uma cadeia:

PM-01 (autoridade sem execução)
→ produz PM-03 (autoridade difusa — ninguém audita o que não corre)

PM-02 (caminhos paralelos)
→ produz PM-05 (verdade normativa divergente — caso mais grave de PM-02)

PM-06 (recomendação sem execução)
→ produz PM-07 categoria "Arquitectural"
(dependência humana que só existe porque a ponte não foi construída)

PM-04 (fragmentação institucional)
→ é o sintoma visível de PM-01, PM-02 e PM-06 combinados

A hipótese central, já registada no MAPA_DOMINIOS_SOBERANOS.md, ganha precisão adicional:

> A plataforma não falha por falta de capacidade.
> Falha por falta de uma autoridade institucional que decida,
> entre capacidades já existentes, qual prevalece.

---

## O QUE ESTE DOCUMENTO NÃO FAZ

Não propõe ADRs.

Não propõe correcções.

Não propõe novos agentes, tabelas ou refactors.

Não atribui prioridade de execução.

Não estima probabilidade ou impacto — não há dados de produção suficientes para isso.

Identifica, com evidência, os mecanismos pelos quais a Plataforma Tributária L2
poderia falhar institucionalmente nos próximos 10 anos, caso cresça
sem primeiro resolver as perguntas que cada PM deixa em aberto.

---

## PRÓXIMO PASSO NA SEQUÊNCIA

Constituição          ✔
Mapa de Realidade      ✔
Mapa de Domínios       ✔
Mapa de Autoridades     ✔
Pré-Mortem Estratégico  ✔ (este documento)
ADRs                   ← desbloqueado

Os ADRs futuros nascem das perguntas em aberto deste documento —
não de opinião, não de preferência técnica, mas de mecanismo de falha
já identificado e provado por evidência.

---

## LEITURA ESTRATÉGICA (não altera os PMs — orienta os ADRs futuros)

PM-05 (verdade normativa divergente) tem alcance distinto dos restantes seis.
Um motor errado afecta um cálculo. Uma norma errada afecta todos os cálculos
que dependem dela — motores, insights, auditoria, previsões e recomendações
simultaneamente. Esta nota não atribui prioridade de execução; regista
profundidade institucional para informar a ordem em que os ADRs serão abertos.

PM-07 evoluiu durante a auditoria de "onde existem humanos?" para
"porque existem humanos?". A classificação Legítima / Insuficiência de
Evidência / Arquitectural / Artificial é o primeiro critério accionável
produzido por toda a auditoria. Uma quinta categoria — Contingencial
(automação existente, desligada por decisão operacional, não por lacuna
estrutural) — foi identificada mas fica guardada, não usada nesta versão.

**Pergunta com maior poder explicativo identificada:**

> Quem tem autoridade para declarar qual capacidade da plataforma
> é a capacidade canónica?

Esta pergunta aparece, directa ou indirectamente, em PM-02, PM-05, PM-06
e PM-07. É candidata a pergunta fundacional dos primeiros ADRs — não
porque resolva os quatro PMs, mas porque uma resposta institucional a
ela reduz a superfície de cada um.

---

*Documento produzido sobre evidência exclusiva do MAPA_AUTORIDADES_L2.md v1.0.*

*Zero correcções propostas. Zero ADRs criados. Apenas mecanismos de falha identificados.*

*O conhecimento não está na conversa. Está no repositório.*
