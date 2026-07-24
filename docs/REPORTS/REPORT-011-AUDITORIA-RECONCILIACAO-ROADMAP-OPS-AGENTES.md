# REPORT-011 — Auditoria e Reconciliação do ROADMAP_OPS_AGENTES

**Estado:** RATIFICADO — FECHO DOCUMENTAL AUTORIZADO POR MIGUEL
**Classificação técnica:** AUDITORIA CONCLUÍDA — PRONTO PARA DECISÃO SOBRE REDACÇÃO CONTROLADA DO ROADMAP
**Parecer GPT:** APROVADO APÓS AUDITORIA INTEGRAL.
**Ratificação de Miguel:** RATIFICO O REPORT-011 E AUTORIZO O SEU FECHO DOCUMENTAL, SEM AUTORIZAR AINDA A REDACÇÃO OU ALTERAÇÃO DO ROADMAP_OPS_AGENTES.
**Data:** 2026-07-23
**Branch:** `main
**Baseline:** `HEAD = origin/main = 31c0f3a01fcef5e1d78a93e02aa19b5ca97f7b3f
**Natureza:** auditoria documental read-only; este relatório não altera nem substitui o roadmap.

## 1. Conclusão executiva

O `docs/ROADMAP_OPS_AGENTES.md`, versão 1.1 de 2026-06-28, deixou de
representar o estado operacional e institucional verificável do repositório.
Preserva princípios ainda válidos — decisão fiscal não delegada a LLM,
aprovação humana, ausência de auto-commit/auto-deploy e proibição de envio de
dados fiscais brutos —, mas mantém B13 como fase corrente, projecta como
futuras entregas já existentes, usa um inventário incompleto, descreve uma
sanitização insuficiente face ao contrato canónico L3 e contém afirmações
normativas e externas não provadas ou incorrectas.

A base documental e operacional é suficiente para uma missão posterior de
redacção controlada. Essa conclusão não autoriza activar agentes, escolher
prioridades de produto, implementar projector/reader/scheduler, integrar LLM
real, escrever no banco ou reabrir ADR ratificado.

## 2. Preflight e integridade inicial

Comandos read-only usados no preflight: `git branch --show-current`,
`git rev-parse HEAD`, `git rev-parse origin/main`, `git diff --cached
--name-only`, `git status --short`, `Get-FileHash` e testes de existência.

Estado Git inicial literal:

```tex
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py


Stage inicial: vazio. `REPORT-011` não existia. Nenhum ficheiro com
`MISSION-011` estava gravado no repositório.

| Ficheiro protegido | SHA-256 inicial |
|---|---|
| `app/agents/adapters/ag_encerramento.py` | `FDEAF1214EAEE4C3F92C08D6989581BF64A31A4BB2C2815F7027CBC57998527A` |
| `app/agents/engines/ag_encerramento.py` | `640F39160A545E3B1EE9135089D9113FCFA3293DFF9E423E5C96DA78A3A9ECA7` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `683A263E3FFB07ED88A5E72501705FAC9A54299D141BDE5024A78515D731E969` |
| `tests/test_ag_encerramento_mission_adapter.py` | `04FA3310D73CE86554380F378511A5E3589B398EB2B824694C173FA53D349CAF` |

SHA-256 do roadmap auditado:
`16B24C2CDD718AEB6E4AF1A59B74689E0EEB036FFFDEFFDA5C939EAC6FB8CE70`.

## 3. Fontes consultadas e método

Foram lidos os documentos autorizados: `AGENTS.md`;
`docs/CCS/CCS-001-CONSTITUICAO-DE-EXECUCAO.md`;
`docs/ROADMAP_OPS_AGENTES.md`;
`docs/B13_OPS_12_DEPENDENCIAS_NORMATIVAS.md`; ADR-008 a ADR-018;
MISSION-001 e MISSION-003 a MISSION-007; REPORT-001 a REPORT-010.
Foram ainda examinados o inventário integral de `app/agents`, as referências
a agentes fora dessa árvore, `app/main.py`, o LLMRouter e provider já
existentes, os quinze ficheiros de testes arquitecturais/contratuais
directamente ligados a B14 e o histórico Git de `30cbb0f` a `31c0f3a
(incluindo o próprio limite inferior para a cronologia).

Não houve internet, teste global, alteração de código, inferência de activação
por mera existência nem elevação de mensagem de commit acima da qualificação
do documento institucional. O método foi: (1) segmentação do roadmap por
linhas e afirmações materiais; (2) confronto documental; (3) confronto com
ficheiros e referências; (4) confirmação cronológica por Git; (5)
classificação pela taxonomia da missão; (6) recomendação de destino sem
reescrita.

## 4. Matriz de auditoria do roadmap

Foram auditados 28 segmentos materiais, cobrindo todas as secções e
afirmações materiais do documento.

| # | Linha/secção original | Classificação | Evidência documental | Evidência Git/código | Impacto de manter | Destino futuro recomendado |
|---:|---|---|---|---|---|---|
| 1 | 1–6, identidade v1.1/B13 em estabilização | **SUPERADA** | ADR-008 fecha B14.0+B14.1; ADR-009–015 tratam B14.3A–G | sequência `e20f55c`–`bb89516` | apresenta fase histórica como actual | mover identidade antiga para histórico; publicar identidade/versionamento novos |
| 2 | 6, princípio “aprende, classifica e sugere; humano aprova” | **VIGENTE** | ADR-008, secções 3 e 18, limita autoridade | adapters produzem resultados e `actions_executed=[]` nos caminhos L3 examinados | baixo; formulação é genérica | manter como princípio, subordinado a contratos/ADR |
| 3 | 8–9, proibições de commit/deploy/BD/decisão fiscal | **VIGENTE** | ADR-008 e ADR-009–015 negam essas autorizações | adapters L3 declaram ausência de persistência/BD/scheduler | baixo; “directamente” é menos rigoroso que escritor único | manter e referenciar escritor único/AuthorityGuard |
| 4 | 13–25, kill switches genéricos e semântica global | **CONFLITANTE** | ADR-008 exige missão explícita; ADR-015 congela `PERMITE_CHAMADA_REAL_V1=false` | adapters não são activados por `AGENTS_ENABLED`; teste arquitectural prova scheduler fora do lifespan | sugere que uma flag global basta para activar toda a brigada | substituir por fronteiras por missão, versão, modo, autoridade e orçamento |
| 5 | 21, `DEEPSEEK_DRY_RUN=true` como kill switch soberano | **SUPERADA** | ADR-015 define canário sem chamada real e sem router/provider | adapter B14.3G tem `llm_used=False` e nenhum caminho real | confunde configuração de provider com autoridade | isolar em manifesto/provider não canónico |
| 6 | 29–43, inventário de oito agentes | **INCORRECTA** | REPORT-002/003 distinguem registry legado de adapters L3 | `app/agents` contém agentes adicionais, contratos, adapters, engines, reader e suporte | omite a arquitectura B14 e pode induzir activação indevida | substituir pelo inventário verificado da secção 7 |
| 7 | 35–42, “existe, desligado” | **NÃO PROVADA** | documentos não ratificam individualmente esse estado para todos | existência/registry não prova execução; scheduler não inicia no lifespan | converte ausência de prova em estado afirmativo | usar `inactivo` só com prova; caso contrário `não provado` |
| 8 | 38, scheduler “não verificado” | **SUPERADA** | REPORT-002 audita scheduler/registry | código mostra `AgentScheduler`, sessões e persistência; `app/main.py` instancia, mas teste arquitectural impede startup automático | oculta risco e distinção legado/L3 | manter como suporte legado inactivo no lifespan; não autorizado para adapters L3 |
| 9 | 44–52, serviços “não provados” | **MANTER COMO HISTÓRICO** | escopo B13 histórico; não há decisão B14 que os torne fronteira L3 | ficheiros podem existir, mas não foram re-auditados integralmente nesta missão | lista deslocada do foco de agentes | mover para dívida histórica, sem afirmar activação |
| 10 | 54–62, tabela normativa, salário 2026 = 1518 e Decreto 12.302/2026 | **INCORRECTA** | B13-OPS-12 regista 1621.00, Decreto 12.797/2025, fonte em revisão e não apta a decisão | evolução B13 anterior a `30cbb0f`; motor possui controlo temporal | risco fiscal directo e referência falsa/desactualizada | retirar valores; remeter a fonte institucional vigente com estado e vigência |
| 11 | 58–62, demais fontes/diplomas como oficiais | **NÃO PROVADA** | B13-OPS-12 deixa vigências e várias dependências pendentes; `pode_fundamentar_decisao=false` | não houve validação externa autorizada | falsa aparência de prova normativa | isolar em dependências normativas, com fonte_id, vigência e autoridade |
| 12 | 66–85, evento manual Pilot 0/race condition | **MANTER COMO HISTÓRICO** | narrativa B13 consistente com o documento da época | `d9f31b4` é evidência histórica anterior ao intervalo | útil, mas não é estado actual | cronologia histórica, claramente datada |
| 13 | 89–109, FASE 0 “Fechar B13”, P0-07/T1–T8/feedback pendentes | **SUPERADA** | transição institucional posterior para B14; REPORT-001 valida o piloto SCS, não o Pilot 0 de produto | schema drift/sentinelas fecham até `30cbb0f`; B14 começa em `e20f55c` | mantém B13 como bloqueante sem reconciliar gates antigos | dívida histórica: indicar o que é provado e o que não tem fecho documental |
| 14 | 112–180, FASE 1/prova de fontes a criar | **SUPERADA** | `FONTES_TRIBUTARIAS.md` e B13-OPS-12 já existem; B13-OPS-12C continua pendente | entregas B13 ocorreram antes do baseline inicial B14 | manda recriar artefactos e mascara pendências reais | separar concluído de gate normativo ainda aberto |
| 15 | 151–158, manifesto marca salário como “verificado” | **CONFLITANTE** | B13-OPS-12 marca `SALARIO-MINIMO-001` “em_revisao”, `pode_fundamentar_decisao=false` | estado canónico posterior contradiz o exemplo | pode fundamentar decisão fiscal indevida | remover exemplo factual; referenciar manifesto versionado |
| 16 | 163–180, teste manifest e sentinela S3 “a criar” | **SUPERADA** | B13-OPS-12 formaliza INVARIANTE-NR-02/03 e progresso posterior | história B13 contém testes e commits de sentinelas | critério de fase obsoleto | histórico + gate normativo corrente comprovado |
| 17 | 184–197, LLMRouter como futuro e ficheiros “a criar” | **CONCLUÍDA** | ADR-015, 2.1, audita stack LLM existente | `app/services/llm_router.py`, providers, schema e teste existem | duplica trabalho e falseia sequência | marco concluído; activação real permanece não autorizada |
| 18 | 199–212, nomes/modelos/endpoints/depreciação DeepSeek | **NÃO PROVADA** | nenhum documento institucional separado os ratifica | internet proibida; nomes temporais não são prova pelo código | dependência temporal falsa e lock-in | retirar; capacidades abstractas e provider substituível em manifesto próprio |
| 19 | 214–244, schemas/testes LLM propostos | **SUPERADA** | ADR-008 define contratos soberanos; ADR-015 reserva output futuro | schemas/router/testes existem, enquanto B14.3G usa contratos próprios | mistura contrato histórico com contrato L3 | manter apenas como dívida/histórico; contratos vigentes por referência |
| 20 | 246–253, invariantes do LLMRouter | **VIGENTE** | compatíveis com ADR-008/015 | provider possui guardas; B14.3G não chama LLM | baixo, mas cobertura não equivale a activação | manter como princípios; apontar para contratos ratificados |
| 21 | 257–280, `EventoOperacional` como contrato futuro | **CONCLUÍDA** | ADR-014 usa e restringe a superfície do evento | `app/schemas/evento_operacional.py` e testes B13/B14 existem | representa contrato existente como proposta | marco histórico; não o elevar a único contrato L3 |
| 22 | 282–293, sanitização por compreensão rasa | **INCORRECTA** | ADR-008, secção 6, ratifica `ContextSanitizationGuard` canónico | `contracts/sanitization.py` faz varrimento profundo, CPF/CNPJ, IP e guardas de contexto/resultado | regressão de segurança e falsa simplificação | retirar exemplo; referenciar guarda canónica e testes |
| 23 | 295–305, seis “agentes prioritários” | **A DECIDIR** | executor não decide prioridade; ADRs só ratificam migrações específicas | vários nomes nem correspondem a componentes L3 actuais | invade autoridade estratégica de Miguel | mover para “futuro não autorizado”; exigir decisão de produto |
| 24 | 306–331, prompt base universal | **SUPERADA** | ADR-008: motor-first, LLM-last; ADR-014: determinístico; ADR-015: sem chamada real | adapters L3 não dependem de prompt universal | sugere LLM-first e contrato informal | retirar do roadmap; prompts pertencem a artefacto versionado futuro |
| 25 | 335–355, circuito fechado até commit/deploy/memória | **CONFLITANTE** | Constituição/CCS e ADR-008 exigem escopo, escritor único e autoridade; ADR-015 não activa LLM | scheduler/executor legados podem persistir, mas adapters L3 estão isolados | normaliza automação e escrita sem missão/autoridade explícitas | substituir por gates humanos e fronteiras, sem cadeia automática |
| 26 | 357, meta `<30 min` | **NÃO PROVADA** | nenhum ADR/relatório ratifica SLA | nenhum teste/telemetria consultada prova a meta | cria compromisso operacional inventado | retirar ou tratar como hipótese futura mensurável |
| 27 | 361–369, critérios por fases 0–4 | **SUPERADA** | cronologia B14 e SCS substituiu a sequência; vários gates têm estados específicos | commits `e20f55c`–`31c0f3a` | impede leitura do estado actual | substituir por concluído/em auditoria/aberto/bloqueado/futuro |
| 28 | 373–383, lista “não fazer” | **VIGENTE**, com item final **NÃO PROVADA** | proibições centrais compatíveis com ADR-008; nomes/depreciação não ratificados | adapters confirmam isolamento; nenhuma prova externa do modelo | mistura invariantes sólidos com facto temporal não provado | manter invariantes; retirar a linha de modelo específico |

## 5. Cronologia reconciliada B13/B14

### 5.1 Pilot 0 e transição

1. O roadmap documenta a correcção de race condition do Pilot 0 em
   `d9f31b4`, anterior ao intervalo obrigatório.
2. `8283fe1` (2026-07-11) adicionou a sentinela `upload_xml_500`.
3. `528d7aa` (2026-07-12) adicionou a sentinela
   `schema_drift_undefined_column`; `162832b` refinou a extracção dinâmica de
   tabela/coluna.
4. `50497c1`, `e21be12`, `ecf8a6b` e `30cbb0f` repararam, respectivamente, o
   drift de `relatorios_analise.fingerprint`, `insights.superseded` e campos de
   resolução de `alertas_fiscais`. Até `30cbb0f` há fecho operacional dessa
   sequência de P0 do Pilot 0.
5. Isto não prova, por si, cada checkbox T1–T8 nem a existência de
   `PILOTO_0_FEEDBACK.md`. Esses itens ficam como dívida histórica não
   reconciliada, não como fase actual.
6. A passagem operacional a B14 inicia-se documentalmente em `e20f55c`.

### 5.2 Fundação L3

1. `e20f55c` ratifica ADR-008.
2. `f77684f` entrega serialização canónica e `ContextSanitizationGuard`.
3. `eed4bdf` entrega contratos partilhados (`SourceRef`, `BudgetPolicy`,
   `AgentEvidence`, `AgentAlert`, `AgentAction`).
4. `e71047c` entrega `AgentMission` e `MissionFactory`.
5. `2641729` entrega `AgentExecutionResult` e validação cruzada.
6. `7e7d764` adiciona invariantes arquitecturais.
7. `668da07` fecha documentalmente B14.0+B14.1 no ADR-008.

### 5.3 Migrações em sombra e canário

| Bloco | Documento | Implementação Git | Estado provado |
|---|---|---|---|
| B14.3A AgAberturaAgent | ADR-009 | `206c2ca` | adapter L3 em sombra; status do ADR ainda diz aguardar ratificação final de Miguel |
| B14.3B AgEncerramentoAgent | ADR-010 | `e753584` | adapter L3 MEI em sombra |
| B14.3C DataSanitizationAgent | ADR-011 | `0da6f7f` | adapter/engine L3 em sombra; status textual ainda diz aguardar Miguel |
| B14.3D ConsistencyAuditAgent | ADR-012 | `d4c506c` | adapter/engine L3 em sombra |
| B14.3E MemorialValidatorAgent | ADR-013 | `2042d52` | adapter/engine L3 em sombra |
| B14.3F AgentErroOperacional | ADR-014 | `7029835` | adapter/engine determinístico em sombra |
| B14.3G fallback LLM operacional | ADR-015 | `31d9681`, `49f2862`, `8f9806f`, `bb89516` | canário de pré-execução; `llm_used=false`; chamada real permanentemente não autorizada em v1 |

### 5.4 Sistema de Construção Soberana

1. `e7f0a73` adiciona a Constituição Operacional L3 (`AGENTS.md`).
2. `7cdacac` institucionaliza o sistema de construção e valida o ciclo
   MISSION-001/REPORT-001.
3. `2ac68bb` ratifica a auditoria das fronteiras da brigada
   (REPORT-002, depois rectificado por REPORT-003).
4. `b177521` ratifica a auditoria de proveniência (REPORT-004/005).
5. `e5cfd5e`, `c0b6337` e `7f09135` ratificam ADR-016, ADR-017 e ADR-018.
6. `b6450f5` ratifica REPORT-009, auditoria pré-implementação da fronteira do
   memorial.
7. `31c0f3a` implementa B14-SVC-06, a fronteira HTTP read-only do memorial,
   documentada no REPORT-010.

Mensagens de commit que dizem “ratificar” não substituem a qualificação
interna de cada documento. Por isso os estados textuais divergentes foram
preservados e registados como conflito institucional.

## 6. Decisões vigentes e estado reconciliado

- B14.0+B14.1: fundação contratual concluída segundo ADR-008.
- Uma missão, um agente; sem chamadas directas entre agentes; escritor único;
  motor-first/LLM-last; sem `run_all()` produtivo.
- `AgentMission`, `MissionFactory`, `AgentExecutionResult`, serialização
  canónica, sanitização profunda e validação cruzada são contratos actuais.
- B14.3A–F possuem adapters L3 por missão, qualificados como sombra nos seus
  documentos/implementações; existência não os activa.
- B14.3G é somente canário de pré-execução, sem LLM real.
- A brigada não possui prontidão produtiva geral provada: REPORT-002/003
  identificam ausência de integração L3, executor, persistência e scheduler
  soberanos.
- ADR-016/017/018 definem fronteiras futuras/específicas; não autorizam
  activação genérica.
- B14-SVC-06 implementa fronteira HTTP read-only do memorial. Não converte a
  brigada inteira em activa.

## 7. Inventário exacto de `app/agents

Legenda de autoridade: `nenhuma` significa que o componente L3 examinado não
tem autoridade de escrita/fiscal; `legado potencial` significa que o código
contém acesso/persistência mas não há autorização L3 para o activar.
Entradas/saídas são resumidas pelo contrato observável. Todos os estados
evitam inferir activação pela mera existência.

### 7.1 Agentes legados e suporte operacional

| Caminho | Natureza | Contrato; entrada → saída | Estado | Escrita / fiscal / LLM | Testes e ADR |
|---|---|---|---|---|---|
| `__init__.py` | suporte | pacote → pacote | inactivo | nenhuma / nenhuma / não | arquitectura; ADR-008 |
| `ag_abertura_agent.py` | agente legado | `dict` → `dict` | legado, usado só pelo adapter sombra | nenhuma provada / orientação não canónica / não | adapter abertura; ADR-009 |
| `ag_encerramento_agent.py` | agente legado | `dict` → `dict` | legado, protegido | nenhuma provada / orientação MEI não canónica / não | adapter encerramento; ADR-010 |
| `agent_erro_operacional.py` | agente legado | `EventoOperacional`/dict → diagnóstico | legado; sentinelas B13 testadas | nenhuma / nenhuma / fallback LLM legado possível | testes B13 e adapter; ADR-014 |
| `data_sanitization_agent.py` | agente legado | dict → relatório legado | legado, não chamado pelo adapter L3 | nenhuma provada / nenhuma / não | adapter sanitização; ADR-011/016 |
| `consistency_audit_agent.py` | agente legado | dict → consistência | legado, não chamado pelo adapter L3 | nenhuma provada / não decide verdade fiscal / não | adapter consistência; ADR-012/017 |
| `memorial_validator_agent.py` | agente legado | dict → validação | legado, não chamado pelo adapter L3 | nenhuma provada / nenhuma / não | adapter memorial; ADR-013/018 |
| `agent_estoque.py` | agente | dict → dict | não provado | não provada / não provada / não provado | não directamente B14; sem ADR específico |
| `auditor_fiscal_agent.py` | agente | dict → auditoria | legado/não provado | não provada / não autorizado a decidir / não provado | registry legado; ADR-008 |
| `normative_validation_agent.py` | agente | contexto/BD → alertas | legado/não provado | legado potencial / valida regras, sem autoridade canónica provada / não | testes próprios; ADR-008 |
| `normative_watchdog_agent.py` | agente | contexto → alertas | legado/não provado | legado potencial / nenhuma decisão provada / não provado | registry legado; ADR-008 |
| `performance_agent.py` | agente | contexto → métricas | legado/não provado | não provada / nenhuma / não | registry legado; ADR-008 |
| `repair_agent.py` | agente | contexto → reparação proposta | legado/não provado | não provada / nenhuma / não provado | registry legado; ADR-008 |
| `security_audit_agent.py` | agente | logs/BD → alertas | legado/não provado | leitura BD; escrita não provada / nenhuma / não | registry legado; ADR-008 |
| `state_recovery_agent.py` | agente | contexto → recuperação | legado/não provado | efeitos em serviços não autorizados para L3 / nenhuma / não | registry legado; ADR-008 |
| `agent_registry.py` | registry | nomes → instâncias legadas | legado, não integra adapters L3 | nenhuma directa / nenhuma / não | testes arquitecturais; ADR-008, REPORT-002/003 |
| `agent_scheduler.py` | scheduler | jobs/BD → chamadas/métricas | inactivo no lifespan; legado | legado potencial, abre sessões/persistência / nenhuma / não provado | teste arquitectural; ADR-008, REPORT-002 |
| `agent_executor.py` | suporte/executor legado | agente+contexto → resultado/alerta | legado, não é executor L3 provado | grava `AlertaFiscal` e commit / nenhuma / indirecto | auditoria arquitectural; ADR-008, REPORT-002 |
| `mission_factory.py` | suporte/factory L3 | parâmetros autorizados → `AgentMission` | disponível, não activa agente | nenhuma / nenhuma / não | 43 testes; ADR-008 |

### 7.2 Adapters, engines e reader L3

| Caminho | Natureza | Contrato; entrada → saída | Estado | Escrita / fiscal / LLM | Testes e ADR |
|---|---|---|---|---|---|
| `adapters/__init__.py` | suporte | pacote → pacote | inactivo | nenhuma / nenhuma / não | arquitectura; ADR-008 |
| `adapters/ag_abertura.py` | adapter | `AgentMission` → `AgentExecutionResult` | sombra | nenhuma / orientação, não decisão / não | 90 testes; ADR-009 |
| `adapters/ag_encerramento.py` | adapter | `AgentMission`+reader → resultado | sombra; ficheiro local protegido | nenhuma / orientação MEI, não decisão / não | 44 testes detectados; ADR-010 |
| `adapters/data_sanitization.py` | adapter | missão tipada → resultado | sombra | nenhuma / nenhuma / não | 34 testes; ADR-011/016 |
| `adapters/consistency_audit.py` | adapter | missão tipada → resultado | sombra | nenhuma / consistência interna, não verdade fiscal / não | 94 testes; ADR-012/017 |
| `adapters/memorial_validator.py` | adapter | missão tipada → resultado | sombra | nenhuma / valida memorial, não decide / não | 75 testes; ADR-013/018 |
| `adapters/agent_erro_operacional.py` | adapter | missão/event snapshot → diagnóstico | sombra | nenhuma / nenhuma / não | 62 testes; ADR-014 |
| `adapters/agent_erro_operacional_llm_fallback.py` | adapter | missão/event snapshot → bloqueio/erro | canário | nenhuma / nenhuma / **não**, `llm_used=false` | 73 testes; ADR-015 |
| `engines/__init__.py` | suporte | pacote → pacote | inactivo | nenhuma / nenhuma / não | arquitectura; ADR-008 |
| `engines/ag_encerramento.py` | engine | snapshot → orientação/payload | sombra; ficheiro local protegido | nenhuma / determinístico, não decisão / não | adapter encerramento; ADR-010 |
| `engines/data_sanitization.py` | engine | contexto tipado → alertas/payload | sombra | nenhuma / nenhuma / não | adapter sanitização; ADR-011 |
| `engines/consistency_audit.py` | engine | pares tipados → alertas/payload | sombra | nenhuma / não decide verdade fiscal / não | adapter consistência; ADR-012 |
| `engines/memorial_validator.py` | engine | contexto tipado → alertas/payload | sombra | nenhuma / nenhuma / não | adapter memorial; ADR-013 |
| `engines/agent_erro_operacional.py` | engine | snapshot → diagnóstico determinístico | sombra | nenhuma / nenhuma / não | adapter erro; ADR-014 |
| `engines/agent_erro_operacional_llm_fallback.py` | engine | snapshot → elegibilidade | canário | nenhuma / nenhuma / não chama router/provider | fallback; ADR-015 |
| `readers/__init__.py` | suporte | pacote → pacote | inactivo | nenhuma / nenhuma / não | arquitectura; ADR-010 |
| `readers/ag_encerramento.py` | reader | missão/tenant/empresa → snapshot | sombra | leitura BD apenas; sem commit / nenhuma / não | adapter encerramento; ADR-010 |

### 7.3 Contratos

| Caminho | Natureza | Contrato / uso | Estado | Escrita / fiscal / LLM | Testes e ADR |
|---|---|---|---|---|---|
| `contracts/__init__.py` | suporte | exports contratuais | vigente | nenhuma / nenhuma / não | arquitectura; ADR-008 |
| `contracts/canonical.py` | contrato | JSON/hash canónicos | vigente | nenhuma / nenhuma / não | canonical; ADR-008 |
| `contracts/sanitization.py` | contrato/guarda | contexto/resultado → validação profunda | vigente | nenhuma / nenhuma / não | sanitização; ADR-008 |
| `contracts/shared.py` | contrato | fontes, orçamento, evidências, alertas, acções | vigente | nenhuma / limita autoridade / metadados apenas | 38 testes; ADR-008 |
| `contracts/mission.py` | contrato | `AgentMission` | vigente | declara, não concede escrita / autoridade tipada / orçamento tipado | 36 testes; ADR-008 |
| `contracts/execution_result.py` | contrato | `AgentExecutionResult` | vigente | regista acções, não as executa / nenhuma / metadados | 45 testes; ADR-008 |
| `contracts/validation.py` | contrato/suporte | missão+resultado → validação cruzada | vigente | nenhuma / valida limites / valida orçamento | 19 testes correlatos; ADR-008 |
| `contracts/ag_abertura.py` | contrato | contexto/payload abertura | sombra | nenhuma / orientação / não | adapter; ADR-009 |
| `contracts/ag_encerramento.py` | contrato | snapshot/payload encerramento | sombra | nenhuma / orientação MEI / não | adapter; ADR-010 |
| `contracts/data_sanitization.py` | contrato | oito campos/alertas/payload | sombra | nenhuma / nenhuma / não | adapter; ADR-011/016 |
| `contracts/consistency_audit.py` | contrato | pares/alertas/payload | sombra | nenhuma / consistência interna / não | adapter; ADR-012/017 |
| `contracts/memorial_validator.py` | contrato | memorial/alertas/payload | sombra | nenhuma / validação não fiscal / não | adapter; ADR-013/018 |
| `contracts/agent_erro_operacional.py` | contrato | snapshots/diagnóstico | sombra | nenhuma / nenhuma / sem chamada no contrato | adapter; ADR-014 |
| `contracts/agent_erro_operacional_llm_fallback.py` | contrato | contexto/output reservado/payload | canário | nenhuma / nenhuma / output LLM reservado, não executado | fallback; ADR-015 |

O inventário contém 50 ficheiros. Não há prova de que os agentes legados
listados no registry estejam activos em produção. `app/main.py` instancia
`AgentScheduler`, mas a evidência arquitectural examinada exige que o lifespan
não o inicie; instância não equivale a execução. Também não há prova de que os
adapters L3 sejam publicados por registry, scheduler ou executor soberano.

## 8. Testes arquitecturais e contratuais relacionados com B14

Foram examinados: `test_agent_canonical_contract.py`,
`test_agent_contract_architecture.py`, `test_agent_contract_sanitization.py`,
`test_agent_shared_contracts.py`, `test_agent_mission_contract.py`,
`test_agent_mission_factory.py`, `test_agent_execution_result_contract.py`,
`test_agent_mission_result_validation.py` e os testes de missão de abertura,
encerramento, sanitização, consistência, memorial, erro operacional e fallback.

A contagem lexical de funções `test_*` nos ficheiros que usam essa forma
directa totaliza 710 (alguns testes parametrizados representam mais cenários;
dois ficheiros usam estruturas que não são contadas por esse método). Nenhum
teste foi executado nesta auditoria, conforme a natureza documental. A
existência dos testes prova cobertura codificada, não activação produtiva.

## 9. Itens superados, incorrectos e não provados

### Superados/concluídos

- B13 como fase corrente e “fecho B13” como próximo bloqueante.
- criação futura de FONTES_TRIBUTARIAS/manifest sem reconciliar entregas B13.
- LLMRouter, providers, schemas e testes tratados como ficheiros futuros.
- EventoOperacional tratado apenas como proposta.
- prompt universal e fases 0–4 como arquitectura corrente.
- inventário pré-B14 e sanitização rasa.

### Incorrectos

- salário mínimo de 2026 em `1518.00` e referência a Decreto 12.302/2026;
  B13-OPS-12 regista `1621.00`, Decreto 12.797/2025, ainda com fonte em revisão.
- descrição do inventário como apenas oito agentes desligados.
- função rasa `sanitizar_contexto` como regra suficiente diante do
  `ContextSanitizationGuard` canónico.

Este relatório não ratifica o valor normativo alternativo: apenas documenta a
contradição com a fonte institucional consultada.

### Não provados

- modelos actuais DeepSeek, nomes `deepseek-v4-*`, disponibilidade, endpoints,
  preços ou depreciação em 2026-07-24;
- vigência externa das fontes/diplomas enumerados no roadmap;
- SLA de 30 minutos;
- activação/desactivação individual de todos os agentes legados;
- fecho documental de cada cenário T1–T8 e do feedback do Pilot 0.

Não se usou internet e nenhuma informação externa nova substituiu essas
afirmações.

## 10. Conflitos institucionais

1. `AGENTS.md` dá hierarquia explícita que inclui GPT acima de ADRs; CCS-001,
   artigo 1, formula uma cadeia própria e está marcado **EM CONSTRUÇÃO**. A
   missão proíbe resolver divergências de precedência; fica registada.
2. ADR-009 declara “ratificado pelo GPT” mas “aguarda ratificação final de
   Miguel”, embora o commit `d11130d` diga “ratificar” e a implementação exista.
3. ADR-011 também declara aguardar ratificação de Miguel, embora commits e
   migração B14.3C existam.
4. REPORT-008/009/010 preservam estados textuais “aguarda commit/push” nos
   próprios documentos, embora commits posteriores estejam presentes no
   baseline. São qualificações históricas desactualizadas, não autoridade para
   reinterpretar o documento.
5. O roadmap permite uma leitura de activação global por flags; ADR-008 e
   adapters B14 exigem missão e fronteiras específicas.
6. O “circuito fechado” do roadmap sugere progressão automática a patch,
   commit, deploy e actualização de memória; a governação vigente exige
   autorização, escopo e escritor único e não autoriza essa cadeia.

## 11. Riscos de manter o roadmap actual

- decisão operacional baseada em fase e gates já superados;
- uso de valor/referência normativa incorrecta ou fonte sem autoridade;
- activação indevida por flag genérica de componentes legados com escrita;
- regressão da sanitização profunda para filtragem rasa;
- confusão entre código existente, sombra, canário e produção activa;
- expectativa de LLM real onde ADR-015 a proíbe;
- dependência de nomes de provider/modelo temporais e não ratificados;
- ocultação dos gates de proveniência, granularidade, autorização e
  integração soberana;
- normalização de circuito automático incompatível com governação actual.

## 12. Estrutura proposta para futura versão

Uma futura versão, ainda não autorizada, deve conter:

1. identidade e versão;
2. autoridade e fontes de verdade;
3. estado actual comprovado;
4. marcos concluídos;
5. arquitectura L3 vigente;
6. agentes e adapters;
7. fronteiras de activação;
8. riscos e gates abertos;
9. dependências normativas;
10. sequência futura autorizável;
11. critérios de saída;
12. dívida histórica;
13. factos externos não canónicos;
14. preparação criptográfica;
15. histórico de versões.

Cada item deve estar exclusivamente em **CONCLUÍDO**, **EM AUDITORIA**,
**ABERTO**, **BLOQUEADO** ou **FUTURO NÃO AUTORIZADO**, com evidência, fonte,
vigência e responsável. Não devem ser usadas percentagens inventadas.

## 13. Factos externos a retirar ou isolar

A futura versão deve remover nomes de modelos não ratificados, expressar
capacidades abstractas e providers substituíveis, e remeter endpoints,
modelos, preço, disponibilidade e depreciação para manifesto versionado
próprio. Qualquer facto temporal deve possuir fonte, data de verificação,
vigência e autoridade. Valores e legislação normativa devem apontar para a
fonte institucional vigente, sem reprodução não provada no roadmap.

## 14. Fronteira criptográfica e pós-quântica

O roadmap não é fonte criptográfica. Os hashes SHA-256 usados nesta auditoria
provam somente integridade byte a byte no momento da medição. Não provam
autoria, proveniência, não repúdio, timestamp confiável nem resistência
pós-quântica.

Nenhuma afirmação de segurança pós-quântica é autorizada. Uma futura
assinatura institucional deve ser versionada, substituível e decidida em ADR
próprio. O roadmap deve preservar agilidade criptográfica e independência de
algoritmo. Nenhuma criptografia foi implementada nesta missão.

## 15. Blockers

Não há blocker técnico para submeter este relatório à auditoria GPT. Há gates
institucionais e operacionais que a futura redacção deve representar sem os
resolver: ratificação humana dos estados documentais divergentes; proveniência
produtiva DataSanitization (ADR-016); granularidade/fronteira produtiva de
ConsistencyAudit (ADR-017); fronteiras do memorial além do escopo read-only
implementado; ausência de integração/execução/persistência/scheduler L3
produtivos; e dependências normativas ainda em revisão/pendentes.

## 16. Recomendação única

Recomenda-se uma missão posterior exclusivamente documental para redacção
controlada da nova versão de `docs/ROADMAP_OPS_AGENTES.md`, usando a matriz,
cronologia e inventário deste relatório, sem activar componentes nem escolher
prioridade estratégica. A recomendação justifica-se porque a auditoria provou
base suficiente para corrigir o estado documental e também delimitou os gates
que não podem ser apresentados como concluídos.

A auditoria e a ratificação foram concluídas, sem autorização para alterar o
roadmap.

## 17. Verificação final

Os hashes protegidos finais, o estado Git final e o stage vazio são registados
após a criação deste ficheiro. O SHA-256 final do próprio REPORT-011 é
necessariamente um hash externo: não pode ser inserido no conteúdo que ele
próprio mede sem alterar os bytes. Deve ser apresentado no handoff externo da
execução.

| Verificação | Resultado final |
|---|---|
| Hashes protegidos | quatro hashes finais idênticos aos iniciais |
| Hash do roadmap | `16B24C2CDD718AEB6E4AF1A59B74689E0EEB036FFFDEFFDA5C939EAC6FB8CE70` |
| Hash externo do REPORT-011 | calculado após fecho e apresentado no handoff |
| Stage | vazio |
| Estado Git | quatro modificações locais protegidas esperadas e apenas REPORT-011 como novo caminho |
| Commit | nenhum |
| Push | nenhum |
| Deploy | nenhum |
