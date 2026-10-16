# SOLVERIS Enterprise — I7: verificacao matematica da assinatura NF-e

**Corte**: 16/10/2026. Branch Enterprise `work/fiscal-assumptions-c0`; baseline obrigatoria `a0cdf185aaee9bfd4b2a0ae24897c573592120c3` (I6). MEI e producao intocados.

## Contrato

`app/services/enterprise_nfe_i7_xml_signature.py` verifica **somente** a assinatura XMLDSig enveloped de uma NF-e modelo 55, versao 4.00. Recebe **bytes exatos** da NF-e, chave esperada e SHA256 dos bytes; nao le ficheiros, BD, certificados do Windows, rede ou SEFAZ. Reutiliza o verificador nacional I3N para cUF/modelo/DV. Checa raiz NFC-e/NF-e, cardinalidade unica de infNFe e assinatura, identificador da referencia sem colisao, transformacoes enveloped+C14N 1.0 e canonicalizacao da infNFe. Verifica digest do conteudo e assinatura RSA-PKCS1 v1.5 de SignedInfo contra a chave do certificado X.509 *embutido no proprio XML*. Rejeita referencias externas e metodos fora da allowlist.

Aceita a forma NF-e historicamente documentada **RSA-SHA1/SHA-1** e tambem **RSA-SHA256/SHA-256**; sinaliza explicitamente `RSA_SHA1_LEGADO_COLISAO_RISCO` para os casos SHA-1. A verificacao matematica SHA-1 **nao representa resistencia criptografica moderna equivalente ao SHA-256**. A NF-e tem historico de requisitos especificos do manual do contribuinte; verificar vigencia de esquemas antes de ampliar algoritmos.

A prova positiva devolve `assinatura_matematica_verificada=True` e `digest_infNFe_verificado=True` com hashes dos bytes e do certificado embutido, nunca o certificado ou dados empresariais em claro. **TODAS** as flags seguintes continuam falsas: `cadeia_icp_brasil_verificada`, `revogacao_certificado_verificada`, `titularidade_emitente_verificada`, `situacao_sefaz_confirmada`, `protocolo_sefaz_autenticado`, `norma_vigente_verificada`, `apuracao_mensal_completa`, `direito_creditorio_comprovado`, `checkout_autorizado`.

O certificado X509 pode ser autogerado ou estranho ao emissor. Esta funcao **NAO** valida a cadeia ICP-Brasil, revogacao CRL/OCSP, assinatura ou autenticidade da resposta/protocolo SEFAZ, posses e poderes do emitente, eventos posteriores, temporalidade de emissao, regime, EFD ou creditos. Portanto, nao existe elevacao a prova fiscal oficial. Uma assinatura matematicamente correta com certificado nao confiavel continua **nao autenticada perante a SEFAZ**.

O CLI `app/scripts/verificar_assinatura_nfe_i7.py` aceita *manualmente* um caminho local com qualquer extensao, sem editar o ficheiro. Mostra apenas sha256, algoritmo, certificado em hash e indicadores negativos de autoridade. Nao enviar XMLs de empresas nem dados pessoais ao Git; consulta oficial permanece separada e depende de autorizacao legitima.

## Validacao

RED causal: modulo ainda ausente e exatamente um teste falha por `I7_RED_CAUSAL_MODULE_MISSING`. GREEN: 26 testes sinteticos, incluindo RSA-SHA1, RSA-SHA256, falso certificado, alteracao do XML, alteracao do SignedInfo, referencia externa, transformacoes, XML wrapping e CLI offline; regressao I6 28, I5 22, I4N 16, I3N 18, I3A 18, I2 20, I1 16 e I0 7; regressao partilhada selecionada. Ambiente isolado `DATABASE_URL=sqlite://`, `ALEMBIC_RUNNING=1`, sem create_all e sem consulta. Ratificacao local antes de commit/push. Deployment desligado na branch e em main.

## Continuidade real

1. Executar o CLI offline sobre NF-e 55 legitimamente acessivel para obter evidencias de integridade matematica, sem usar certificado do Windows e sem transitar dados de empresas ao chat.
2. Implementar politica de confianca ICP-Brasil, verificacao da cadeia, revogacao e vinculo do certificado ao emitente. Confrontar o estado oficial da NF-e e dos eventos em transporte legitimamente autorizado, com custodia comprovada e anti-replay.
3. Passar a cobertura EFD por competencia e provas item/norma/regime antes de reconhecer qualquer credito. Prioridade aos casos nacionais, incluindo ICMS monofasico de combustiveis.

Fonte primaria: Manual de Orientacao do Contribuinte NF-e (Portal Nacional NF-e / CONFAZ) — algoritmo historico RSA-SHA1, referencia por Id, C14N 1.0, transformacoes enveloped.
