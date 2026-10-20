# SOLVERIS Enterprise — G1.13-C7 — dossiê investigativo interno por item

Corte: 20/10/2026; branch obrigatória `work/fiscal-assumptions-c0`; HEAD-base remoto/local obrigatório `7f988cde6242b6b6d4a3cc0bbc15c69fdd7dedeb`.

## Objetivo comercial sem exagero

Consolidar resultados já calculados nas pontes C3/C4/C5/C6 para produzir **uma unidade estruturada de dossiê por item de NF-e**, com duas diferenças monetárias observadas entre XML e G1.2, MVA documental candidata e realmente usada, proveniência do registo L2 e lista explícita de bloqueios de avaliação tributária. Nenhum motor é chamado, nenhuma base de dados é aberta e o módulo não produz valores pagos ou recuperáveis. Um resultado sem autoridade não é oferta comercial pronta.

## Achados verificáveis no repositório em 7f988cde

1. C3 coteja um PDF oficial e a linha de henna (CEST 20.001.00, NCM 1211.90.90), mas para o piloto temporal só observou 31/03/2026 e 01/04/2026. As datas seguintes exigem nova verificação; não se generaliza vigência aberta.
2. C4 coteja item, sujeito documental e pares numéricos `BASE_ST`/`ICMS_ST` provenientes do G1.2/G1. Não prova incidência do tributo.
3. C5 expõe MVA, alíquota e valores usados pelo motor; estas não são necessariamente as alíquotas juridicamente aplicáveis.
4. C6 expõe `TabelaMVA.id` e rastreia fonte/vigência, mas `TabelaMVA` não contém CEST nem FK para `RuleVersion` e `buscar_mva()` consulta por UF/NCM/data, não CEST.
5. A G1.13-C1 tem limite interno de 500 páginas de PDF; o consolidado oficial da SEFA/PR que alimentou a C3 tem 587 páginas. Logo, um vínculo C1/C3 baseado no **mesmo PDF consolidado** não pode ser afirmado como já executável, sem intervenção própria e testes. O PDF modificador de 29 páginas é uma fonte distinta e os hashes não podem ser substituídos um pelo outro.
6. A G1.13-C1 recebe uma `RuleVersion` com parâmetros declarados, incluindo alíquota, mas a relação semântica do texto oficial com a fórmula, a alíquota e a operação não é automaticamente demonstrada.

## C7: contrato e condições

`tools/enterprise_g113_c7_diagnostic_dossier.py`, função `preparar_dossie_investigativo_g113_c7`, recebe **somente** resultados upstream de C3, C4, C5 e C6 (obrigatórios) e resultado C1 (opcional). Verifica os esquemas, escopo de item, identificador de documento, SHA do XML, fonte PDF, hash do excerto, NCM, CEST, UF, data, versões, MVA, alíquota, registro L2 e cada par G1 de diferenças numéricas. Divergências estruturais geram STOP. O relatório não recalcua imposto nem tenta recuperar crédito; apenas concilia os números que os módulos upstream devolveram. Um conjunto de dicts arbitrários **não comprova** execução de motores, autenticação da NF-e ou consulta da BD: cabe exclusivamente ao orquestrador executar e preservar o encadeamento das chamadas originais.

Se C1 for fornecida, exige igualdade literal de SHA PDF e SHA excerto, alíquota e MVA, identidade de documento e flags de confiança negativas. Ainda assim **não declara uma FK L2↔RuleVersion**. A ausência de C1 não é inventada como prova. G16/G18/ADR-020 devem ser tratados nos seus contratos originais antes de fornecer qualquer C1 autêntica; a C7 não executa nem substitui esses contratos.

Saída: `DOSSIER_INTERNO_NAO_PUBLICAVEL`, duas diferenças monetárias `motor-menos-XML`, `alerta_investigativo`, e uma lista de lacunas para decisão fiscal: CEST na consulta L2; unicidade; relação ADR-020; vigência legal, exceções e benefícios; alíquota; ICMS próprio independente; origem externa/SEFAZ e posse; EFD e pagamentos; alterações normativas; revisão profissional. Todas as flags de autoridade, crédito e checkout permanecem `False`. Divergências de percentuais/valores são **alertas para investigação**, não sobrepagamento comprovado.

## Gates, escopo e continuidade

- Acrescentam-se só 3 ficheiros novos: módulo, 25 testes sintéticos, documento. Nenhum ficheiro existente modificado.
- Executor no ZIP, fora do Git, verifica SHA do ZIP e dos membros, HEAD remoto/local exato, branch, ausência de modificações tracked e índice limpo; instalações pré-existentes só são aceites se hashes idênticos. Verifica RED se ficheiros ainda ausentes, 25 GREEN sintéticos e hashes/escopo dos novos ficheiros. Sem commit/push/deploy/DB/MEI/pagamentos.
- O próximo marco **não** é criar outro adapter sem fim: é testar um caso E2E de âmbito explicitamente delimitado, com documentos de empresa autorizados e revisão especializada, ligando a execução original I2/G13/G14/G12/G1 à verificação real da norma, da operação e dos dados de recolhimento. Não há esse caso nesta C7.
- A primeira venda deve ser proposta como **serviço de investigação assistida e revisão especializada** só quando o fluxo real e a entrega forem demonstrados, não como crédito recuperado ou autossuficiência jurídica.
