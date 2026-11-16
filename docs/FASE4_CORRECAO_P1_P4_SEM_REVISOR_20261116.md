# SOLVERIS — Fase 4 — Correção a P1-P4 (remoção da dependência de revisor; esclarecimento da assinatura)

**Data:** 16/11/2026
**Corrige:** docs/FASE4_RATIFICACAO_PROMOCAO_SOBERANA_P1_P4_20261116.md
**Ver também:** docs/SOLVERIS_PRINCIPIO_SOBERANIA_SEM_TERCEIROS.md

## Correção ratificada por Miguel

A proposta original (secção 3, grupo 3 de evidências) exigia `RuleReviewRecord` com "revisor habilitado e independente do preparador" antes do pedido de promoção. Isto introduzia dependência de um terceiro humano, incompatível com a natureza soberana do SOLVERIS — corrigido:

- **Revisão funde-se no ato de ratificação de Miguel.** Ele verifica a evidência diretamente, ou delega a verificação a um mecanismo técnico automatizado (validação de hash, estrutura, coerência entre CEST/remetente/datas) — nunca a uma pessoa terceira. Não há papel de "revisor" separado no fluxo.
- **Assinatura digital mantém-se exigida (P2), mas esclarecida:** não depende de certificado de autoridade certificadora externa. Usa-se uma chave própria de Miguel (gerada localmente, GPG ou equivalente, sob o seu controlo exclusivo).

## Estado

Correção de arquitetura ratificada nesta data. P1, P3, P4 permanecem como ratificados em 16/11. P2 fica esclarecido conforme acima. P5 (dependência 0020/0024) já resolvido em D2 final. Nenhum código, base de dados ou migração foi criado ou alterado.
