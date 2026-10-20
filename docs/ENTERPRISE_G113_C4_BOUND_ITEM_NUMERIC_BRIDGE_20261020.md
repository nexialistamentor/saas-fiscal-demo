# SOLVERIS Enterprise G1.13-C4 — NF-e / G13 / G14 / C3 / G1.2 / G1

Corte: 20/10/2026. Branch de instalação `work/fiscal-assumptions-c0`, HEAD-base obrigatório `3a50fd0b7d0d5f3b57c6940c3addcfe4699d7112`. **Não tocar no MEI.**

## Objetivo comercial real

Avançar do texto normativo observado ao confronto monetário por item **sem inventar outro motor**. G1.2 já usa motores existentes e G1 devolve `comparacoes` por `BASE_ST` e `ICMS_ST`, com valores observados no XML e valores calculados internamente. G1.13-C3 conserva a MVA original extraída de PDF oficial dentro de janelas estritas. **G1.2 não expõe a MVA realmente selecionada para cada item**: não é possível demonstrar que o cálculo G1.2 deriva causalmente do valor C3, apenas emparelhar os resultados e isolar a pendência.

## Contrato proposto

Ficheiro `tools/enterprise_g113_c4_fiscal_item_bridge.py`, função `cotejar_item_evidencia_calculo_g113_c4`. Serviço **puro read-only**, sem base de dados, rede, pagamentos, persistência ou chamadas aos motores. Requer os bytes XML exatos e snapshots reais devolvidos pelos serviços originais G1.3, G1.4 e pela função C3; cabe ao orquestrador autorizado executar I2/G13 (mesma DB/identidade), G14 e C3 e passar os resultados sem substituí-los por objetos fabricados. Os objetos recebidos isoladamente não autenticam a origem, a posse nem a situação fiscal de um cliente. No novo módulo a identidade da data/UF/NCM/CEST/CFOP/CST/ICMS10, o hash XML, documento, empresa e relatório são rechecados contra os bytes, com parsing `defusedxml` e vedação a DTD/entidades.

A nova ponte lê os pares monetários **já produzidos pela G1**, exige base ST e ICMS-ST e coteja os valores XML com `vBCST` e `vICMSST` diretamente nos bytes. Recalcula somente **a diferença entre dois montantes já observados**, não a obrigação fiscal, a alíquota ou a base segundo outra fórmula. Se G1 ou G1.2 não produziram esses pares válidos, há abstenção sem quantificação.

Estados possíveis:

- `CONFRONTO_NUMERICO_E_MVA_CANDIDATA_SEM_PONTE_CAUSAL`: identidade e pares de G1 unidos; **NÃO comprova que G1.2 usou a MVA C3**.
- `ABSTENCAO_NORMATIVA_TEMPORAL`: janela C3 sem cobertura ou sobreposição.
- `ABSTENCAO_G12_SEM_SIMULACAO_ITEM`: cálculo por item não disponível.
- `ABSTENCAO_G1_SEM_PARES_NUMERICOS`: comparação G1 não disponível.
- `STOP` em contradições estruturais, identidade, hashes, flags de autorização forjadas ou montantes inconsistentes.

Todas as flags de crédito, autoridade fiscal, checkout, aptidão comercial e causalidade MVA→motor permanecem `False`. Nenhum resultado numérico C4 representa pagamento, recolhimento indevido ou crédito recuperável.

## Segurança e testes

- Testes: **32 casos sintéticos** de identidade, hash, XML com DTD, operação, escopo, MVA, abstenção, pares G1, divergências falsas, autorização indevida.
- Não há NF-e real de contribuinte nem leitura de DB neste pacote; não alegar E2E cliente.
- A cadeia G15–G18/G113-C1 e o serviço C3 são preservados, sem modificações; nenhuma rota integra C4 automaticamente.
- Requer `defusedxml` no Python de testes; se indisponível, STOP — não efetuar instalações automáticas.

## Próxima prova que altera realmente a prontidão comercial

Instrumentar, **depois de auditoria de contratos**, o motor G1.2/versão existente para devolver `mva_percentual_realmente_utilizada`, `fonte_legal`, `versao_regra`, parâmetros de base e alíquota, mais a identidade de `TabelaMVA`/registo normativo, mantendo a autoridade apenas quando a origem exata for comprovada. A partir daí comparar a MVA efetivamente usada com a linha oficial C3, cobrir alterações e exceções, construir recálculo fiscal independente e só então quantificar uma divergência com fundamento. Ainda são necessários documentos de cliente, EFD/recolhimentos e revisão fiscal profissional para falar de créditos.
