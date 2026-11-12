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

**Prova pendente:** execução da suíte relevante e da catraca anti-duplicação
no ambiente Windows com o `test.db` restaurado. Os commits remotos são
artefactos de entrega para essa verificação, não constituem PASS dos testes.
Até à saída verificável, não declarar o fecho técnico validado.

O teste positivo com autoridade normativa verificada não integra o critério
de fecho desta Fase 1: a portaria identificável não consta do dado real.
Nenhuma referência normativa foi presumida nem criada.
