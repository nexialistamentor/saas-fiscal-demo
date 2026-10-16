# SOLVERIS Enterprise — I9: cadeia X.509 restrita a âncora aprovada explicitamente

**Corte de 16/10/2026.** Branch Enterprise `work/fiscal-assumptions-c0`, HEAD obrigatório `e3c286c90399daa8e7583e9dc435f3ebb1763e5f`, após I8 ratificada. Continuação do **único diagnóstico Enterprise integral**, sem mini-produto.

## Autoridade e objetivo

`enterprise_nfe_i9_chain_anchor.py` recebe os bytes exatos da NF-e, a chave, o CNPJ emitente e o hash SHA-256; reutiliza I8→I7 e valida o percurso linear **folha embutida na NF-e → intermediárias explicitamente entregues → raiz externa**, exigindo SHA-256 da raiz aprovado pelo chamador. A raiz NÃO é inferida nem aceite do certificado que vem no próprio XML; não existem raízes embutidas no código, downloads automáticos ou fallback à Windows Store.

- Validação de assinatura RSA-PKCS1v1.5 de cada certificado, sujeito/emissor, correspondência AKI/SKI quando presentes, janela temporal em UTC fornecida, BasicConstraints CA, KeyUsage keyCertSign, pathLen e recusa de extensões críticas CA desconhecidas.
- Assinaturas de certificados permitidas neste perfil: RSA com SHA-1 histórico (sinal de risco), SHA-256, SHA-384 ou SHA-512. NENHUMA assinatura RSA-PSS, EC ou algoritmo não listado tem fallback silencioso; isso limita abrangência, não invalida esses certificados externos.
- Proteção contra certificados repetidos, raiz divergente, intermediário adulterado, emissor incorreto, CA sem permissão, alteração XML e CNPJ divergente. Somente hashes, contagens, flags e estado técnico são devolvidos.

## Fronteira fundamental

**`cadeia_assinaturas_ate_ancora_pinada_verificada=True` NÃO significa `cadeia_icp_brasil_verificada=True`.** O segundo permanece `False`. Uma raiz sintética e um hash autodeclarado podem formar uma cadeia válida, sem nenhuma legitimidade fiscal. O produto ainda não tem a lista de âncoras ICP-Brasil obtida e ratificada por canal independente, regras de políticas e nomes RFC5280 completos, atualização das LCR/OCSP, timestamp externo, cadeia pública auditada ou anti-replay.

A I9 é um verificador de **assinaturas e topologia restrito**, não um validador PKIX completo. Não usar os campos como autenticação ICP-Brasil. Nenhum certificado privado ou real de terceiro é incluído, carregado ou distribuído. A assinatura matemática e identidade foram exercitadas na I7/I8; a I9 só aumenta a capacidade verificável sem conceder autoridade de venda.

## Testes e isolamento

RED causal: módulo I9 ausente, exatamente um teste falha. GREEN: 24 testes I9 com chaves, XML e CA exclusivamente sintéticos; regressão I8 (22), I7 C14N (3), I7 (26), I6 (28), I5 (22), I4N (16), I3N (18), I3A (18), I2 (20), I1 (16), I0 (7) e regressão partilhada (12). Testes sem rede, certificados reais, base de dados, migrações, MEI, checkout, pagamento e deploy. Repo público com XMLs de terceiros precisa intervenção de privacidade separada e autorizada.

## Continuação necessária para o diagnóstico integral

1. Canal independente para obter e ratificar âncoras oficiais do ITI, política de certificados, cadeia completa e prova de revogação/estado temporal (LCR/OCSP). Prova de ICP exige esse passo e perfil adequado, não apenas o módulo I9.
2. Integração do operador SEFAZ I4N com custódia, autenticação demonstrável e anti-replay em consulta permitida; seguir protocolo e eventos posteriores sem inferir situação a partir da assinatura XML.
3. Reconciliar EFD-Contribuições e receitas item a item por competência; vincular norma/UF/NCM/ANP/regime e cálculos fiscais antes de qualquer reconhecimento de crédito. Fechar os gates das 52 capacidades e respetiva entrega comercial integral.

**Nenhum motor existente é substituído ou despromovido por esta etapa.**
