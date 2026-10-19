# SOLVERIS Enterprise G1.11-R3 — CMS sem signedAttrs (19/10/2026)

## Evidência do Windows

No PDF oficial observado localmente (SHA-256 `a23209626b9d7ca753aba82335c410ea4b636950579d39a90476b4c2d4de0e27`), G1.11-R2 passou 16 testes e ignorou um; a verificação real interrompeu com `G111_CMS_ATRIBUTOS_ASSINADOS_AUSENTES`. O `ByteRange` integral e o preenchimento zero de BER/EOC já haviam sido examinados. A ausência de `signedAttrs` **não é por si só prova de falsificação ou validade**.

## Contrato RFC 5652

Secções 5.3, 5.4 e 5.6: o `signedAttrs` é opcional quando `encapContentInfo.eContentType == id-data`. Quando está presente, `message_digest` e `content_type` são obrigatórios e verificam-se as assinaturas sobre o DER `SET OF` assinado. Quando está ausente, a assinatura RSA-PKCS#1 v1.5 é verificada **sobre os octetos exatos do eContent** usando o algoritmo declarado no `SignerInfo`, sem criar atributos artificiais e sem fallback em caso de atributos malformados. **Para `/adbe.pkcs7.sha1`, o `eContent` deve conter o digest SHA-1 recalculado do `ByteRange`**; a identidade do certificado signatário é cotejada com o `SignerInfo`.

## Estados e fronteiras

Para assinatura sem atributos, `cms_signed_attributes_digest_confere=False` (não se afirma prova inexistente), `cms_assinatura_sem_atributos_verificada=True` apenas após RSA verdadeiro. `cms_assinatura_rsa_valida=True` quando a matemática da assinatura é válida. `cms_tem_signing_time_nao_confiavel=False` se não existe `signedAttrs`. Não se concede certificação ICP-Brasil, validação histórica, timestamp, frescura, adequação jurídica, crédito nem checkout. O SHA-1 legado continua de risco por colisão.

## Limites

G1.11-R3 somente auditoria criptográfica limitada. Nenhuma escrita de BD, rede no serviço, endpoint, SEFAZ, pagamento, MEI ou produção. A `.venv-release` e os motores e cadeia G1.5-G1.10 não são modificados. Execução em `.venv-pyhanko` isolada. O smoke do PDF real deve comprovar RSA e SHA1, e diferenciar ausência de atributos de falha efetiva; sem alteração dos sinais comerciais. Commit/push apenas com GREEN real e hashes ratificados.
