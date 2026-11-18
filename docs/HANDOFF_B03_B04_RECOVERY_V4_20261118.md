# HANDOFF soberano SOLVERIS — recuperação Enterprise B03/B04 rumo a B06

**Corte:** 18/11/2026. **Autoridade:** Coach Miguel + GPT. **Estado:** RECOVERY_EM_CURSO; CONTRATO_DIRIGIDO_RED; GLOBAL_GREEN=false. **Destinatário:** qualquer sessão futura GPT/Codex, que deve retomar exatamente deste estado e confirmar hashes antes de agir.

## 1. Missão e limites ratificados

Recuperar, com prova de origem e execução, a cadeia **B02 → G12 → G13 → I0/I2 → B03 → B04**, incluindo B01 sintético e G1 segregado, para só depois regressar ao mapeamento original de **B06 Fase 0**. Não declarar B03/B04 recuperados enquanto o circuito real e as catracas estiverem RED.

- Preservar B01 sintético com **UF PR**, sem substituir por PA: a solução SOLVERIS Enterprise tem finalidade **nacional**, embora a autorização do resolvedor da main permaneça limitada ao piloto PA.
- Não ampliar autoridade fiscal a PR nem a qualquer UF sem fonte/autorização; cálculo observacional não é prova normativa, crédito, checkout nem publicação.
- Não tocar no MEI, no TaxConsistencyEngine compartilhado, no resolvedor fiscal compartilhado, nas migrações, main, produção, Railway, Vercel ou contratos B01/G1 para obter GREEN.
- Contratos originais, hashes, origem histórica e testes negativos são imutáveis durante correção. Nunca skip, xfail, deselect, relaxamento de asserções ou mudança silenciosa de fixtures.
- Cada decisão, recibo, patch e handoff durável pertence ao **Git**. Branch isolado de recuperação, **sem merge e sem deploy** até aprovação formal. Auto-deploy continua desativado.

## 2. Identidade do Git e ambiente Windows

- Repositório: nexialistamentor/saas-fiscal-demo.
- Main congelada de referência: **a6a2da6cbf07c7b9922f8571bf2e6016376304d5**.
- Branch Git de custódia: **recovery/enterprise-b00-b04-20261117**. Último commit documental confirmado antes deste handoff: **2c5ae9f1de4417b8e036b5ba6b6bcb7b6e83f7e0**.
- Worktree do Miguel: **C:\dev\saas-fiscal-demo-b06-green-20261118**, com branch recovery acima, V2 + V3 + V3.1 aplicados sem commits de produto. O caminho antigo **C:\dev\saas-fiscal-demo-a1** tem dados untracked do utilizador: **não limpar nem substituir**.
- Python **3.12.10**, FastAPI **0.135.1**, Pydantic **2.12.5**; Docker Server **29.6.1**. No Windows usar o virtualenv .venv-release, ENVIRONMENT=test e DATABASE_URL de SQLite de teste quando os procedimentos assim exigirem.
- Baseline JUnit de main: **.pytest_cache/b03b04_baseline_main.xml**, SHA-256 **798A14E3A2C6C517DD179559395A12E7FC370CDB49EB2FA3BD674B1599523692**, **4102 casos**: 4074 passed, 13 failed preexistentes, 15 skipped, 34 subtests passed. Exit 1. O gate deve manter **GLOBAL_GREEN=false** e aceitar apenas as mesmas 13 falhas e causas.
- Ajustes de harness já existentes no Windows: teste ADR-020 PostgreSQL SSL (blob **b7e551df23c3f2ec60bcf95d1a1c3c9be9a68d50**) e leitura AST UTF-8 BOM (blob **0d24fd62d66277d0107af182e035059523d72dae**). Não alterar nem recriar sem investigação.

## 3. Fontes recuperadas e situação comprovada

- Histórico principal: **c9a17fd1** (36 ficheiros originais recuperados por hash Git); B01 original em **b45ef539**, atualizado B04 em **1af67fe4**.
- G1 histórico: commit **ee1007562836378e2addb50f9af0a09b609aef88**, blob **543f19b4b777ecaaa107d699dd13c002b378e8a2**. O G1 compartilhado da main (blob **9f7a5ddf144293fe3591989c784c8ec6d875cd07**) tem consumidores reais e permanece intacto.
- G1 privado: **app/services/enterprise_tax_consistency/enterprise_tax_consistency_engine.py** (classe EnterpriseTaxConsistencyEngine), AST funcional equivalente ao original, sem colisão com o compartilhado. Coexistência deliberada no REGISTRO_CANONICO.json, débito técnico dedicado e exceção estrita em check_duplicacao.py.
- 22 contratos G1 originais: blob **45a2080a8adead467aa4b00275e3a33616b0966c**, intactos; + 8 controles de coexistência. B03/B04/B01: 25 contratos originais, +6 de atomicidade.
- V3 documental em **a901c6ebbdebf210df8440bd55573655aec9b0d8**; V3.1 Windows Git-byte em **b968c7b017cc40ca0ff03f4df6d11469339c6ad0**. No Windows **39 testes da catraca V3.1 passaram**, sem necessidade de novo reparo SSL/BOM.
- Execução dirigida Windows dos seis ficheiros: **59 passed, 2 failed, 34 warnings, exit 1**, 3,74 s. Os dois RED de tests/test_solveris_b01_circuit.py são:
  - test_01_circuito_real_writer_i2_g12_g14_adr020_c3_c7: recebeu ABSTENCAO em vez de DOSSIER_INTERNO_NAO_PUBLICAVEL.
  - test_05_dependencia_c3_falha_fecha_circuito: PDF adulterado não foi inspecionado; exceção C3 esperada não ocorreu.
- Teste B01 original protegido, blob Git **eb961ee500de8a3dee76c0a6e4c4b4be577367e5**, preservado no manifesto de 36 fontes. **Não trocar PR por PA, NCM ou valores da fixture**.
- Diagnóstico publicado: **7c9a7f5dfc6b7ea18ca0a457c41e4f152ae19d05** — docs/B03_B04_STOP_B01_PR_VS_PILOTO_PA_20261118.md.

## 4. Descobertas causais que não se podem perder

1. O resolvedor **app/services/fiscal_utils.py** da main (Git blob **d625f12f68441f655cee06a6368b2ef7cfbf85b2**) define UF_PILOTO=PA e bloqueia PR com calculo_autorizado=False, motivo fora_de_escopo_normativo_piloto. É uma guarda real, **não um erro a remover**.
2. A fonte de c9a17fd1 usava um contrato nacional de resolução com UFS_VALIDAS incluindo PR (blob **7eb7599cc25e8db3804405aeedfe794e097f0145**). Recuperar G12/B01 sobre a main não recupera implicitamente esse contrato.
3. O G12 só produz SIMULACAO_CONDICIONAL_MVA quando o resolvedor autoriza; sem simulação G14 recusa candidato estrutural e B01 devolve ABSTENCAO **antes de chamar C3**. Isto explica por leitura a coincidência dos dois RED; o motivo interno exato G12/G14 ainda não foi capturado por instrumentação Windows.
4. Segundo delta independente: **buscar_mva** da main, em app/services/tabela_normativa_service.py (blob **371df51169a078aad4aa66040d4cf8952d0df1f0**), **não devolve registro_mva_id nem importado_por**. No histórico c9 (blob **df5bd75f102bb3a2cdd22e6f62fd0e07eb936408**) devolvia ambos. Sem registro_mva_id, o G12 não constrói proveniencia_l2_g12_v1, e o C6 retorna ABSTENCAO_SEM_IDENTIDADE_REGISTO_L2. Por isso trocar PR por PA seria INSUFICIENTE, além de proibido.
5. O objetivo nacional não permite fabricar autorização: qualquer replay sintético de PR deve manter autoridade_fiscal=False, credito_confirmado=False, checkout_autorizado=False, usavel_comercialmente=False.
6. G12 do candidato V3 é **fixado por hash**: blob **7b70bd28af292dc8028d572336b80f22bac0a945**. A catraca V3 tem PINNED + proveniência das 36 fontes e os testes test_enterprise_recovery_scope_v3_gate.py avaliam contra a árvore ATUAL.

## 5. Ensaio exploratório V4 — REPROVADO PELA CATRACA, NÃO PUBLICADO

No worktree Linux descartável **/tmp/solveris-g1-v3-3ZM46m**, que contém a V2/V3/V3.1 aplicada, foi preparado um experimento **não publicado**:

- Modificação apenas de G12 para reconhecer **exclusivamente** linha TabelaMVA de B01 sintético identificada por marcador, fonte sintética, SQLite em memória e unicidade temporal, com observação numérica via MotorFiscal e resolvedores existentes, sem transformar a autorização canónica PR em True.
- Leitura do ID real de TabelaMVA a partir da mesma linha sintética para suprir a ausência de registro_mva_id no retorno compartilhado. Novo teste experimental separado para positivos/negativos. Nenhum teste B01 ou G1 original alterado.
- G12 experimental local, blob **fac1a166941dcd94d497e86b98d818871c0a39d6**, compila, mas **não foi executado no Windows** e não tem verificação funcional GREEN. Nenhum patch de produto foi publicado no Git nem aplicado no Windows.
- Com esse G12 local, o comando de 39 testes de catraca passou a dar **4 falhas + 1 erro**, todas precedidas de **SCOPE_V3_PROVENANCE_CHANGED:app/services/enterprise_g12_st_item_reconciliation.py**. O gate V3 reprova qualquer alteração legítima do G12, antes de verificar a nova lógica.
- STOP publicado em **2c5ae9f1de4417b8e036b5ba6b6bcb7b6e83f7e0** — docs/B03_B04_STOP_V4_CATRACA_G12_20261118.md.

**Não transportar cegamente o experimento para o Windows.** O diretório /tmp é descartável; reconstruir pelo Git, não depender de memória nem de /tmp. A tentativa serve como hipótese de arquitetura, não como correção aceite.

## 6. Ratificação nova de Miguel e missão imediata

Miguel declarou expressamente em 18/11/2026: **registar handoff completo no Git e, em seguida, considerar ratificada a proposta de evolução V3→V4 test-only com commits separados**. A autorização cobre somente a evolução rastreável da catraca histórica, sem relaxar asserções nem modificar contratos B01/G1. Produto V4 permanece condicionado à validação de test-only.

Procedimento obrigatório:

1. **Primeiro commit test-only, separado de produto:** versionar a aceitação para que os testes históricos V3 comprovem uma árvore **V3 original e verificada por Git/hash**, enquanto os controles ativos V4 examinarão a árvore candidata. Preservar origem, node IDs e asserções substantivas; adicionar negativos contra snapshot falso, hash alterado, nova falha G1/B01 e falta de controle C3. Não utilizar mock que apenas devolva o hash esperado sem verificar bytes reais. Não suprimir testes antigos na suite global.
2. Verificar o commit test-only e os novos controles usando documentação/pacotes de teste no branch isolado. Um teste que passe por alteração de expectativas é falso GREEN e deve parar.
3. Preparar **em commit/patch distinto** o G12 privado V4 restrito ao confronto sintético, com provas de SQLite in-memory, marcador, origem nacional PR preservada, unicidade temporal, ID observável real e negações soberanas. Nenhuma alteração ao resolvedor, main, MEI ou motor compartilhados. Criar manifesto V4 com hashes/versionamento explícitos.
4. Executar novamente 25 B01/B03/B04 + 6 atomicidade + 22 G1 + 8 coexistência **e novos negativos V4** no Windows. Só se estes forem GREEN, iniciar suite global com JUnit e catraca diferencial sobre a baseline das 13 falhas históricas. GLOBAL_GREEN deve permanecer false mesmo na aprovação diferencial.
5. Ao concluir, escrever recibo e handoff no Git, apresentar resultado B03/B04 a Miguel. Só então retomar mapeamento B06 Fase 0, sem migração, SQL protegido, deploy ou merge não ratificados.

## 7. Invariantes e instruções de retomada

- Antes de ação: verificar branch recovery, HEAD documental, main de referência, hashes do B01, do G1 original e do módulo compartilhado, além de git status; manter mudanças preexistentes e nunca limpar worktrees do Miguel.
- A documentação Git pode avançar em commits próprios; não commitar produto ainda RED nem misturar test-only/produto no mesmo commit.
- Em caso de perda de contexto, reabrir primeiro este ficheiro, os dois STOPs de 18/11, B03_B04_EXECUCAO_G1_PRIVADO_V3_20261118.md e os manifestos V2/V3, mais AGENTS.md. Confirmar que **39/39 V3.1 só se aplica à candidata V3 original**, não à V4.
- Não repetir 45 minutos de suite global antes de ter GREEN dirigido. Evitar comandos PowerShell longos; executar no ambiente local do Miguel somente o que não puder ser verificado diretamente e pedir saídas compactas.
- Se a migração da catraca não puder manter os testes históricos genuínos e simultaneamente testar V4, **STOP CONTRACT_CONFLICT** e nova decisão de Miguel. Nunca contornar um gate congelado.

**Estado exato ao encerrar este handoff:** a missão não está concluída; 2 RED B01 + evolução de gate V3/V4 pendentes; documentação no Git; nenhuma correção V4 de produto publicada; main e produção preservadas.
