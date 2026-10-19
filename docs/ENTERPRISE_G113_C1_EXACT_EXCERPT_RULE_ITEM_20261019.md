# SOLVERIS Enterprise G1.13-C1 — PDF → excerto exato → regra ADR-020 → item fiscal

Corte: 19/10/2026. Branch obrigatória: `work/fiscal-assumptions-c0`, HEAD ratificado `3069be1f05eb3566f999e79247f1dacd2bf0566c`.

## Constatação C0

Os serviços G1.2/G1.4 permitem confronto condicional por item. G1.5/G1.10 cotejam o artefacto PDF, G1.6 coteja as identidades internas de `ExtractionResult` e `RuleVersion`, G1.7 a janela administrativa limitada e G1.8 o hash externo PDF. G1.11/G1.12 observaram assinatura PDF e caminho de certificação real; **não provaram** revogação histórica, instante confiável nem interpretação de uma disposição fiscal.

O nome legado de `sha256_texto_normativo_declarado` na G1.4 indica **o hash do artefacto PDF** no contrato G1.5. Não o reutilizar como SHA do excerto: G1.13 emprega campos distintos para `pdf_sha256`, `pagina_texto_sha256`, `excerto_sha256` e `inicio_caracter`.

## G1.13-C1 — contrato opt-in, totalmente read-only

Módulo independente em `tools/enterprise_g113_exact_normative_excerpt.py`; não importa `app.database`, não executa SQL, não liga à rede, não escreve ficheiros, não chama checkout, não modifica motores ou modelos.

A função `cotejar_excerto_normativo_g113` recebe bytes reais do PDF (máximo 16 MiB), SHA-256 do documento, índice de item, item já produzido pela G1.4, snapshots G1.6 e G1.8, e **objetos efetivamente lidos** da base pelo chamador autorizado (`ExtractionResult` e `RuleVersion`). Os objetos recebidos por argumento não são uma prova independente de persistência ou integridade do próprio banco. Cabe ao orquestrador lê-los por `db.get` do mesmo snapshot usado pelos gates anteriores, sem misturar sujeitos ou checkpoints.

Confrontos efetivos:

1. Bytes e SHA-256 PDF com o hash observado na G1.8, identidade XML/documento/empresa/relatório e item exato; pressupõe que as G1.4/G1.6/G1.8 foram efetivamente chamadas e passaram seus gates.
2. Identidade e hashes de registos `ExtractionResult`/`RuleVersion`, ligados à regra interna G1.6; rejeita divergências e alertas de alteração/revogação conhecidos.
3. Páginas e texto extraível pelo `pypdf`, sem OCR. Exige que o mesmo `g113_v1` conste dos dois campos JSON `evidence`, com página 1-based, hash do texto extraído, excerto exato, SHA do excerto, offset e dispositivo declarado. Exige ocorrência **única** na página observada.
4. Parâmetros estruturados `g113_v1` iguais em `ExtractionResult.structured_content` e `RuleVersion.structured_content`, associados ao item NCM/CEST/CFOP/CST/UF/regime, vigência **declarada** e fórmula candidata `IVA-ST`. MVA maior que 100% não é negada por um limite artificial; alíquota não pode ultrapassar 100%.

Estes novos campos `g113_v1` são um **contrato proposto, não uma afirmação de que registos históricos os contêm**. Dados ausentes → STOP/abstenção; não preencher ou mutar ORM automaticamente, nem criar fonte normativa inventada.

## Limites inalterados

- **Localização física e identidade declarada de regra NÃO demonstram pertinência semântica**, validade legal, texto original fiel (normalização PDF), interpretação de exceções ou eficácia dos percentuais. `prova_de_relacao_semantica_entre_excerto_e_parametros=False` deliberadamente.
- Exigir a mesma referência em dois registos internos NÃO é auditoria externa independente, nem prova de que uma afirmação substantiva provém da norma.
- `hash_pdf_distinto_hash_excerto=True` significa identidades criptográficas **conceitualmente separadas**, não uma prova de diferença numérica obrigatória em todos os casos.
- `formula_juridicamente_autorizada`, `fonte_primaria_autenticada`, `vigencia_juridica_comprovada`, `credito_confirmado`, `checkout_autorizado` e restantes flags continuam **False**.
- Não afirma que o PDF piloto IOEPA de 23/02/2026 contenha uma disposição aplicável a MVA/ST; só aceitar um excerto real identificado explicitamente e uma relação fiscal justificada em gate posterior.
- O G1.13-C1 ainda não é chamado automaticamente pela G1.8 nem por produto/endpoint. Os testes são sintéticos e não substituem E2E com linhas ADR-020 reais.

## Gates de instalação

R1: instalar somente `tests/test_enterprise_g113_exact_normative_excerpt.py` e observar RED pela ausência do módulo. R2: instalar só serviço e documento após hashes e executar 26 testes no `.venv-pyhanko` isolado (`pypdf` obrigatório), sem alterações na `.venv-release`. Só depois de GREEN serão revistos diff/estado e eventual commit/push exclusivo. Nunca tocar em MEI, DB, SEFAZ, pagamentos ou deploy.

A próxima etapa operacional G1.13-C2 deverá identificar **um texto normativo real e relevante ao item** e produzir evidência de pertinência semântica verificável, sem converter parâmetros declarados em tributação autorizada. Também fica aberto o âmbito PIS/COFINS, IRPJ/CSLL, EFD e ICMS próprio independente, conforme o objetivo integral Enterprise.
