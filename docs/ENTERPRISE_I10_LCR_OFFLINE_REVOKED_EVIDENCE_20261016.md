# SOLVERIS Enterprise — I10: observação de LCR assinada por cadeia já verificada

**Corte**: 16/10/2026. **Base**: `work/fiscal-assumptions-c0`, HEAD `ab4488b0b78f64dcdf92bea0ac4dd01814e9396a`, I9 ratificada. Uma única SOLVERIS Enterprise integral; não existe mini-produto.

## Âmbito estrito

`verificar_lcr_nfe_i10` reutiliza I9→I8→I7 para reconciliar NF-e modelo 55, assinatura XMLDSig, CNPJ declarado e cadeia X.509 para uma raiz externa pinada. Exige **uma LCR DER completa, direta e fornecida pelo operador para cada emissor dos certificados não-raiz**, em ordem folha→intermediárias. Exige um SHA-256 esperado para cada LCR. É um observador totalmente **offline e read-only**; não abre URL, Windows Store, ficheiros, certificados privados, SEFAZ, DB ou credenciais.

Valida assinatura RSA das LCRs, identidade do emissor, janela `thisUpdate`/`nextUpdate` contra instante UTC **fornecido**, `CRLNumber`, correlação AKI/SKI quando presentes, permissão `cRLSign` e rejeita certificados da cadeia listados como revogados nas LCRs fornecidas. Não admite LCRs indiretas, delta CRL, escopo incompleto, extensões críticas desconhecidas ou entradas críticas não suportadas. Aceita RSA PKCS#1v1.5 SHA-1 histórico (explicitamente sinalizado como fraco) e SHA-2 compatível, sem fallback a algoritmos não implementados. Cada entrada é limitada em bytes; nenhuma delas é guardada pelo módulo.

## Autoridade proibida

O facto de a LCR ser criptograficamente assinada **não comprova que o conteúdo foi obtido de canal oficial auditado**, nem que representa a situação atual global de revogação, nem impede rollback para uma LCR antiga ainda dentro da janela declarada. Os hashes fornecidos também podem ser arbitrários; não existe registo durável de anti-rollback nem âncora ICP-Brasil oficial provisionada. O instante é recebido do operador e não é provado externamente. A I10 não faz OCSP nem validação PKIX/RFC 5280 completa; perfis legítimos fora deste subconjunto são recusados como **não suportados**, não declarados inválidos no mundo real.

Logo, os únicos indicadores positivos são `assinaturas_lcrs_fornecidas_verificadas`, `certificados_nao_listados_nas_lcrs_fornecidas` e `cadeia_i9_para_ancora_pinada_verificada`. Os campos `origem_oficial_das_lcrs_verificada`, `atualidade_externa_das_lcrs_verificada`, `revogacao_oficial_global_verificada`, `politica_icp_brasil_completa_verificada`, `cadeia_icp_brasil_verificada`, `ocsp_verificado`, `situacao_sefaz_confirmada`, `efd_competencia_reconciliada`, `apuracao_mensal_completa`, `direito_creditorio_comprovado` e `checkout_autorizado` permanecem **False**. Nenhum dado pessoal, CNPJ, chave XML, certificado ou LCR é emitido.

## Gates

RED causal um teste com módulo ausente. GREEN 28 testes puramente sintéticos: LCR verdadeira sob CA sintética, certificado folha/intermediário listado, issuer incompatível, assinatura forjada, LCR expirada/futura, pin divergente, CRLNumber e AKI, delta e indirect fora do perfil, extensões críticas, falta e excesso de LCR e isolamento de rede. Regressões: I9 24, I8 22, I7 C14N 3, I7 26, I6 28, I5 22, I4N 16, I3N 18, I3A 18, I2 20, I1 16, I0 7 e 12 testes partilhados. Nenhum uso dos XMLs privados do repositório.

## Próximos gates para o produto integral

1. Obtenção e ratificação **independente** de raízes, LCRs e políticas ICP-Brasil oficiais, com identificação de versão, distribuição, procedência, anti-rollback e eventual OCSP. **Não automatizar consulta à SEFAZ sem autorização documental válida.**
2. Custódia auditável I4N/I5/I6: guardar os bytes autorizados fora do Git, atestar canal e implementar ledger durável anti-replay, sem falsos positivos fiscais.
3. EFD por competência, norma vigente por item/UF/NCM/ANP/regime, créditos, reconciliação de valores, rastreio jurídico e todos os gates de entrega e checkout da Enterprise. A privacidade dos XMLs reais publicados no repo deve ser tratada em intervenção separada, previamente autorizada.

MEI, pagamentos, banco, produção, certificados do Windows, motores normativos e deploy permanecem intocados.
