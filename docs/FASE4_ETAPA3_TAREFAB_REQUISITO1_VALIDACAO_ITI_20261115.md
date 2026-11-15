# SOLVERIS — Fase 4 / Etapa 3 / Tarefa B — Requisito 1 (custódia dos decretos) — validação ITI e fecho do incidente de corrupção

**Data:** 15/11/2026

## Incidente: primeiro download do V2 estava corrompido

O ficheiro `DOE_PA_20230307_EXTRA_35315.pdf` obtido em 13/11/2026 passava no teste de cabeçalho `%PDF-`, mas não abria em nenhum leitor PDF real. O ficheiro original foi renomeado para `DOE_PA_20230307_EXTRA_35315_PRIMEIRA_TENTATIVA_CORROMPIDO.pdf` e mantido para auditoria (hash antigo: `C3F75D50C23912BFDDD43195A03C9DBD2DC61FE34D02311628EF3DBA1849CC9A`, inválido como prova). Um novo download do mesmo URL produziu um ficheiro íntegro, que abre normalmente e foi validado pelo ITI (abaixo). Hash correto registado no manifesto local: `777D92FA94E2227C5E094666D51D03492F5C8FB6BD8AF91870D935ECA60DA498`.

**Lição:** o teste de cabeçalho `%PDF-` sozinho não garante que o ficheiro é um PDF válido/completo; é preciso confirmar abertura real antes de aceitar um download como custódia.

## Validação no serviço oficial ITI (validar.iti.gov.br)

### V1 — DOE_PA_20220830_35096.pdf (Decreto 2.588/2022)

- SHA-256: `3bd54aa6a6b28d3f94d3ff0957a3f6bd0935f5b07fda08dfd97e192e7268543a`
- Assinante: IMPRENSA OFICIAL DO ESTADO, CNPJ 04.835.476/0001-01
- Data de assinatura: 29/08/2022 22:59:45 BRT
- Emissor do certificado: AC Imprensa Oficial SP RFB G5 (válido 21/10/2021–21/10/2022, assinatura dentro da janela de validade)
- Estrutura: Em conformidade com o padrão
- SignatureDictionary: Valid
- Status de assinatura: Reprovado (certificado folha expirado hoje, sem LTV/timestamp embutido para confirmação offline retroativa)

### V2 — DOE_PA_20230307_EXTRA_35315.pdf (Decreto 2.931/2023)

- SHA-256: `777d92fa94e2227c5e094666d51d03492f5c8fb6bd8af91870d935eca60da498`
- Assinante: IMPRENSA OFICIAL DO ESTADO, CNPJ 04.835.476/0001-01
- Data de assinatura: 07/03/2023 21:06:29 BRT
- Emissor do certificado: AC PRODESP v1 (válido 18/08/2022–18/08/2023, assinatura dentro da janela de validade)
- Estrutura: Em conformidade com o padrão
- SignatureDictionary: Valid
- Status de assinatura: Reprovado (mesma causa: certificado folha expirado hoje, sem LTV/timestamp embutido)

## Interpretação

Os dois decretos, assinados com certificados de cadeias distintas (G5 vs PRODESP v1), convergindo na mesma raiz ICP-Brasil/ITI (válida até 2029), apresentam a mesma falha técnica explicável — certificado expirado sem validação de longo prazo — e não um erro de conteúdo, estrutura ou integridade. Isto é consistente com documentos legítimos validados anos depois sem LTV, não com adulteração.

Fonte secundária de conteúdo (PGE-PA, já reportada em missão anterior) corrobora o texto normativo (CEST 03.010.01, MVA 40%) sem alegar identidade binária com os PDFs da IOEPA.

## Estado

A aceitação desta evidência como suficiente para o requisito 1 permanece reservada a Miguel. Nenhuma escrita em test.db, produção ou código foi realizada.
