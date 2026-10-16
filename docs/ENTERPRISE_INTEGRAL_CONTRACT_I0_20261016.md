# SOLVERIS Enterprise — I0: contrato de censo e projeção integral (16/10/2026)

**Ponto de partida imutável:** `work/fiscal-assumptions-c0` / `15957fa559b035e4c9d1ab55506eaa25cfd09515`.

**Objetivo:** criar uma matriz executável de cobertura integral a partir do `resultado_empresarial_service.compor_resultado_empresarial` existente. As capacidades PIS e Cofins são entradas separadas (também os respectivos créditos), nunca uma omissão conjunta. Os motores permanecem intocados.

## Prova e limitações

- A fonte de `resultados_engines` é `insights_engine.executar_engines`; `pis_cofins` é calculado por `calcular_pis_cofins` e persiste no resultado empresarial. A projeção NÃO executa motores nem os reconstrói.
- Campos do motor são devolvidos **somente como `resultado_bruto_nao_validado` de uso interno**; não correspondem a crédito jurídico, apuração conclusiva, valor comercial ou conformidade.
- PIS/Cofins preservam os valores observados mas sinalizam `PIS_COFINS_BASE_ICMS_PROPRIO_NAO_VERIFICADA_ST_NAO_E_ICMS_PROPRIO`, devido à inferência atualmente presente no InsightEngine. Essa correção causal pertence à I1 e não pode ser substituída por ICMS=0 assumido.
- Cada capacidade tem exatamente um estado no censo I0: `informativo_sem_prova`, `nao_apurado`, `falha_motor` ou `nao_integrado_ao_snapshot`. `nao_integrado_ao_snapshot` significa que o produtor existe no código ou está planeado, sem prova de execução nesse caso. Não confundir com inexistência de implementação.
- O contrato aceita apenas payload empresarial já autenticado e verificado pelo chamador; **não verifica** fingerprint, proveniência, documentos ou titularidade. Não criar endpoint público ou consumir diretamente em UI/PDF/pagamento.
- `checkout_autorizado = false`, `diagnostico_empresarial_completo = false` e `comprovacao_normativa = false` por definição I0, inclusive nos casos sintéticos positivos.
- Registros de motores não catalogados são sinalizados como `engines_nao_catalogadas`, sem perda silenciosa de inventário.

## Cadeia comprovada por leitura e ensaio de contrato

`InsightEngine` → `resultados_engines` e outros campos → `compor_resultado_empresarial` existente → `projetar_diagnostico_integral_i0` **novo**, determinístico e sem efeitos laterais. O teste inclui simultaneamente PIS/Cofins, crédito PIS/Cofins, IRPJ adicional, CSLL, risco, oportunidades e créditos ST e examina ausência/falha de entradas. Os valores do teste são exclusivamente sintéticos. **Não** testa detecção automática de tributo, geração PDF, autoridade normativa ou aquisição.

## Fronteira I0/I1/I2

A I0 apenas inventaria e preserva outputs originais na camada interna; não corrige o contexto fiscal, não inventa item documental, não grava outro resultado e não habilita venda. Na I1: substituir inferência ST→ICMS próprio por read-model comprovado ou indisponibilidade e vincular empresa/documento/período/UF. Na I2: projetar states e inputs validados por motor para snapshot versionado, preservando a matriz inteira. A publicação PDF/API/UI virá depois de homologar essas ligações, **sem alterar o renderizador compartilhado com `tax.report` no I0**.

## Limites de alteração e de execução

**Somente três ficheiros novos:** `app/services/enterprise_integral_projection.py`, `tests/test_enterprise_integral_projection_contract.py`, este documento. Nenhum arquivo existente é alterado. Nenhuma migration, banco, `MEI`, Vercel, Railway, Mercado Pago, grant, checkout, commit ou push automático. A execução é local no checkout Enterprise, condicionada a branch/HEAD/remote/status, RED causal confirmado, GREEN e regressão delimitada.

**STOP:** divergência de baseline, código em conflito, venv inexistente, RED não causal, falha de GREEN/regressão ou tentativa de expansão de escopo. O reporte exato deve preceder commit/push.
