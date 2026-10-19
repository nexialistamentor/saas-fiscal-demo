# SOLVERIS Enterprise G1.10-R1 — CAS → ADR-020 → G1.5–G1.8

**Base ratificada:** `work/fiscal-assumptions-c0` HEAD `771d61345d8f0b2be55b4d4b5c06b176f90b3504` (G1.9-R2).

## Missão

Habilitar **apenas por argumento explícito** `cas_root` a leitura verificável de
`NormativeArtifact.immutable_location` com esquema G1.9 `cas+sha256://sha256/<hex>`
na cadeia existente G1.5 → G1.6 → G1.7 → G1.8. O limite histórico G1.5 de
2 MiB mantém-se para `immutable_bytes`; o percurso CAS G1.9 permite de 1 KiB até
16 MiB com SHA-256 refeito em duas leituras sob descritores abertos. Nenhuma
localização legada não canónica é reinterpretada como CAS.

## Autoridade e fronteiras

- **G1.5 permanece soberana**: consulta os mesmos registos `ArtifactReference`,
  `AcquisitionExecution`, `NormativeArtifact` e três `ArtifactVerificationRecord`
  (`authenticity`, `integrity`, `preservation`), valida identidades e predecessores
  antes de declarar `cadeia_interna_adr020_verificada=True`.
- Só no ramo `immutable_bytes is None`, `immutable_location` não nula e
  `cas_root` explícita a G1.5 usa `cotejar_localizacao_adr020_g19` com os **mesmos
  identificadores da aquisição e artefacto**, URL exato, tamanho e digest,
  seguida de todas as verificações ADR-020 anteriores; erro/ausência de CAS
  mantém o item não cotejado.
- G1.6/G1.7/G1.8 encaminham `cas_root` **somente quando não nula**; todos os
  chamadores anteriores mantêm a assinatura de invocação das dependências,
  comportamento read-only e contratos de saída.
- O resultado ainda significa **vínculo interno por hash**, não certificado
  oficial, temporalidade confiável, exaustividade de revogações, aplicabilidade
  tributária, direito a crédito ou elegibilidade comercial.
- Todos os campos `fonte_primaria_autenticada`, `versao_oficial_verificada`,
  `atualizacao_e_revogacao_exaustivas`, `vigencia_juridica_comprovada`,
  `autoridade_fiscal`, `credito_confirmado`, `checkout_autorizado`,
  `usavel_comercialmente` permanecem `False`.
- A G1.9 continua a não garantir imutabilidade contra intervenções privilegiadas
  nem custódia por uma entidade externa; o PDF piloto IOEPA permanece fora da BD
  e sem prova de ato/norma fiscal aplicável. O PDF com assinatura legada SHA-1
  permanece sem prova de timestamp RFC 3161 nem revogação histórica exaustiva.

## Gates

1. RED: instalar apenas o novo teste `test_enterprise_g110_cas_pipeline.py` e
   exigir falha da opção `cas_root` na G1.5 anterior.
2. Validar HEAD, hashes de *Git blob* dos quatro módulos de origem, ficheiros
   limpos, patch contextual completo e AST antes de qualquer escrita. Guardar
   originais fora do repositório; nunca sobrepor versões alheias.
3. Aplicar quatro alterações mínimas e instalar este documento; executar os
   testes G1.10 e regressões reais G1.5 a G1.9, incluindo os casos já RATIFICADOS.
4. Verificar linhas de diff e escopo; commit/push específico apenas após GREEN,
   sem deploy, bases reais, MEI, LLM source trust, SEFAZ ou checkout.
5. Testar ligação com as linhas ADR-020 **reais e verificadas**, quando houver
   aquisição e extração autenticadas; o teste sintético não cria essas linhas.

Este gate **não** é homologação comercial do produto Enterprise integral.
