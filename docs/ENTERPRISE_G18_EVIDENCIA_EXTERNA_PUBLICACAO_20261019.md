# SOLVERIS Enterprise G1.8 — cotejo de evidência externa (sem autoridade fiscal)

**Base obrigatória:** `work/fiscal-assumptions-c0`, HEAD `5fabb5dc87d15551a76d4baf36c66ed823079547` (G1.7-R1). 19/10/2026.

## Intervenção limitada

São **três ficheiros novos**, sem alteração de modelos, migrations, G1.7, MEI, pagamento, checkout ou deploy. A camada `app/services/enterprise_g18_external_publication.py` fornece:

1. `observar_pdf_publicacao_g18`: recalcula o SHA-256 de **bytes reais fornecidos**, valida o cabeçalho PDF e devolve um testemunho observacional isolado. Suporta o piloto real IOEPA de 2.764.152 bytes sem introduzir binários reais no Git ou na BD. **Não prova que o PDF veio da autoridade indicada no URL**.
2. `cotejar_evidencia_externa_publicacao_g18`: chama **a função real da G1.7** na mesma sessão/bytes/contexto e apenas depois compara, por índice de item, o PDF fornecido pelo chamador com `NormativeArtifact` e `ArtifactReference` da ADR-020, vinculados pelo índice e identificadores de `referencias_cobertura` da G1.7. Confere o SHA-256 real, byte size, URL exata, IDs e `record_hash`; quando os bytes são residentes confere-os diretamente. **Nunca escreve**, não busca ficheiros ou URLs, não produz `TRUE` em nenhuma autoridade.

O PDF tem teto independente de 16 MiB e limite de 32 evidências por cotejo. O XML mantém o teto preexistente de 2 MiB. Um `immutable_location` externo permite cotejar o **hash declarado do registo** contra os bytes expressamente fornecidos ao adaptador, mas não constitui leitura, fixação ou revalidação independente dessa localização. Por isso `custodia_externa_revalidada=False` mesmo com hash coincidente.

A função independente de observação permite medir o PDF real imediatamente, sem qualquer escrita ADR-020. Já a ligação positiva G1.8 a uma regra **exige que a G1.7 tenha aceite aquela regra e que as linhas ADR-020 persistidas correspondam exatamente aos mesmos bytes/hash/URL**. A amostra IOEPA 23/02/2026 não é presumida ligada a uma regra nem carregada em `NormativeArtifact`. **A G1.5 ainda impõe limite de 2 MiB em `immutable_bytes` e não aceita `immutable_location`: até existir um gate específico para armazenamento CAS/revalidação, o PDF piloto de 2,76 MB não pode obter um cotejo integral G1.5/G1.7/G1.8 em produção.** Não contornar nem relaxar silenciosamente essa restrição.

## Piloto real externo T1 — observações e lacunas

Publicação: PDF IOEPA, `https://www.ioepa.com.br/arquivos/2026/2026.02.23.DOE.pdf`, 2.764.152 bytes, SHA-256 `a23209626b9d7ca753aba82335c410ea4b636950579d39a90476b4c2d4de0e27`. Os bytes e relatórios continuam **fora do Git** nos Downloads, com proveniência técnica auditada.

- `/adbe.pkcs7.sha1`; ByteRange estruturalmente íntegro e sem bytes acrescentados após a revisão assinada; SHA-1 encapsulado coincidente. Risco de colisão SHA-1 não eliminado.
- CMS RSA PKCS #1 v1.5 verificado com certificado de SHA-256 `1a3176ec0d40e464092387d839489ecd29b5fb6462506d14c3e31fd8d2964e36`. `VALID_CRYPTO_ONLY`, nunca `trusted`.
- Cadeia verificada: Imprensa Oficial → SERPRORFBv5 (`b1e93a02...`) → RFBv4 (`2c7a8ad7...`) → Raiz v5 (`caa53fc6...`). Raiz obtida do SERPRO e ITI coincidiu em DER. Validade nominal da cadeia cobriu 23/02/2026.
- LCR das três autoridades emissoras obtidas e assinaturas verificadas. Os certificados consultados não constavam dos **snapshots recolhidos** (as LCR consultadas são de 2026-08/10). Não prova estado histórico de revogação em 23/02/2026, nem abrangência de listas delta/cobertura completa.
- Sem carimbo RFC 3161 incorporado ou `signing_time` CMS; `/M` é declaração de data, não testemunho temporal confiável.
- Fonte/publicador oficialmente reconhecidos por nome no certificado, mas o **direito jurídico de publicação do ato específico e o conteúdo normativo exato** não foram autenticados por esta prova criptográfica isolada.

## Estados obrigatoriamente bloqueados

`fonte_primaria_autenticada=False`, `versao_oficial_verificada=False`, `atualizacao_e_revogacao_exaustivas=False`, `vigencia_juridica_comprovada=False`, `autoridade_fiscal=False`, `credito_confirmado=False`, `checkout_autorizado=False`, `usavel_comercialmente=False`. Por item, `edicao_oficial_assinatura_validada=False`. G1.8 **não valida CMS nem cadeia X.509 no runtime do produto**; relatórios locais do piloto são evidência para futura integração de verificador independente, e não autoridade reutilizável por afirmação do chamador.

## Gates

1. Instalar **somente teste** `tests/test_enterprise_g18_external_publication.py`, correr RED com erro de módulo ausente esperado.
2. Com RED ratificado, instalar **somente serviço e documentação** e executar GREEN dos 35 testes, regressões G1.7/G1.6/G1.5 e integração anterior, revisão de hashes/diff.
3. Commit/push separado, só depois de gates e revisão. Não alterar `app/database.py`, tabelas, migrations, bibliotecas da venv-release, pagamentos, endpoints MEI, deployments ou repositórios paralelos.
4. Depois de GREEN, executar a observação real no PDF já adquirido em Downloads, sem importar para BD nem publicar arquivo privado.

## Gates futuros obrigatórios para produto integral

- Validador PDF/PAdES/legado em execução controlada, com âncoras oficiais versionadas, políticas, timestamps/LCR/OCSP históricos e adjudicação externa independente de autenticidade do publicador; o documento legado SHA-1 deverá permanecer de risco explicitado se a confiança não for resolúvel.
- Adaptador imutável CAS para `NormativeArtifact.immutable_location`, com bytes reais revalidados, vínculo ao `AcquisitionExecution`/`ArtifactReference`, e revisão de limites da G1.5 **somente com testes e autoridade explícita**.
- Provar `documento+item → versão/ato/norma/data/vigência` e a abrangência real das republicações/retificações/revogações pertinentes. O PDF piloto não fornece sozinho uma norma fiscal por item.
- Completar vínculo dos motores existentes de ICMS/ST/MVA/PMPF/PIS/Cofins/IRPJ/CSLL, regimes, créditos, risco e histórico em snapshot integral; entrega fiel por API/PDF/UI, elegibilidade documental, pagamento/checkout e deploy apenas após gates.

**Sem rede, BD real, writes, SEFAZ, marketplace, checkout ou deploy no contrato G1.8.**
