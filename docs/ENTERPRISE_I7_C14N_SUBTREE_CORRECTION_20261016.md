# SOLVERIS Enterprise — I7 C14N: correcao da canonicalizacao em subarvores

Data: 16/10/2026. Base da branch `work/fiscal-assumptions-c0`: `227797ebc3e1b638987573b14ae8c0a3b98ea3c3`.

## Incidente real

O verificador I7 devolveu `I7_REFERENCE_DIGEST_INVALID` no documento NF-e 55 local de teste previamente usado, apos o commit I7 ter passado nas suites sinteticas. Nao concluir que o XML foi adulterado ou que a SEFAZ confirmou/autenticou o documento.

## Analise causal

O I7 original usava `etree.tostring(node, method='c14n', exclusive=False, with_comments=False)` diretamente sobre a **subarvore com ascendentes**. No lxml/libxml2 reproduzido em ensaio isolado, a canonicalizacao pode introduzir uma declaracao espuria `xmlns=""` nos descendentes, fazendo com que o digest SHA-1 calculado difira do `DigestValue` que uma NF-e corretamente canonizada transporta.

Foi comparado em leitura o conteudo NF-e 55 existente no GitHub publico (SEM copia no teste e SEM incluir PII); o digest SHA-1 indicado bateu com a canonicalizacao inclusiva esperada do infNFe, apos preservar o namespace herdado. O resultado ainda deve ser confirmado com os **bytes exatos no Windows**, e a assinatura RSA de `SignedInfo` tambem tem de ser validada.

## Intervencao restrita

- `enterprise_nfe_i7_xml_signature.py`: `_canonical` usa `deepcopy(node)` antes de chamar C14N para isolar a subarvore e preservar o namespace efetivo. A mesma rotina e aplicada ao digest da `infNFe` e a assinatura RSA sobre `SignedInfo`.
- `test_enterprise_nfe_i7_xml_signature.py`: a rotina de geracao dos testes sinteticos passa a assinar o conteudo canonicamente isolado, em vez de assinar com o mesmo comportamento defeituoso.
- `test_enterprise_nfe_i7_c14n_regression.py`: novo RED/ GREEN explicito com namespaces herdados e nao mutacao.
- Nenhuma NF-e real e copiada, incluida ou publicada nos testes.

## Seguranca e limites

A matematica XMLDSig continua distinta de confianca na cadeia ICP-Brasil, verificacao de revogacao e titularidade, situacao oficial na SEFAZ, EFD, receitas, direitos creditorios e pagamentos. SHA-1 legado continua marcado como risco; nao alargar algoritmos, trust stores, rotas HTTP nem NF-e de terceiros nesta correcao.

A amostra XML real esta exposta num repositorio publico e exige intervencao de privacidade separada com autorizacao; o hotfix nao remove, modifica nem regrava historia. Nenhuma consulta SEFAZ/certificado, DB, migracao, MEI, producao ou deploy.
