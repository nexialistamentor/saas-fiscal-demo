# Fase 1 — seleção jurisdicional, prova PA

## Escopo implementado

Implementação isolada em `app/services/jurisdicao_normativa_service.py`.
Reutiliza `buscar_mva` e `resolver_aliquota_e_mva` sem modificar nenhum dos dois.
A UF é obtida da empresa e a consulta usa a chave exata UF, NCM e data de
referência. O retorno reaproveita `scope`, `domain`, `policy_version`,
`policy_hash` e `declared_material_applicability`. Os dois campos de
política permanecem nulos: a presença de uma linha na tabela MVA não constitui
política assinada nem autoridade normativa verificada.

O contrato jurisdicional usa `scope.jurisdiction = "BR-PA"`,
`scope.sphere = "estadual"`, `scope.territory.uf = "PA"`,
`scope.use = "icms_st_mva"`, `domain = "ICMS_ST_MVA"` e
`declared_material_applicability.kind = "vigencia_regra_cadastrada"`.
Nenhum novo schema de base de dados ou processo de governação foi criado.

## Dado PA efetivamente identificado

- UF `PA`, NCM `22021000`, registo `id=1`.
- MVA `40.0` (40%), alíquota interna `0.18` (18%).
- Vigência inicial `2024-01-01`, fim não indicado.
- `nivel_confianca_fonte="oficial"`, mas `fonte_legal=NULL` e `url_fonte=NULL`.
- Origem da restauração: `app/scripts/seed_mva.py`, existente no repositório.

## Decisão ratificada e comportamento

`fonte_legal` é obrigatória para que a autoridade normativa seja considerada
verificada. Para o registo PA, a resposta correta é
`REGRA_CADASTRADA_AUTORIDADE_NAO_COMPROVADA`, com
`regra_cadastrada=True`, `autoridade_normativa_verificada=False`,
`calculo_autorizado=False` e `norma_resolvida=None`, acompanhada do aviso
`cobertura normativa não comprovada`. Nenhum fallback se torna autoridade.
O resolvedor fiscal original permanece intacto.

## Validação

`tests/test_jurisdicao_normativa_fase1_pa.py` contém seis testes de leitura
SQLite, sem escrita no `test.db`. Verifica o registo PA, a diferença entre
cadastro e autoridade, o bloqueio no resolvedor já existente, o isolamento
jurisdicional, a vigência e a data explícita.

**Prova executada no Windows em 2026-11-12** (saída do operador,
`C:\dev\saas-fiscal-demo-a1`, `.venv-release`): `python -m pytest -q`
sobre `test_jurisdicao_normativa_fase1_pa.py`,
`test_enterprise_b03_item_reconciliation.py`,
`test_empresarial_normative_key.py` e
`test_l3_normative_resolution_invariants.py`:
**72 passed, 1 warning, 0 failed (5.55s)**.

Catraca executada no mesmo ambiente:
`python tools\check_duplicacao.py --repo C:\dev\saas-fiscal-demo-a1
--registro docs\REGISTRO_CANONICO.json`:
**OK: nenhuma duplicacao nao declarada encontrada (cobertura completa)**.
O aviso `SyntaxWarning` em `danfe_pdf_adapter.py` não reprovou a catraca.
O aviso `StarletteDeprecationWarning` também não reprovou a suíte.

**Fecho técnico desta Fase 1 no âmbito ratificado: GREEN** para seleção
jurisdicional com distinção cadastro/autoridade e proteção fail-closed.
Não foi apresentado hash do `test.db` antes/depois do conjunto de testes;
portanto, uma prova independente de identidade de bytes do banco não está
documentada nesta execução. Os seis testes próprios usam conexão read-only.
Nenhum merge ou deploy integra este fecho.

O teste positivo com autoridade normativa verificada não integra o critério
de fecho desta Fase 1: a portaria identificável não consta do dado real.
Nenhuma referência normativa foi presumida nem criada.
