# SOLVERIS Enterprise — G1.11-R2 — CMS BER indefinido com EOC legítimo

Corte: 19/10/2026. Branch `work/fiscal-assumptions-c0`, HEAD inicial obrigatório `5425dc9b1ea4c91ebd20a81348b0a8ece9640e4f`.

## Causa e reprodução

No piloto real IOEPA, DOE 36.540 de 23/02/2026 (PDF SHA-256 `a23209626b9d7ca753aba82335c410ea4b636950579d39a90476b4c2d4de0e27`), a primeira execução G1.11 rejeitou `G111_CMS_PADDING_NAO_ZERO`/`G111_CMS_ASN1_INVALIDO`, embora o diagnóstico read-only tenha observado:

- `/SubFilter=/adbe.pkcs7.sha1`; PDF com ByteRange completo; 16.384 bytes de reserva `/Contents`.
- CMS `ContentInfo` signed_data **BER de comprimento indefinido**: cabeçalho de 2 bytes, corpo de 2.432 bytes e **trailer ASN.1 EOC de 2 bytes (`00 00`)**.
- Objeto completo de 2.436 bytes, seguido de **13.948 bytes exclusivamente `00`**. Não existia preenchimento não nulo depois do CMS.

A R1 concatenava somente `header + content` e tratava qualquer `trailing` de `asn1crypto.parser.parse()` como invalidade. Em BER indefinido, `trailing` é precisamente o terminador ASN.1 EOC e **faz parte do objeto CMS**; não é preenchimento PDF.

## Correção restrita R2

Na função `_get_cms`, aceitar **somente** um EOC `00 00` quando o cabeçalho exterior for exatamente `30 80` (SEQUENCE BER indefinida); para DER de comprimento definido, exigir trailer ASN.1 vazio. Construir o objeto `header + content + trailing` para `cms.ContentInfo.load(strict=True)`; recusar **qualquer byte não zero** após esse objeto. Adicionalmente, fazer parse sequencial das **duas partes obrigatórias de CMS ContentInfo**: OID (`UNIVERSAL 6`) e invólucro `content [0] EXPLICIT` (`CONTEXT 0`). Rejeitar bytes internos adicionais, inclusive quando um terminador EOC malformado fosse ignorado pelo parser de alto nível.

Os testes novos 14–17 cobrem BER/EOC válido com zeros reservados; reserva não nula; EOC com corrupção não nula; bytes extras não nulos entre conteúdo e EOC. Permanecem testes anteriores de hash do PDF, ByteRange, digest SHA1 legado, digest CMS, RSA e bloqueios de autoridade. Importante: **quando o EOC e o preenchimento são ambos zero, não existe informação suficiente para distinguir a origem de cada zero**. Nunca afirmar proteção impossível contra remoção de terminador se o preenchimento subsequente pode materializar o mesmo EOC efetivo.

## Prova e limites

O teste RED deve mostrar falha específica de `test_14` com verificador G1.11-R1 antes de substituir o serviço; o GREEN executa a suite sintética numa venv de auditoria isolada. O smoke real deve usar exatamente o PDF IOEPA com hash e tamanho revalidados. **Assinatura CMS RSA matematicamente válida NÃO é prova de autenticidade oficial, certificação ICP-Brasil no instante, revogação histórica, ausência de risco SHA1, validade normativa por operação nem autorização comercial**. Todos os sinais correspondentes permanecem `False`.

## Escopo

Substituições controladas apenas de `tools/enterprise_g111_legacy_pdf_signature_audit.py` e `tests/test_enterprise_g111_legacy_pdf_signature_audit.py` ainda não rastreados, com backups completos dos bytes R1 em `Downloads`, e criação deste documento R2. Preservar o documento G1.11-R1 original. Sem alteração na G1.5–G1.10, MEI, banco de dados, migrations, rede, dependências de `.venv-release`, pagamentos ou deploy. Sem commit/push até GREEN real e auditoria Git posterior.
