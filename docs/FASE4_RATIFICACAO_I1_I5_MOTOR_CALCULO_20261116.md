# SOLVERIS — Fase 4 — Ratificação I1-I5 (integração da autoridade promovida no motor de cálculo)

**Data:** 16/11/2026
**Ratificado por:** Miguel
**Documento de referência:** proposta do GPT, 16/11/2026 (integração em prever_impacto_st, não em selecionar_norma_por_jurisdicao)

## Correção de premissa aceite

`motor_predicao_tributaria.py::prever_impacto_st` chama `buscar_mva` diretamente, nunca passa por `selecionar_norma_por_jurisdicao`. O ponto de integração é na fronteira de `prever_impacto_st`, entre a recolha dos dados do item e a decisão `if uf:` atual.

## Ratificado

- **I1:** inserir a consulta soberana antes do ramo legado, exclusivamente para o âmbito comprovado (PA/22021000/CEST 0301001/distribuidor-atacadista). Nunca depois do legado, nunca em paralelo com escolha automática entre fontes.
- **I2:** serviço novo, read-only, dedicado à verificação da autoridade promovida — consome o contrato P1-P4 já assinado/verificado, nunca reimplementa emissão, assinatura ou ratificação.
- **I3:** fluxo legado inalterado para tudo comprovadamente fora do escopo; abstenção (nunca TabelaMVA) para o escopo protegido sem promoção válida, ou para escopo indeterminado (CEST/remetente desconhecidos).
- **I4:** falha isolada por item — nunca fallback para TabelaMVA, nunca autorização implícita, nunca interrompe outros itens.
- **I5:** exigir prova independente de CEST, remetente e modalidade antes de qualquer integração com o cálculo.

## Estado dos três resultados fechados do consumidor

`AUTORIDADE_PROMOVIDA_VERIFICADA` / `ABSTENCAO_AUTORIDADE` / `FORA_DO_ESCOPO_COMPROVADO` — aprovados como os únicos três estados possíveis.

## Pendências técnicas identificadas, não ratificadas nem resolvidas

- Mecanismo de fencing/ordenação para impedir uso após revogação concorrente — fica para a implementação.
- Conversão de unidade MVA percentual (cotejo) vs decimal (motor) — contrato explícito a definir na implementação, nunca presumido.
- `ItemFiscal` não possui CEST nem categoria de remetente — ver item 9 do checklist consolidado.

## Estado

Decisão de arquitetura ratificada nesta data. Nenhum código, adaptador, TabelaMVA, base de dados ou repositório foi alterado.
