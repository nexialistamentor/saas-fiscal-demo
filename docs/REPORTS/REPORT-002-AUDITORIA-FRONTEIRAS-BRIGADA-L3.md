# REPORT-002  Auditoria de prontidão produtiva da Brigada L3

## 1. Identificação da missão

Missão: `MISSION-002`. Natureza: auditoria técnica read-only. Escopo: `DataSanitizationAgent`, `ConsistencyAuditAgent` e `MemorialValidatorAgent`. Resultado permitido: este relatório. Não foram executados commit, push, migrations ou alterações de produto.

## 2. Estado inicial do repositório

Comandos obrigatórios executados antes da auditoria:

```text
git branch --show-current: main
git rev-parse HEAD: 7cdacac5d4af200b4a4f9a0372a88b5bea607fbb
git rev-parse origin/main: 7cdacac5d4af200b4a4f9a0372a88b5bea607fbb
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
git diff --name-only: os mesmos quatro ficheiros
git diff --cached --name-only: vazio
```

Estado: SIM
Ficheiro: estado Git, não aplicável a ficheiro fonte.
Linhas: não aplicável.
Evidência: `HEAD == origin/main`; quatro alterações locais protegidas; stage vazio.
Implicação: a auditoria partiu da revisão remota esperada sem modificar o working tree.

## 3. Metodologia e limites

Pesquisa estática read-only com `rg`, leitura numerada de fontes e `alembic heads/history`. Áreas pesquisadas: `app/**/*.py`, `tests/**/*.py`, `migrations/versions`, `railway.toml`. Termos principais: nomes dos três agentes e adapters, `AgentMission`, `MissionFactory`, identificadores de correlação/idempotência, modelos fiscais, memorial, commits/rollbacks e scheduler/registry. Ausência é reportada apenas dentro dessas áreas e termos. Não se executaram testes por não serem necessários para comprovar estrutura estática e para evitar efeitos laterais.

## 4. Sumário executivo

Estado: NÃO
Ficheiro: `app/agents/agent_executor.py`; `app/agents/agent_registry.py`; `app/routes/relatorio_router.py`.
Linhas: executor 8-47; registry 24-35; router 357-405.
Evidência: não existe activação produtiva por missão L3; o executor aceita dicionário genérico e o registry inclui os três agentes legados; as rotas do memorial recolhem todos os dados antes de autorizar e pagar.
Implicação: a integração produtiva segura permanece bloqueada pelos gates ADR-011, ADR-012, ADR-013, executor/persistência/idempotência e política transaccional.

## 5. Integração produtiva geral

### Missões e chamadas

Estado: NÃO
Ficheiro: `app/agents/mission_factory.py`; `app/agents/adapters/data_sanitization.py`; `app/agents/adapters/consistency_audit.py`; `app/agents/adapters/memorial_validator.py`.
Linhas: factory 172-206; adapters 331-337, 356-361 e 340-341.
Evidência: a factory e as três funções existem, mas pesquisa por `create_mission`, `MissionFactory` e pelos três nomes `execute_*_mission` fora dos próprios adapters não encontrou chamador em produção. As chamadas encontradas estão em `tests/test_data_sanitization_mission_adapter.py:165-864`, `tests/test_consistency_audit_mission_adapter.py:210-1178` e `tests/test_memorial_validator_mission_adapter.py:195-1349`.
Implicação: não há código produtivo que crie `AgentMission`, use `MissionFactory` ou chame os adapters destes agentes; existência estrutural não constitui integração.

Estado: NÃO
Ficheiro: `app/main.py`; `app/agents/agent_scheduler.py`; `app/agents/agent_registry.py`.
Linhas: main 128-140 e 494; scheduler 38-56; registry 24-35.
Evidência: não há endpoint, service, job, evento ou worker L3; o único caminho encontrado é legado/genérico, e o startup periódico está comentado.
Implicação: activação explícita por missão não existe.

Estado: SIM
Ficheiro: `app/agents/agent_registry.py`; `app/agents/agent_scheduler.py`.
Linhas: registry 3-6 e 25-31; scheduler 7, 36 e 44-49.
Evidência: há importação e registo indirectos dos três agentes legados; o scheduler constrói contexto genérico e chama `run_all`.
Implicação: contraria o estado arquitectural declarado, embora o loop de startup esteja inerte.

## 6. Executor L3

Estado: NÃO
Ficheiro: `app/agents/agent_executor.py`.
Linhas: 8-47.
Evidência: `run_all(context)` percorre registry, chama `agent.run(context)`, grava `AlertaFiscal` e adiciona timestamp; não recebe `AgentMission` nem devolve `AgentExecutionResult`.
Implicação: executor actual é legado, não executor L3.

Estado: PARCIAL
Ficheiro: `app/agents/contracts/validation.py`; `app/agents/contracts/sanitization.py`; `app/agents/adapters/data_sanitization.py`; `app/agents/adapters/consistency_audit.py`; `app/agents/adapters/memorial_validator.py`.
Linhas: validation 182-193; adapters 331-337, 356-361 e 340-341.
Evidência: contratos, validação cruzada, sanitização e bloqueios locais existem nos adapters; não existe executor que os componha, dispatcher por `target_agent`/`mission_type`, persistência ou idempotência.
Implicação: capacidades isoladas não formam fronteira produtiva autorizada.

Estado: PARCIAL
Ficheiro: `app/agents/contracts/mission.py`; `app/agents/contracts/canonical.py`.
Linhas: mission 32-171; canonical 151-217.
Evidência: missão modela origem exclusiva, correlação, parent, request/event, `context_hash` e chave; não há controlo operacional/persistente desses valores.
Implicação: causalidade é contratual, não operacional.

Estado: NÃO
Ficheiro: repositório pesquisado (`app/agents`, `app/services`, `app/models.py`, migrations).
Linhas: não aplicável; termos `dispatcher`, `target_agent`, `mission_type`, modelos de missão e transação L3.
Evidência: não foi encontrado dispatcher nem política transaccional ratificada para executor L3.
Implicação: não é possível provar execução, rollback ou atomicidade L3 seguros.

Estado: NÃO COMPROVADO
Ficheiro: `app/agents/agent_executor.py`.
Linhas: 23-37.
Evidência: o executor legado cria Session própria e faz `commit`, sem `rollback`; portanto não partilha a sessão do chamador. Não existe executor L3 para avaliar rollback compartilhado.
Implicação: o risco solicitado não se aplica ao executor existente, mas permanece sem política para um futuro executor.

## 7. Persistência e idempotência

Estado: NÃO
Ficheiro: `app/models.py`; `migrations/versions/0000_baseline_soberana.py` a `0017_alertas_resolucao.py`.
Linhas: modelos 1-805; cadeia Alembic integral.
Evidência: não há ORM/tabela para `AgentMission` ou `AgentExecutionResult`, nem migration correspondente.
Implicação: missão, resultado, estado, tentativa, timestamps e resultado serializado L3 não são persistidos.

Estado: NÃO
Ficheiro: `app/models.py`.
Linhas: 1-805.
Evidência: pesquisa por `mission_id`, `idempotency_key`, `context_hash`, `correlation_id`, `parent_mission_id`, `source_request_id` e `source_event_id` não encontrou armazenamento L3.
Implicação: não existe `UNIQUE`, claim concorrente ou consulta equivalente para impedir duplicação de missão.

Estado: PARCIAL
Ficheiro: `app/agents/contracts/canonical.py`.
Linhas: 151-217.
Evidência: existem apenas `build_mission_idempotency_key` e `build_context_hash`, sem consulta ou persistência.
Implicação: idempotência é construção estrutural, não garantia concorrente.

## 8. Scheduler e registry

Estado: NÃO
Ficheiro: `app/main.py`.
Linhas: 128-140 e 494.
Evidência: `scheduler = AgentScheduler()` existe, mas ambas as chamadas `asyncio.create_task(...iniciar_loop...)` estão comentadas.
Implicação: scheduler legado não está activo no startup produtivo observado.

Estado: SIM
Ficheiro: `app/agents/agent_registry.py`; `app/agents/agent_executor.py`.
Linhas: registry 3-6, 25, 30-31; executor 16-20.
Evidência: as três classes legadas correspondentes aos agentes estão presentes no registry genérico e seriam chamadas por `run_all` com contexto genérico. Os três adapters L3 não estão registados, não possuem chamador produtivo e permanecem isolados do scheduler legado.
Implicação: a presença das classes legadas cria risco de activação acidental caso o scheduler genérico seja ligado. O isolamento actual dos adapters L3 está preservado.

## 9. DataSanitizationAgent

### Proveniência dos oito campos fiscais

Fonte produtiva candidata: `InsightEngine._montar_contexto_engines`, não ligada ao adapter L3.

| Campo exacto | Origem/fórmula | Unidade/período | Negativo/ausência/default/autorização |
|---|---|---|---|
| `faturamento` | soma de `NotaFiscalItem.valor_produto`, documentos `saida` (`app/services/insights_engine.py:70-76`) | moeda; todo o histórico, sem cutoff | preserva soma; ausência vira 0; só `empresa_id`, sem actor |
| `custos` | soma de `valor_produto`, documentos `entrada` (77-83) | moeda; todo o histórico | ausência vira 0; sem actor |
| `lucro_contabil` | `max(0, faturamento-custos)` (100,115) | moeda; histórico | negativos truncados; ausência vira 0 |
| `lucro` | mesma fórmula truncada (100,116) | moeda; histórico | negativos truncados; ausência vira 0 |
| `regime` | `empresa.regime_tributario` ou `presumido` (98-99) | categoria; estado actual | default silencioso inclusive empresa ausente |
| `icms_pago` | soma histórica de `ItemFiscal.valor_st` em entradas (84-90,120) | moeda; histórico | ausência vira 0; agregado distinto por tipo de documento; deriva da mesma família de dados declarados `ItemFiscal.valor_st`; sem proveniência independente comprovada; sem cutoff temporal e sem actor autorizado |
| `icms_devido` | soma histórica de `valor_st` em saídas (91-97,121) | moeda; histórico | ausência vira 0; agregado distinto por tipo de documento; deriva da mesma família de dados declarados `ItemFiscal.valor_st`; sem proveniência independente comprovada; sem cutoff temporal e sem actor autorizado |
| `custo_fiscal_entradas` | igualado a `custos` (114) | moeda; histórico | sem prova semântica fiscal independente |

Estado: NÃO
Ficheiro: `app/services/insights_engine.py`; `app/agents/contracts/data_sanitization.py`.
Linhas: service 68-127; contrato 32-39 e 150-159.
Evidência: o serviço devolve ainda `db`, `data_referencia`, `base_calculo`, `atividade` hardcoded e `context_flags`; o contrato é `extra="forbid"` e admite somente identidade mais os oito campos.
Implicação: contexto actual não atravessa directamente a fronteira L3; transporta Session e extras.

Estado: NÃO
Ficheiro: `app/services/insights_engine.py`.
Linhas: 70-105.
Evidência: consultas filtram apenas `empresa_id`; `data_referencia` é só `max(data_emissao)`, não delimita leituras; não há `reference_at`, início/fim, tenant ou actor.
Implicação: proveniência temporal e autorização não são comprovadas.

Estado: SIM
Ficheiro: `app/services/insights_engine.py`.
Linhas: 71-97.
Evidência: a fonte candidata converte agregados ausentes em zero antes da fronteira L3. O agente possui o diagnóstico canónico `CONTEXTO_SEM_CAMPOS_FISCAIS` para contexto sem campos fiscais, mas a transformação anterior apaga a ausência antes de o contexto chegar ao agente.
Implicação: a proveniência de ausência é perdida na fonte ou projector anterior ao agente, impedindo a activação do diagnóstico canónico. O problema não é falta de capacidade diagnóstica do DataSanitizationAgent.

### ADR-011-PROVENIENCIA-001

Estado técnico observado: fontes candidatas históricas e agregadas existem, mas não constituem reader L3 autorizado e perdem ausência, negativos de lucro, período e actor.

Gate produtivo: ABERTO; integração produtiva bloqueada.

Evidências: `app/services/insights_engine.py:68-127`; `app/agents/contracts/data_sanitization.py:32-39,144-159`.

Decisões ainda necessárias: fonte canónica/unidade/período dos oito campos; semântica de custo fiscal e ICMS; política de ausência/zero/negativo; fronteira tenant/actor. Este relatório não decide essas matérias.

## 10. ConsistencyAuditAgent

Estado: PARCIAL
Ficheiro: `app/models.py`.
Linhas: 430-468.
Evidência: `ItemFiscal` persiste por item `base_st` e `valor_st`, além de `base_icms`/`valor_icms`; não há `mva_xml`, `base_st_calculada` ou `icms_st_calculado` persistidos.
Implicação: apenas o lado declarado XML tem campos identificáveis no nível de item.

Estado: PARCIAL
Ficheiro: `app/services/tax_consistency/tax_consistency_engine.py`.
Linhas: 20-129.
Evidência: engine aceita dois dicionários independentes e compara `valor_st/icms_st`, `mva_xml/mva_utilizada`, `base_st/base_st_calculada`; se qualquer lado faltar, retorna consistente sem divergências (52-56, 82-86, 111-115).
Implicação: chamada legada com contexto vazio produz falso consistente.

Estado: SIM
Ficheiro: `app/agents/contracts/consistency_audit.py`; `app/agents/engines/consistency_audit.py`.
Linhas: contrato 60-61 e 125-157; engine 113-132.
Evidência: contrato L3 oferece três pares e o motor L3 exige pelo menos um par completo não nulo.
Implicação: o falso consistente vazio está bloqueado dentro do motor L3, mas falta reader produtivo.

Estado: NÃO COMPROVADO
Ficheiro: `app/services/analysis_orchestrator.py`; `app/motor_fiscal.py`; `app/xml_service.py`.
Linhas: pesquisa por pares calculados e fluxos de XML.
Evidência: não foi localizado armazenamento produtivo dos lados calculados; o motor produz resultados em memória, sem vínculo canónico por item/documento ao `ItemFiscal` declarado.
Implicação: independência e granularidade da comparação não são demonstráveis.

Estado: PARCIAL
Ficheiro: `app/services/registro_analise_service.py`.
Linhas: 86-129, 149-180.
Evidência: `executar_analise_xml(xml_bytes)` ocorre na linha 102; depois `processar_e_persistir_xml(xml_bytes)` nas linhas 113-118, logo o XML atravessa análise e persistência separadas. `processar_e_persistir_xml` devolve documento, mas o chamador descarta o retorno; `DuplicataFiscalError` é capturada sem usar `documento_id` (119-123).
Implicação: não há ligação inequívoca conservada entre `DocumentoFiscal` e `RelatorioAnalise`; há parsing/análise repetidos no mesmo fluxo.

Estado: NÃO
Ficheiro: `app/models.py`.
Linhas: `DocumentoFiscal` 420-468; `RelatorioAnalise` 587-616; `EngineResultado` 774-782.
Evidência: relatório e engine ligam-se por FK opcional, mas documento não tem FK para relatório e o relatório conserva apenas `xml_chave`; não há unicidade/granularidade de engine por item ou documento.
Implicação: escolher primeiro item, somar ou agregar seria decisão não ratificada; nenhuma dessas políticas está comprovada.

### ADR-012-GRANULARIDADE-001

Estado técnico observado: XML declarado é persistido por item; resultados calculados não estão persistidos em pares independentes com ligação ao mesmo item/documento; granularidade não está decidida.

Gate produtivo: ABERTO; integração produtiva bloqueada.

Evidências: `app/models.py:430-468,587-616,774-782`; `app/services/tax_consistency/tax_consistency_engine.py:20-129`; `app/services/registro_analise_service.py:86-123`.

Decisões ainda necessárias: item/documento/relatório/agregado; proveniência independente de cada par; vínculo documento-relatório-engine; tratamento de múltiplos itens e duplicatas.

## 11. MemorialValidatorAgent

### Fronteira de autorização

Estado: SIM
Ficheiro: `app/routes/relatorio_router.py`; `app/services/memorial_service.py`.
Linhas: router 357-399; service 57-150.
Evidência: JSON e PDF chamam `coletar_contexto_memorial` antes de comparar `user_id` e antes de `pago`; o agregador consulta relatório por ID e materializa engines, alertas, insights e referências.
Implicação: relatório alheio autenticado e relatório não pago causam leitura completa antes de 403/402.

Estado: SIM
Ficheiro: `app/routes/relatorio_router.py`; `app/security.py`.
Linhas: router 371-375 e 393-399; security 150-171; dashboard 52-55.
Evidência: memorial exige criador exacto (`rel.user_id`); dashboard usa `verificar_acesso_relatorio`, que aceita criador ou empresa pertencente ao utilizador.
Implicação: há divergência exacta de política entre dashboard e memorial.

Estado: PARCIAL
Ficheiro: `app/routes/relatorio_router.py`.
Linhas: 367-375 e 389-399.
Evidência: respostas distinguem 404, 403 e 402 após diferentes condições sobre contexto materializado.
Implicação: existe superfície de enumeração diferenciada; explorabilidade não foi testada.

Estado: NÃO
Ficheiro: `app/services/memorial_service.py`.
Linhas: 153-164.
Evidência: marcação consulta apenas por ID, altera `memorial_gerado` e faz commit sem reconfirmar utilizador, empresa ou pagamento.
Implicação: a operação de escrita não preserva autonomamente a fronteira de autorização.

### Projecção mínima

Estado: NÃO
Ficheiro: `app/services/memorial_service.py`; `app/agents/contracts/memorial_validator.py`.
Linhas: service 75-150; contrato 144-190.
Evidência: serviço produz relatório com `user_id`, `analysis_type`, `xml_chave`, tempo, score, `resultado_json`, fingerprint, pago, memorial, timestamp; engines com resultado integral/timestamp; alertas; insights; referências com código/título/descrição/UF/vigência/URL. Contrato aceita só `empresa_id`, `relatorio_id`, snapshot `{id,empresa_id,status,total_alertas}`, engines `{engine_nome}`, e referências `{fundamento}`; `extra="forbid"`.
Implicação: projecção actual seria rejeitada e materializa dados fiscais/pessoais desnecessários.

Estado: PARCIAL
Ficheiro: `app/services/memorial_service.py`.
Linhas: 75-127.
Evidência: nenhum ORM/Session é devolvido; serialização é para dict. Ordenação usa apenas `criado_em`, sem desempate por ID; referências por código. Não há unicidade de engine por relatório/nome.
Implicação: projecção não é determinística em empates e admite engines repetidas.

Estado: NÃO
Ficheiro: `app/models.py`.
Linhas: 774-782.
Evidência: `EngineResultado.empresa_id` não tem FK; `relatorio_analise_id` é nullable; não existe unique `(relatorio_analise_id, engine_nome)`.
Implicação: coerência da engine com relatório não é garantida pelo schema.

### Referências legais

Estado: NÃO
Ficheiro: `app/models.py`; `app/scripts/seed_referencias_legais.py`; `app/services/pdf_report_service.py`.
Linhas: models 625-650 e 755-768; seed 1-6,20-126; PDF 242-245 e 299-323.
Evidência: não há FK entre `Insight` e `ReferenciaLegal`; seed declara convenção `Insight.tipo == ReferenciaLegal.codigo`; PDF constrói `ref_map` por código e procura pelo tipo.
Implicação: cobertura jurídica depende de convenção textual.

Estado: SIM
Ficheiro: `app/services/pdf_report_service.py`.
Linhas: 299-323.
Evidência: quando `ref_map.get(tipo)` não encontra correspondência, o PDF não bloqueia e não gera alerta. A geração continua e apresenta o fallback textual: "Fundamento: base normativa em actualização."
Implicação: a ausência de referência aplicável é substituída por um fallback textual com aparência de fundamento normativo, sem bloqueio e sem alerta explícito.

Estado: PARCIAL
Ficheiro: `app/services/memorial_service.py`.
Linhas: 37-54,127.
Evidência: carrega até 200 referências gerais, opcionalmente UF; não selecciona códigos exigidos pelos insights nem filtra vigência, tributo, regime, NCM, operação, engine ou tipo.
Implicação: limite pode truncar silenciosamente e não há data normativa definida.

Estado: NÃO
Ficheiro: `app/models.py`; `app/services/memorial_service.py`.
Linhas: models 755-768; service 127-150.
Evidência: memorial não preserva snapshot imutável do fundamento; lê referências mutáveis no momento da geração.
Implicação: alterar referência pode mudar fundamento de memorial antigo.

Estado: PARCIAL
Ficheiro: `app/agents/contracts/memorial_validator.py`; `app/agents/engines/memorial_validator.py`.
Linhas: contrato 165-190; engine verificações de referências vazias/incompletas.
Evidência: contrato recebe apenas `fundamento`, não `codigo` nem insights; agente detecta lista vazia ou fundamento incompleto.
Implicação: não consegue provar cobertura de um fundamento por insight.

### Mutação e semântica HTTP

Estado: SIM
Ficheiro: `app/routes/relatorio_router.py`; `app/services/memorial_service.py`.
Linhas: router 357-399; service 153-164.
Evidência: ambos GET chamam escrita; campo `memorial_gerado=True`; commit interno. JSON marca após checks; PDF gera bytes e marca antes de construir/entregar `StreamingResponse`.
Implicação: leitura, validação, geração, publicação e marcação não estão separadas; falha de streaming pode ocorrer após commit.

Estado: PARCIAL
Ficheiro: `app/services/memorial_service.py`.
Linhas: 153-164.
Evidência: atribuir True é repetível, mas cada chamada faz commit; o commit pode incluir alterações pendentes externas na Session compartilhada.
Implicação: efeito lógico é idempotente, fronteira transaccional não é.

### Testes da fronteira

| Teste | Prova | Não prova / técnica |
|---|---|---|
| `tests/test_ops12_f6_memorial_contract.py:45-76` `test_f6_memorial_retorna_200_com_contexto` | 200, colector e marcação chamados | monkeypatch; cristaliza mutação em GET; não usa funções reais |
| `:83-112` inexistente | 404 e sem marcação | colector fake |
| `:119-148` outro utilizador | 403 e sem marcação | exige que colector já tenha sido chamado; cristaliza leitura antes do 403 |
| `:155-184` não pago | 402 e sem marcação | exige contexto recolhido; cristaliza leitura antes do 402 |
| `:191-214` sem auth | 401 antes do colector | dependências e funções patched |
| `tests/test_e2e_bloco2_memorial.py:130-148` | PDF não pago retorna 402 | não prova ausência de leitura/geração/mutação |
| `:150-176` | PDF pago retorna 200 | não verifica marcação nem ordem |
| `:178-204` | bytes começam `%PDF` | não verifica conteúdo, autorização cruzada ou fundamento |
| `tests/test_memorial_validator_mission_adapter.py:195-1694` | contrato/engine/adapter L3 isolados | não cobre rota, agregador ou marcação reais |

Estado: NÃO
Ficheiro: `tests` pesquisado por memorial, colector, marcação, acesso, pagamento e PDF.
Linhas: referências na tabela anterior.
Evidência: não existe teste directo do agregador real nem da função real de marcação; não há teste PDF de outro utilizador, ausência de leitura antes de 403/402, ausência de geração em acesso negado, ausência de mutação em falha ou marcação somente após resposta PDF válida.
Implicação: os riscos da fronteira real não estão protegidos.

### ADR-013-FRONTEIRA-001

Estado técnico observado: autorização e pagamento ocorrem depois da materialização; política diverge do dashboard; GET muta e commit interno não reconfirma autoridade; projecção não corresponde ao contrato mínimo.

Gate produtivo: ABERTO; integração produtiva bloqueada.

Evidências: `app/routes/relatorio_router.py:357-405`; `app/services/memorial_service.py:57-164`; `app/security.py:150-171`; testes acima.

Decisões ainda necessárias: política de propriedade, ordem 404/403/402, projecção mínima, instante de marcação/publicação e fronteira transaccional. Este relatório não escolhe políticas.

## 12. Política transaccional

Estado: SIM
Ficheiro: `app/database.py`.
Linhas: 21-28 e 173-178.
Evidência: `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`; `get_db` abre, faz yield e apenas fecha.
Implicação: commit/rollback ficam a cargo dos chamadores/serviços.

Estado: NÃO
Ficheiro: repositório pesquisado por `begin_nested`, `savepoint`, gestor L3 e `no_autoflush`.
Linhas: único `no_autoflush` em `app/agents/readers/ag_encerramento.py:104`; nenhum savepoint L3.
Evidência: não existe gestor transaccional L3 ou savepoints nos serviços auditados.
Implicação: sessão compartilhada não tem isolamento de unidade L3.

Estado: SIM
Ficheiro: `app/services/memorial_service.py`; `app/services/registro_analise_service.py`; `app/services/insights_engine.py`.
Linhas: memorial 163; registro 41,75,153-166; insights 371.
Evidência: serviços internos fazem commit; registro usa prequery, insert, captura `IntegrityError`, `rollback` e requery.
Implicação: rollback sobre Session recebida pode invalidar trabalho exterior não confirmado; commit pode confirmar trabalho exterior.

Estado: NÃO COMPROVADO
Ficheiro: fontes transaccionais acima.
Linhas: acima.
Evidência: não há ADR/política L3 implementada que permita reutilização segura da mesma Session.
Implicação: futuro executor L3 não pode ser considerado transaccionalmente seguro.

## 13. Banco, migrations e deploy

Estado: SIM
Ficheiro: `migrations/versions/0017_alertas_resolucao.py`.
Linhas: 35-53.
Evidência: `alembic heads` devolveu um head: `0017_alertas_resolucao`; `down_revision = 0016_add_insights_superseded`.
Implicação: cadeia canónica observada é linear e tem um head.

Estado: SIM
Ficheiro: `railway.toml`.
Linhas: 5-7.
Evidência: Railway executa `alembic upgrade head` em `preDeployCommand` antes de `uvicorn`.
Implicação: migrations são mecanismo de deploy produtivo observado.

Estado: SIM
Ficheiro: `app/main.py`.
Linhas: 128-129 e 242.
Evidência: lifespan e caminho adicional chamam `Base.metadata.create_all(bind=engine)`.
Implicação: modelos sem migration podem ser criados em ambientes onde a aplicação inicia sobre schema ausente; `create_all` não migra colunas existentes.

Estado: PARCIAL
Ficheiro: `app/database.py`; `migrations/env.py`; `tests/conftest.py`.
Linhas: database 21-28,155-170; env 13-25; conftest configuração de SQLite.
Evidência: produção Railway usa PostgreSQL/Alembic; execução sem `DATABASE_URL` cai em SQLite local e aplica compatibilidade/create_all; testes usam SQLite e criação de metadata.
Implicação: schema local/teste pode divergir da disciplina produtiva de migrations.

## 14. Matriz de evidências

| Gate | Estado | Evidência principal | Bloqueia integração produtiva |
|---|---|---|---|
| Criação produtiva de AgentMission | NÃO | factory sem chamador produtivo; `mission_factory.py:172-206` | SIM |
| Executor L3 | NÃO | executor legado `agent_executor.py:8-47` | SIM |
| Persistência de missões | NÃO | sem ORM/migration | SIM |
| Persistência de resultados | NÃO | sem ORM/migration | SIM |
| Idempotência concorrente | NÃO | apenas builders `canonical.py:151-217` | SIM |
| ADR-011-PROVENIENCIA-001 | ABERTO | `insights_engine.py:68-127` | SIM |
| ADR-012-GRANULARIDADE-001 | ABERTO | `models.py:430-468`; consistency engine | SIM |
| ADR-013-FRONTEIRA-001 | ABERTO | router 357-405; memorial service 57-164 | SIM |
| Política transaccional L3 | NÃO | commits/rollback internos, sem gestor | SIM |
| Activação por missão explícita | NÃO | nenhum chamador produtivo | SIM |
| Adapters L3 isolados do scheduler legado | SIM | adapters sem registo e sem chamador produtivo | NÃO |
| Agentes legados presentes no registry genérico | SIM | `app/agents/agent_registry.py` | SIM |

## 15. Pendências formais

1. Decisão GPT sobre os gates ADR-011-PROVENIENCIA-001, ADR-012-GRANULARIDADE-001 e ADR-013-FRONTEIRA-001.
2. Ratificação de Miguel das decisões arquitecturais correspondentes.
3. Definição autorizada de executor, persistência/idempotência e política transaccional L3.
4. Resolução explícita da presença dos três agentes no registry legado, sem alteração nesta missão.

## 16. Riscos não resolvidos

- Activação acidental dos agentes legados por `run_all` se o scheduler for ligado.
- Contexto fiscal histórico sem cutoff/actor, defaults silenciosos e truncamento de prejuízo.
- Comparação sem pares persistidos independentes e sem granularidade/vínculo canónico.
- Leitura de dados do memorial antes de autorização/pagamento e regras divergentes.
- Mutação e commit em GET, com possível confirmação de trabalho exterior.
- Referências legais por convenção textual, sem snapshot ou cobertura por insight.
- Divergência potencial entre PostgreSQL/Alembic e SQLite/create_all.

## 17. Estado final do repositório

Verificação final obrigatória executada sem restaurar ou corrigir diferenças:

```text
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md
git diff --name-only:
app/agents/adapters/ag_encerramento.py
app/agents/engines/ag_encerramento.py
docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
tests/test_ag_encerramento_mission_adapter.py
git diff --cached --name-only: vazio
```

Estado: SIM
Ficheiro: estado Git e este relatório.
Linhas: não aplicável.
Evidência: quatro alterações protegidas preservadas, um único novo relatório e stage vazio.
Implicação: o estado final corresponde ao permitido pela missão.

## 18. Declaração de não alteração

Foi criado exclusivamente `docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md`. Nenhum código, teste, ADR, migration ou ficheiro protegido foi deliberadamente alterado; nenhum ficheiro foi apagado, formatado ou movido; nenhum stage, commit ou push foi efectuado.

Estado da execução da missão:
EXECUTADA COM PENDÊNCIAS

Auditoria:
PENDENTE  autoridade GPT

Ratificação:
PENDENTE  autoridade Miguel
