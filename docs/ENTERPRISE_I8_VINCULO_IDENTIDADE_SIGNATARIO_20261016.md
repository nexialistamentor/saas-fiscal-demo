# SOLVERIS Enterprise — I8: conciliação do signatário da NF-e com o emitente

**Linha de desenvolvimento integral**, não um mini-produto ou SKU separado. A sequência I0–I7 C14N permanece íntegra. Branch obrigatória `work/fiscal-assumptions-c0`, baseline Git `8293f3d545d7a0363ba6e1b460f423f05c5a415c`.

## Objetivo e prova

O módulo `enterprise_nfe_i8_signer_identity.py` reutiliza a validação matemática XMLDSig I7 sobre os mesmos bytes exatos; examina o CNPJ do emitente em `infNFe/emit/CNPJ`, exige equivalência com o CNPJ codificado na chave de acesso NF-e (`chave[6:20]`) e com o outroNome do certificado X509 embutido no XML, OID `2.16.76.1.3.3`. Exige o CNPJ fornecido pela fronteira chamadora e dígitos verificadores válidos. A extensão ICP-Brasil aceita `otherName` ASN.1 **PrintableString** ou **OCTET STRING** com exatamente 14 dígitos ASCII; sem fallback para CN, organização ou campo não padronizado. Rejeita campo duplicado e certificateCA, exige chave de assinatura compatível, e janela de validade do certificado coerente com a data de emissão declarada no XML. O resultado contém somente identificadores SHA-256 e flags de observação, nunca CNPJ/chave em claro.

**Fonte normativa consultada 16/10/2026:** ITI [DOC-ICP-04 — Política de Certificados](https://repositorio.iti.gov.br/resolucoes/Resolucao179_DOC-ICP-04.htm); ITI [DOC-ICP-04.01 — Atribuição de OID](https://repositorio.iti.gov.br/instrucoes-normativas/IN2020_15_DOC-ICP-04.01.htm). O DOC-ICP-04 ressalva a transição futura para o atributo `serialNumber` do DN. Este contrato limita-se ao otherName historicamente especificado; **certificados válidos em outros perfis não são automaticamente inválidos por serem recusados por este perfil restrito**.

## Fronteiras não resolvidas

- O certificado é retirado do próprio XML; portanto uma correspondência de CNPJ **não comprova titularidade jurídica externa, integridade ICP-Brasil, cadeia confiável, ACL, estado de revogação, autorização para consultar terceiros ou situação SEFAZ**. O mesmo vale para a data de emissão declarada, que ainda não possui confirmação temporal independente.
- Não abre URLs, OCSP, CRL, Windows Store ou SEFAZ; não grava em BD, não mexe no MEI, pagamento, produção, checkout ou modelos normativos. Continua `checkout_autorizado=False`, `credito_fiscal_comprovado=False`, `apuracao_mensal_completa=False`.
- O comando offline `python -B -m app.scripts.verificar_signatario_nfe_i8 <caminho>` limita-se a um ficheiro local, não publica identidade, chave ou certificado. A observação sobre XML real já no repo nunca é condição para o commit e não confere permissão de uso.
- Repositório público com XMLs de terceiros identificados permanece um risco de privacidade. Regularizar custódia/histórico é intervenção distinta que exige autorização e salvaguarda de evidências.

## Gates

RED causal: `test_00_adapter_required` falha por módulo ausente na baseline. GREEN: 22 testes puramente sintéticos, incluindo RSA-SHA256, CNPJ SAN OtherName printable/octet, recusa de divergência/chave, CA, validade declarada, assinatura adulterada e CLI offline. Regressões I7 26 + C14N 3, I6 28, I5 22, I4N 16, I3N 18, I3A 18, I2 20, I1 16, I0 7 e suíte partilhada. Todas usando DB inacessível (`DATABASE_URL=sqlite://`, `ALEMBIC_RUNNING=1`); push normal apenas após GREEN e diff --cached --check.

## Continuação integral

Próximos gates obrigatórios e reais: cadeia ICP-Brasil com âncoras oficiais independentes + CRL/OCSP + temporalidade; canal SEFAZ legitimamente autorizado, prova de custódia antirreplay; reconciliação EFD-Contribuições por competência; versão/vigência de norma item a item para todas as verticais incluindo monofásico combustíveis; avaliação dos créditos com base fiscal; passagem pelos gates comerciais existentes da Enterprise. Nenhuma redução a subproduto.
