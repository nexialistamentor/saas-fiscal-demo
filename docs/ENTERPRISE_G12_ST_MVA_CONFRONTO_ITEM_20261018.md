# SOLVERIS Enterprise — G1.2: ligação ST/MVA ao confronto fiscal G1.1

**Base obrigatória:** `work/fiscal-assumptions-c0` / `ee1007562836378e2addb50f9af0a09b609aef88`.

**Escopo:** acrescentar apenas um adaptador read-only e um teste, sem modificar os
produtores legados, sem anexar automaticamente uma análise comercial e sem
instalar um novo resolvedor de normas ou tabela normativa.

## Circuito efetivamente ligado

1. Entrada: bytes XML NF-e sintética ou autorizada, sem acesso ao MEI.
2. Parser real `app.xml_service.ler_xml_unico` e leitura restrita para confirmar
   `nItem`, chave, UF, tipo de NF-e, finalidade, data com fuso, NCM, CFOP e ICMS10.
3. Resolvedor **existente** `app.services.fiscal_utils.resolver_aliquota_e_mva`
   com UF + NCM + data; bloquear se parcial, fallback ou ausente.
4. Releitura **existente** `buscar_mva` para confirmar fonte declarada,
   correspondência de valores e vigência: não autentica a publicação.
5. Priorização **existente** `resolver_base_calculo_st`: quando PMPF for escolhido
   ou quando MVA e base divergem, bloquear a simulação até existir conciliação
   específica de PMPF, embalagem, marca e unidade.
6. `MotorFiscal.calcular_base_st` e `MotorFiscal.calcular_icms_st` existentes,
   comparados a base devolvida pelo resolvedor. O cálculo subtrai `vICMS`
   **observado no XML**, não apurado independentemente por regra de ICMS próprio.
7. Confronto numérico através de `TaxConsistencyEngine` **G1.1**; os estados
   permanecem `COMPARACAO_NUMERICA_SEM_AUTORIDADE`, `PARCIAL_SEM_AUTORIDADE` ou
   `NAO_AVALIADO`. O adaptador não concede qualquer autoridade adicional.

## Limites expressos

- Simulação apenas para NF-e modelo 55 de saída normal, intrastadual,
  `idDest=1`, `ICMS10`, `modBCST=4`, CFOP 5xxx, sem frete, seguro, desconto,
  outras despesas ou redução de base que exigiriam composições adicionais.
- Não suporta PMPF, FCP, DIFAL, IVA ajustada, operação interestadual,
  ICMS parcial/antecipado ou legislação específica dos itens.
- `fonte_legal` é **texto vindo de tabela**, e não prova de publicação normativa
  oficial ou de vigência ratificada. Requer ainda ADR-020/norma original,
  enquadramento CEST/NCM/CFOP/CST, EFD e documentos de recolhimento.
- Hash XML é hash de bytes observados, não prova de autenticidade SEFAZ.
- Sem confirmação de crédito, restituição, conformidade fiscal ou checkout.
- Sem integrar ao `processar_e_persistir_xml`: fluxo compartilhado por MEI
  e outros regimes; a ligação Enterprise poderá ocorrer somente numa rota
  autorizada após verificação de posse, provenance e identidade fiscal.

## Gates

- 24 testes sintéticos isolados (sem empresas reais).
- Smoke de importação da versão preparada usando os **módulos originais** do
  checkout Windows (parser, resolvedores, MotorFiscal e G1), com lookup normativo
  sintético explicitamente marcado como tal. Isso valida wiring técnico, não
  autoridade tributária nem BD.
- 22 testes G1.1 e regressões previamente escolhidas (39 esperados no corte).
- Instalação só depois dos gates; nenhum commit ou push automático.

## Continuação G1.3

Ligar com gate de posse e identidade na **fronteira Enterprise**, introduzir
prova normativa de versão/fonte oficial/CEST/vigência e discriminar PMPF por
marca+embalagem antes de tornar qualquer resultado fiscal avaliável. Manter a
I13 histórica em `AWAITING_HISTORICAL_CRL_EVIDENCE` e usar apenas XMLs sintéticos
até que chegue o novo XML empresarial autorizado.
