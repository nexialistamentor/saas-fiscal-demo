# SOLVERIS Enterprise — G1.13-C5: rastro de parâmetros efetivamente utilizados na G1.2

Corte 20/10/2026. Branch exclusiva `work/fiscal-assumptions-c0`; HEAD-base obrigatório `479dcec3f5b50c6a7755865de197033791df97ce`.

## Constatação confirmada em código conectado

`app/services/enterprise_g12_st_item_reconciliation.py` já calcula base e ICMS-ST com `MotorFiscal`, a partir de `resolver_aliquota_e_mva`, `buscar_mva` e `resolver_base_calculo_st`. Entretanto, a saída anterior de G1.2 por item não inclui a MVA e a alíquota *efetivamente utilizadas* nos cálculos. A G1.13-C4 apenas apresenta valores calculados e MVA documental C3 lado a lado, sem demonstrar a ponte causal.

O retorno de `buscar_mva()` possui MVA, alíquota, fonte, URL, vigência e nível de confiança **declarado pelo registo**, mas não expõe `TabelaMVA.id` nem ID de `RuleVersion` ADR-020. A palavra `oficial` dentro do cadastro não constitui validação externa da fonte nem prova de aplicabilidade jurídica.

## Alteração proposta — mínima e aditiva, sujeita a GREEN local

O executor acrescenta **uma única atribuição** `info['rastro_parametros_g12_v1']` no ramo em que a G1.2 já concluiu o cálculo, logo depois de determinar `base_motor` e `st_motor` e **antes** de assinalar `SIMULACAO_CONDICIONAL_MVA`. Não altera fórmula, resolutores, base de dados, esquemas ORM, checkout, rotas ou flags de autoridade. Itens não calculados **não ganham rastro artificial**. A rastreabilidade apresenta as frações exatas (`mva_fracao_utilizada`, `aliquota_fracao_utilizada`), os valores de entrada XML, resultado do motor, fonte e URL consultadas, com `identidade_registo_normativo_comprovada=False` e `regra_adr020_comprovada=False`.

O módulo puro `tools/enterprise_g113_c5_parameter_trace.py` confronta o rastro da G1.2 com a G1.13-C3 e os montantes já conciliados pela C4, exigindo a identidade do item e do documento e preservando a abstenção quando a execução G1.2 antiga não publicou rastro. Divergência de MVA produz **alerta numérico sem decisão fiscal**, não crédito recuperável.

## Fronteiras não ultrapassadas

- A instrumentação é observabilidade interna no exato ramo de cálculo; não é um recálculo fiscal legal independente, não prova valores pagos ou escrituração EFD e não autentica a SEFAZ.
- Mesmo quando a MVA utilizada coincide com a MVA documentada pela C3, **não** está comprovado que a versão documental seja juridicamente aplicável ao contribuinte, que todas as alterações posteriores tenham sido vistas, ou que o registo L2 corresponda ao mesmo ato ADR-020.
- `autoridade_fiscal`, `credito_confirmado`, `checkout_autorizado`, `usavel_comercialmente` permanecem `False`.
- A base de testes usa NF-e *sintética*, não documentos de clientes, e stubs sem conexão à BD. Se faltarem dependências no Python isolado, abortar: não instalar pacotes nem mexer na `.venv-release`.
- A alteração do serviço G1.2 é **tracked** e aditiva; os três ficheiros C5 são novos. GREEN valida estado staged no sentido de preparado para futura revisão, mas o executor não faz `git add`, commit, push ou deploy.

## Gates e continuidade

1. HEAD remoto/local e hash da G1.2 original presos à base ratificada; árvore tracked limpa (ou unicamente a alteração C5 idêntica, para retomar execução abortada). Índice Git vazio.
2. ZIP e hash de cada membro validados antes de qualquer escrita; RED por ausência do rastro G1.2 original; aplicação mínima no local correto, sem substituição de código anterior.
3. **32 testes sintéticos:** 26 cenários de identidade, fonte, parâmetros, confronto/abstenção e autoridade negada; 6 casos executam a **G1.2 real em memória** com dependências controladas e uma NF-e sintética, sem DB e sem rede.
4. Hashes, `git diff --check`, escopo exclusivo: `M app/services/enterprise_g12_st_item_reconciliation.py` e três novos ficheiros `??`.

Após GREEN: auditoria do diff aditivo e regressão controlada da G1.2, só depois commit/push exclusivo. Próxima frente comercial: preservar ID e versão reais da regra L2/ADR-020, cobrir vigência e exceções juridicamente verificadas, e executar um E2E com documentação autorizada de cliente, até dossiê auditável e revisão tributária. A C5 não autoriza vendas como recuperação de créditos.
