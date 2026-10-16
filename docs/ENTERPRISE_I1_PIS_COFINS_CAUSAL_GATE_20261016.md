# SOLVERIS Enterprise — I1: quarentena causal PIS/Cofins

**Baseline exigida**: `work/fiscal-assumptions-c0` / `2134bc30a7251cec39dc32e928973b27bf1f20a9`.

## Objetivo
A auditoria confirmou que `InsightEngine` agrega `NotaFiscalItem.valor_st` em `icms_pago`/`icms_devido`, e `executar_engines` pode transportar esses campos como `icms` para `calcular_pis_cofins`. **ST não comprova ICMS próprio** e a diferença não constitui crédito.

## Implementação isolada I1
- Novo `enterprise_pis_cofins_authority_i1.py`, **sem alterar o motor legado**, e sem substituir ICMS desconhecido por zero.
- Wrapper concreto de I0: `projetar_diagnostico_integral_i1`; mantém as 52 capacidades e coloca PIS, Cofins e respetivos créditos em quarentena, removendo valores legados da saída **I1**.
- Sem evidência documental vinculada: `nao_apurado`, causa explícita; não chama cálculo.
- Com envelope sintético de documentos coerente (empresa, competência, documento ID, SHA256 declarado, papel, modalidade ICMS próprio, valores monetários): invoca o **motor existente** apenas para simulação condicional, **sem crédito apurado, norma, autenticidade comprovada ou autorização comercial**.
- Com ST, hashes duplicados, mismatch de empresa/período, ausência de ICMS próprio ou falha de engine: STOP lógico, sem números comerciais.

## Limitações inegociáveis
O envelope documental é **declarado**: o adaptador não abre NF-e, não autentica bytes/SEFAZ, não lê EFD, nem obtém normas oficiais ou recibos de pagamento. Mesmo o cenário positivo apenas produz **simulação não publicável**. Não integra ainda automaticamente a rota produtiva, os relatórios adquiridos nem o PDF. Não prova correção da execução legada que continua a existir; é uma nova fronteira Enterprise para preparar o desvio controlado futuro. **Não afirmar a I1 como cadeia ponta a ponta concluída.**

## Segurança
Sem BD real, MEI, alteração de contratos históricos, migrations, pagamentos, catálogo, grants, checkout, scheduler, Vercel ou Railway. `checkout_autorizado=False` sempre. Não se altera `app/services/insights_engine.py`, nem `tax_engines/pis_cofins_engine.py` nesta etapa.

## Homologação
RED causal (módulo ausente) -> GREEN (16 testes causais) -> I0 (7 testes) + regressões PDF/checkout, sem escrever fora dos dois novos ficheiros. Conferir `git status` e HEAD; ratificar diff antes do commit.

## Próxima intervenção automática após I1 validada
I2: ligar esta fronteira à persistência e proveniência **autenticada** do caso Enterprise, mediante teste causal dos documentos/itens, competência, fontes oficiais e estados normativos, sem exposição PDF, cobrança ou alterações MEI enquanto faltarem as provas. Não continuar a aceitar valores PIS/Cofins do contexto agregado de ST como material comercial.
