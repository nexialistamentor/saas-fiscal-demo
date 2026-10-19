# SOLVERIS Enterprise — G1.5: cotejo de artefacto normativo ADR-020

**Base de trabalho:** `work/fiscal-assumptions-c0` · HEAD `1962b11335e3e1066a2658e3e40c788066825dcc` (G1.4).

## Objetivo e ligação causal

G1.5 chama obrigatoriamente o circuito **G1.4 → G1.3 → I2 / G1.2 / G1** na mesma base e nos mesmos bytes documentais. Apenas depois do gate de posse, relatório persistido/fingerprint e enquadramento estrutural G1.4, aceita identificadores explícitos ADR-020 **não confiáveis** para resolver, por `db.get`, os seguintes objetos existentes:

1. `ArtifactReference`: referência em evento `resolvida`, identificador de ato e localizador exato iguais aos metadados candidatos G1.4.
2. `AcquisitionExecution`: evento/estado `conclusao`/`concluida`, vinculado à referência exata.
3. `NormativeArtifact`: vínculo à mesma execução e referência, bytes imutáveis presentes na própria linha (limite 2 MiB), tamanho e SHA-256 matematicamente coincidentes com o candidato G1.4.
4. `ArtifactVerificationRecord`: três tipos exatos `authenticity`, `integrity`, `preservation`, todos com resultado registado `conclusivo_favoravel`, sem incidente no registo **referenciado**, hashes do mesmo artefacto, predecessores vinculados.

A prova é estritamente **interna, documental e referenciada**. Não são fabricados registos de aquisição/verificação e não se gravam resultados na BD. Ficheiros armazenados em CAS externos (`immutable_location`) não são lidos nem aceites até existir gate próprio. Nenhum texto de XML, documento normativo ou dado empresarial é colocado no resultado da G1.5; somente metadados técnicos limitados.

## Limites importantes, mesmo quando os quatro pontos passam

- **A presença de `conclusivo_favoravel` na BD não verifica autonomamente a identidade do verificador ou a fonte oficial.** G1.5 confere a existência e a coerência desses registos, não executa um verificador externo independente, nem confirma a criptografia de todos os `record_hash`.
- Não confirma se há verificações, incidentes ou revogações **posteriores** aos IDs fornecidos; o snapshot referenciado não tem frescura comprovada. Também não comprova horário autêntico de publicação/vigência.
- O `versao_ato` da G1.4 permanece declaração não verificada: G1.5 **não** interpreta nem compara semanticamente o texto do ato, os dispositivos legais, as exceções, CEST ou o regime tributário.
- Uma coincidência textual URL/identificador/hash com referência previamente carregada **não prova a autenticidade do órgão publicador**, nem vigência jurídica, autorização fiscal, incidência, crédito, restituição, escritura EFD, recolhimento, autorização SEFAZ, pagamento, ou disponibilidade comercial.
- Os flags `fonte_primaria_autenticada`, `enquadramento_legal_autorizado`, `autoridade_fiscal`, `credito_confirmado`, `checkout_autorizado`, `usavel_comercialmente` continuam invariavelmente `False`.
- **Não alterar** `app/database.py`, `app/models.py`, os motores legados, MEI, pagamentos, bases reais, origem das normas ou deploy. Só adicionar este adaptador, os testes e este documento.

## Prova e gates

- **34 testes sintéticos** sem rede nem BD para contratos de entrada, ordem de chamadas, adulteração, hashes, identidade e bloqueios de autoridade.
- Smoke com **módulos reais I2/G1.3/G1.2/G1.4/G1** e classes ADR-020 existentes; NF-e e ato normativo estritamente sintéticos; DB fake `get` somente leitura; resolvedor sintético por injeção no processo de teste. Prova integração técnica, **não** verificação oficial.
- Regressões selecionadas no Windows; não constitui suíte completa do projeto.
- Só instalar três novos ficheiros após gates `STAGED` + smoke real. Commit e push separados após inspeção de hashes, status e diff.

## Próximos gates técnicos

G1.6 deve ligar verificadores oficiais independentes, frescura do estado de verificação, fonte institucional e versão efetiva **do conteúdo** do ato, bem como exceções/revogação, sem elevar autoridade por simples armazenamento. Depois, validação jurídica da aplicabilidade a cada operação, ICMS próprio independentemente recalculado e trilhas de escrituração/recolhimento ainda separadas. XML novo real não é pré-requisito para estes testes sintéticos.
