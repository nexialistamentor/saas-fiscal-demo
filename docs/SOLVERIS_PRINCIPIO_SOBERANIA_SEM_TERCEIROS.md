# SOLVERIS — Princípio permanente: soberania sem dependência de terceiros

**Data:** 16/11/2026
**Origem:** correção à Fase 4 / Proposta de Promoção Soberana (ratificada 14-16/11/2026), depois de Miguel identificar que a proposta original introduzia dependência de um revisor humano independente, incompatível com a natureza soberana do SOLVERIS.

## Regra permanente

Nenhuma arquitetura, processo ou missão no SOLVERIS (ou em qualquer outra plataforma soberana de Miguel) pode depender de um papel humano terceiro — revisor, aprovador intermédio, validador externo — entre a preparação de uma evidência e a ratificação soberana final. Miguel é a única autoridade ratificante. Qualquer verificação adicional antes da ratificação tem de ser técnica e automatizada (scripts, validação de hash, estrutura, coerência), nunca um papel humano externo.

Isto aplica-se mesmo quando um padrão de referência (compliance regulado, normas de auditoria, boas práticas de engenharia genéricas) sugere separação preparador/revisor/decisor. Esse padrão pressupõe uma organização hierárquica com terceiros disponíveis; o SOLVERIS não tem essa estrutura e não deve importá-la por reflexo, só porque é "boa prática" em outro contexto.

## Sobre assinatura digital em atos de ratificação interna

Exigir prova verificável de que foi Miguel quem ratificou (não só um campo de texto `actor='Miguel'`) continua válido e necessário. Mas isso não exige certificado de autoridade certificadora externa (ICP-Brasil ou equivalente) — essa exigência é só para documentos públicos externos (ex. decretos do Estado), onde a confiança tem de vir de fora. Para um ato de ratificação interna, basta uma chave própria de Miguel (par de chaves gerado localmente, GPG, ou mecanismo equivalente que só ele controla).

## Para quem ler isto depois

Antes de desenhar qualquer fluxo que inclua "aprovação", "revisão", "validação por terceiro" ou "segunda opinião" como etapa obrigatória antes da decisão de Miguel: parar e verificar se essa etapa pode ser substituída por verificação técnica automatizada. Se não houver forma técnica de substituir, a existência dessa dependência (e quem seria essa pessoa) é decisão soberana e tem de ser pedida explicitamente a Miguel antes de desenhar em cima dela — nunca assumida por analogia com outros projetos ou "boas práticas" genéricas.
