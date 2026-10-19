# SOLVERIS Enterprise — G1.11-R1 — Verificação criptográfica independente de PDF/CMS legado

Corte: 19/10/2026. Origem: branch `work/fiscal-assumptions-c0`, HEAD obrigatório `5425dc9b1ea4c91ebd20a81348b0a8ece9640e4f`.

## Finalidade e autoridade

Complementar G1.10 com verificação **real** dos bytes da assinatura digital `/adbe.pkcs7.sha1` (formato PDF legado), sem alterar G1.5–G1.10. A ferramenta nova em `tools/` é explicitamente invocada, nunca importada por produção. Lê bytes fornecidos pelo operador e SHA-256 da aquisição; devolve observação não comercial. Não abre rede, não persiste, não usa BD nem dados de clientes.

O módulo usa `pypdf` para resolver o campo de assinatura PDF, `asn1crypto` para CMS DER e `cryptography` para validar RSA PKCS#1 v1.5. Recalcula e confronta: SHA-256 do PDF integral; ByteRange cobrindo todo o ficheiro e excluindo exclusivamente o hex `/Contents`; SHA-1 histórico do ByteRange com eContent CMS; digest dos atributos assinados; identidade serial+issuer do certificado incluído; assinatura RSA dos atributos assinados. Recusa segundo signatário, estrutura não suportada, assinatura incompleta, bytes alterados e ausência de certificado coincidente.

Este formato exige SHA-1 na ligação ByteRange/CMS. **SHA-1 é legado e suscetível a colisões.** Um RSA matematicamente válido não implica autenticidade oficial da publicação, origem autorizada, segurança histórica nem aplicabilidade normativa.

O resultado `cms_assinatura_rsa_valida=True` é **apenas** verificação matemática do CMS extraído desse PDF. `fonte_primaria_autenticada`, `cadeia_icp_brasil_validada`, `identidade_publicador_autenticada`, `instante_assinatura_comprovado`, `revogacao_historica_comprovada`, `versao_oficial_verificada`, `vigencia_juridica_comprovada`, `autoridade_fiscal`, `credito_confirmado`, `checkout_autorizado`, `usavel_comercialmente` continuam invariavelmente **False**.

A ausência de carimbo RFC3161, o certificado histórico sem avaliação de confiança ancorada num instante demonstrado e a falta de prova completa de revogações impedem uma conclusão jurídica. `cms_tem_signing_time_nao_confiavel` apenas reporta presença do atributo, sem validar tempo. Mesmo uma LCR atual assinada não prova automaticamente o estado do certificado em fevereiro de 2026.

## Fontes oficiais de orientação

- ITI, DOC-ICP-15 e DOC-ICP-15.01 (verificação de assinatura, política, cadeia e validação): https://www.gov.br/iti/pt-br/assuntos/legislacao/documentos-principais
- ITI, Carimbo do Tempo: https://www.gov.br/iti/pt-br/acesso-a-informacao/perguntas-frequentes/carimbo-do-tempo
- ITI, assinatura digital com referência temporal AD-RT: https://www.gov.br/iti/pt-br/assuntos/repositorio/assinatura-digital-com-referencia-de-tempo-ad-rt

## Piloto e gates

PDF adquirido IOEPA 36.540, edição 23/02/2026: `C:\Users\Oem\Downloads\SOLVERIS_T1_IOEPA_PILOT_20260223\IOEPA_DOE_36540_20260223.pdf`, tamanho 2.764.152 bytes, SHA-256 `a23209626b9d7ca753aba82335c410ea4b636950579d39a90476b4c2d4de0e27`. Resultado esperado **sujeito ao smoke real**; o PDF real não integra os testes sintéticos do pacote.

1. RED: instalar **exclusivamente** `tests/test_enterprise_g111_legacy_pdf_signature_audit.py`. Falha esperada: `ModuleNotFoundError: No module named 'tools.enterprise_g111_legacy_pdf_signature_audit'`.
2. GREEN: instalar só `tools/enterprise_g111_legacy_pdf_signature_audit.py` e este documento por hashes, testar num **venv isolado** de auditoria que já tem `pypdf`, `asn1crypto`, `cryptography`, sem instalar pacotes na `.venv-release`.
3. Smoke com PDF real: verificar resultado e imprimir digest/estado. Qualquer incompatibilidade do formato, assinatura ou parser é STOP para análise; nunca trocar para `True` por alegações externas.
4. Commit/push exclusivamente três ficheiros após GREEN e verificação de escopo, sem mexer nos serviços existentes.

## Limitações deliberadas

Não valida PAdES, assinaturas PDF genéricas `adbe.pkcs7.detached`, CAdES arbitrárias, assinaturas múltiplas, DSS/LTV, timestamp externo, ancoragem governamental, revogação no tempo, cadeia de republicações, versão jurídica, UF/NCM, direitos fiscais ou elegibilidade comercial. G1.11 não substitui o ITI nem autoriza alterações a produção. PDFs rejeitados devem ser inspecionados separadamente, sem relaxar as restrições silenciosamente.
