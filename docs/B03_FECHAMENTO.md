# B03 — Fechamento

## Estado

B03 (comparação monetária: XML vs valores declarados vs cálculo
independente) está fechado e commitado em `b03/inventario-antidup-20261110`,
commits `381a4acb`..`c75068c6`.

## O que está provado

- Adaptador fino `confrontar_documento_b03`/`confrontar_xml_b03`
  (`app/services/enterprise_b03_item_reconciliation.py`), ligando
  `resolver_aliquota_e_mva`, `MotorFiscal`, `TaxConsistencyEngine` e
  `xml_service.ler_xml_unico` — nenhum reimplementado.
- 7 testes automatizados (`tests/test_enterprise_b03_item_reconciliation.py`),
  cobrindo: sem divergência, divergência encontrada, sem autoridade
  normativa, campos essenciais ausentes (fail-closed), item sem
  `valor_produto` (fail-closed), parsing XML com erro (fail-closed),
  ponta-a-ponta via `confrontar_xml_b03`.
- Validação ponta-a-ponta contra **dado real da BD** (não só mocks):
  regra UF=PA, NCM=22021000 — `SEM_DIVERGENCIA` e `DIVERGENCIA_ENCONTRADA`
  corretos, valores (`base_st=435.00`, `icms_st=25.65`) conferidos
  manualmente.
- Catraca anti-duplicação (`tools/check_duplicacao.py` + pre-commit hook
  no git-common-dir) instalada e validada a bloquear duplicação real.

## RESSALVA HONESTA — cobertura real, não a presumida no plano inicial

**B03 está fechado para UF=PA, NCM=22021000 — não para PR**, como o plano
original presumia (`listar_base_normativa` devolveu só 1 regra na BD no
momento desta sessão, e é de PA, não PR). Não há ainda prova ponta-a-ponta
contra uma regra de PR, nem contra nenhuma outra UF.

**Cobertura nacional/interestadual continua pendente** — já rastreada
separadamente em `cobertura-nacional-jurisdicoes` — B03 não resolve isso,
só opera corretamente sobre a regra que a BD já tiver, qualquer que seja a
UF.

**Dois bugs de produção reais foram corrigidos nesta sessão**, ambos só
descobertos por testar contra dado real:
1. Crash (`AttributeError`) quando faltam `chave_nfe`/`uf_operacao`/
   `data_operacao` — corrigido para `NAO_AVALIADO` fail-closed.
2. Erro de 100× em todo cálculo monetário (MVA/alíquota em fração vs
   percentual) — corrigido com conversão explícita antes de chamar
   `MotorFiscal`.

Isto significa que **nenhum código de B03 deve ser considerado confiável
em produção antes de rodar os testes automatizados** (`pytest
tests/test_enterprise_b03_item_reconciliation.py`) e, idealmente, antes de
validar contra pelo menos mais uma UF real (quando a BD tiver mais regras
cadastradas).

## O que falta, explicitamente fora de B03

- `tools/schema_census/` (achado no branch `wip-local-*-3`, nunca
  incorporado em B03) — candidato à "catraca de conformidade" pendente em
  `schema-drift-incident`, precisa de revisão própria.
- A reversão de bloqueio de registo MEI em `auth_router.py` (mesmo branch)
  — mudança de regra de negócio em autenticação, fora de escopo de B03,
  não incorporada.
- Cobertura nacional de jurisdições — pendência já tracked, não resolvida
  por B03.

## Próximo passo recomendado (fora desta sessão)

Push do branch (`git push`) e abertura de PR para revisão humana antes de
merge em qualquer branch principal — nenhum merge foi feito nesta sessão,
tudo fica em `b03/inventario-antidup-20261110` até ratificação.
