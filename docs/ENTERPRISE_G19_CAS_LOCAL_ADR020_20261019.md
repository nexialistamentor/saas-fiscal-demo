# SOLVERIS Enterprise — G1.9 CAS local por conteúdo (proposta controlada)

**Base obrigatória:** `work/fiscal-assumptions-c0` HEAD `9d91275c96992be8cd04831544738915aa179015` (G1.8, commit e push concluídos; 175 testes anteriores verdes). G1.9 não mexe nos ficheiros anteriores.

## Âmbito

O modelo ADR-020 `NormativeArtifact` já tem `immutable_bytes` **ou** `immutable_location`; a G1.5, porém, aceita somente os `immutable_bytes` até 2 MiB e **recusa explicitamente** `immutable_location`. O PDF piloto IOEPA é de 2.764.152 bytes, logo não pode passar a G1.5 por esse caminho.

O serviço G1.9 estabelece um **novo formato opcional de localização** `cas+sha256://sha256/<digest sha256 minúsculo>` para um diretório local **explicitamente fornecido**, e nunca assume que as localizações antigas da ADR-020 têm esse formato. O percurso é derivado exclusivamente do digest: `root/sha256/ab/<digest>.pdf`. O escritor usa criação exclusiva (`O_EXCL`) e falha sem sobrescrever. O leitor recalcula o SHA-256 integral em cada leitura, verifica tamanho, cabeçalho PDF, tipo de ficheiro, ligações simbólicas/junctions/reparse points e estabilidade observável durante a leitura. Limites: 1 KiB–16 MiB. O armazenamento local não assegura imutabilidade contra administradores, rollback de ficheiro/disco, substituição física, hardlinks ou privilégios elevados. Prova de custódia externa independente: **FALSE**.

A função independente `cotejar_localizacao_adr020_g19` consulta **somente** modelos reais `NormativeArtifact`, `ArtifactReference`, `AcquisitionExecution`, compara identidades, aquisição concluída, locator exato, hash, tamanho e bytes do CAS. Não escreve BD. Não cria linhas ADR-020 nem altera migrations ou contratos originais. Este cotejo isolado **não substitui a cadeia G1.5**; esta continuará a recusar artefactos `immutable_location` até uma missão futura expressamente aprovada, RED/GREEN e regressões completas. Não altera G1.8 nem utiliza DB de produção.

## Piloto real

A aquisição IOEPA `https://www.ioepa.com.br/arquivos/2026/2026.02.23.DOE.pdf` produziu SHA-256 `a23209626b9d7ca753aba82335c410ea4b636950579d39a90476b4c2d4de0e27`, 2.764.152 bytes. Pode ser arquivado localmente **fora do repositório** num CAS de demonstração, com comando autónomo e gate de hash. Isso não insere o artefacto no banco nem cria prova de aplicação a operações fiscais concretas.

## Provas preservadas e bloqueios

G1.8 tem hash e relação do PDF real, mas ainda sem ligação ADR-020 real; o documento `/adbe.pkcs7.sha1` teve CMS RSA verificado, cadeia de certificados SERPRORFBv5 → RFBv4 → Raiz ICP-Brasil v5 verificada e três LCR assinadas consultadas. **Não há timestamp RFC 3161, prova temporal de assinatura ou prova completa de não revogação em fevereiro/2026.** O SHA-1 mantém risco. Certificado da Imprensa Oficial não garante por si só enquadramento fiscal por item, atos/revogação exaustivos, versão jurídica, vigência ou ausência de exceções.

G1.9 retorna invariavelmente `fonte_primaria_autenticada=False`, `versao_oficial_verificada=False`, `atualizacao_e_revogacao_exaustivas=False`, `vigencia_juridica_comprovada=False`, `autoridade_fiscal=False`, `credito_confirmado=False`, `checkout_autorizado=False`, `usavel_comercialmente=False`.

## Gates de instalação

1. Instalar exclusivamente o teste novo e constatar RED com módulo ausente; sem apagar testes existentes.
2. Instalar serviço e documentação com comparação de hashes, GREEN sintético e regressões G1.8→G1.5; hash/diff, commit e push separados.
3. Smoke real: escrever com exclusividade o PDF IOEPA já adquirido num `Downloads/…/CAS_G19`, reler, recalcular o SHA-256 e comprovar que o estado de autoridade fiscal e comercial permanece False.
4. Próximo gate após G1.9: desenhar G1.10 para rever G1.5 e ligar um armazenamento CAS fiável à cadeia ADR-020, **sem reduzir** regras de proveniência, verificação/predecessores, cobertura e interpretação fiscal. Completar o produto Enterprise integral (todos os motores, API/PDF/UI, aquisição e checkout) só depois de homologação.

Sem rede, DB real ou write de BD, MEI, SEFAZ, checkout ou deployment na G1.9.
