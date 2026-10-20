# SOLVERIS Enterprise — G1.13-C3 — seleção temporal de MVA observada

Corte: 20/10/2026. Base Git exigida: branch `work/fiscal-assumptions-c0`, HEAD `ee7cb91f75a990db22604a2db86424959a09fcb2`.

## Entrada documental comprovada pelo utilizador (G1.13-C2T-R2)

- Resolução SEFA/PR nº 1245/2025, modificadora da nº 571/2019: PDF `https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101202501245.pdf`, SHA-256 `e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832`. Excerto corrigido (página 1) `480c12a491af5cf40abcd8a6f72dbfb7a4ee7b682d1284ac76dc41dd2fb99959`; MVA original de henna, CEST 20.001.00, NCM 1211.90.90: `46,78%`, efeitos declarados desde `2026-04-01`.
- PDF consolidado oficial `https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101201900571.pdf`, 587 páginas, SHA-256 `af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d`.
- Página física 55 (índice 54): texto SHA-256 `49de93b123f058fb3b1062c00eb1ffdeaf2fd8e97aaf93c8fbdfcd307dc91bf0`, posição `152`, excerto corrigido SHA-256 `bae481ebbd19b978787496d2e3739d4d042828b4a3132c1c571fa45693e4053d`, representação extraída `46, 78` → Decimal `46.78`.
- Página física 86 (índice 85): texto SHA-256 `e4d3c4df93ea178040f2c54e0434a0021d4e41ee55a91b5750b48388fc53228b`, posição `130`, excerto corrigido SHA-256 `c7451d943547e212701021f85de2b24a2b07de387795de9f5e91a6f84182cf11`, representação extraída `41, 42` → Decimal `41.42`.
- Os resultados R2 comprovaram a correspondência **documental** das duas linhas e um diferencial de 5,36 pontos percentuais; não comprovaram consulta exaustiva de alterações posteriores, situação tributária de contribuinte, valor pago, escrituração ou crédito.

## Contrato C3

Serviço puro `tools/enterprise_g113_temporal_mva_evidence.py`: aceita um corpus finito de PDFs já adquiridos pelo chamador (`dict[URL, bytes]`), identidade declarada de item (UF/NCM/CEST), data de operação declarada e versões com provas textuais imutáveis. Recomputa SHA dos bytes, SHA do texto extraído da página, posição CEST, NCM, descrição, MVA com normalização apenas do separador decimal, número da linha seguinte, e hash do excerto **não normalizado**. O texto bruto permanece intacto.

Cada versão tem separadamente uma **vigência declarada** e uma **janela documental de observação** inclusiva. Uma versão só pode ser selecionada se a data estiver dentro de ambas. Sobreposições e ausência de janela retornam `ABSTENCAO_TEMPORAL`. Contratos malformados, hashes divergentes, texto alterado e percentuais ambíguos provocam STOP. O serviço **não** declara como demonstrados todos os dias de uma vigência aberta apenas porque uma fonte declara data inicial sem data final.

### Piloto real deliberadamente limitado

- Exemplo da redação anterior: **somente 31/03/2026** está dentro da janela observada neste teste, com o candidato `41.42`.
- Exemplo da redação posterior: **somente 01/04/2026** está dentro da janela observada neste teste, com o candidato `46.78`.
- **02/04/2026 e datas posteriores: abstenção** até que a janela seja comprovadamente estendida, com revisão de alterações e cobertura normativa. O facto de existir um ato com efeitos desde 01/04 não é prova independente de que nenhuma alteração posterior ocorreu.

A função não importa as camadas `app` nem se integra automaticamente na G1.12 ou G1.13-C1. As entradas de item e data são declarações de chamador, não autenticação NF-e. O piloto não comprova que a mercadoria de determinado emitente é henna em embalagem até 200g, qual a operação sujeita a ST, a alíquota interna, MVA ajustada, exceções, benefícios, EFD, pagamentos, ou crédito. **NUNCA autorizar cálculo definitivo, checkout ou recuperação de créditos a partir desta etapa.**

## Gates

Um `gate.py` incluído no ZIP é executor auxiliar **fora do Git**: confere HEAD remoto/local, árvore tracked e index intactos, hashes do ZIP, entradas, e ficheiros; observa RED de importação quando ausente, instala só três novos ficheiros se os hashes corresponderem, executa 30 testes sintéticos GREEN, então adquire por HTTPS apenas o PDF consolidado oficial e valida as páginas 55/86 e a seleção nos dois dias de corte. Nenhum commit, push, deploy, DB, MEI ou alteração aos motores anteriores. Os ficheiros ficam **untracked** até revisão/autorização da integração.

Próximo passo comercial relevante: alargar as janelas temporais somente depois de verificar completude normativa; vincular a seleção ao I2/G14 e reconstruir base/ICMS próprio/alíquota/frete/descontos por operação, documentar limitações e impacto económico sem promover simulações a crédito.
