# SOBERANA L2 — ROADMAP V3

> Critérios de abertura ao utilizador e rota para Fintech

> Data: 2026-05-05 | HEAD: 1cf6385

---

## CRITÉRIOS DE ABERTURA (todos obrigatórios)

A plataforma só abre ao utilizador quando TODOS os itens abaixo estiverem ?.

---

## BLOCO 1 — ENGINES FISCAIS CORRECTAS

### E1 ? IRPJ (CRÍTICO)

**Problema:** limiar adicional R$20.000 total em vez de R$20.000/mês

**Fix:** `irpj_engine.py` ? limiar = R$20.000 × meses do período

**Base legal:** RIR/2018 art. 622 ? adicional 10% sobre excesso de R$20.000/mês

**Critério:** cálculo correcto para empresa com lucro R$500k/ano

### E2 ? CSLL (CRÍTICO)

**Problema:** 9% fixo sem distinção de regime

**Fix:** `csll_engine.py` ? 9% Lucro Real, 9% sobre base presumida (12% comércio / 32% serviços)

**Base legal:** Lei 7.689/88 + alterações

**Critério:** resultado diferente e correcto para presumido vs real

### E3 ? MEI (ALTO)

**Problema:** SM fixo R$1.412 (desactualizado), só comércio

**Fix:** `mei_engine.py` ? SM 2026 = R$1.518, distinção comércio/indústria/serviços

**Base legal:** LC 123/2006 + Resolução CGSN 2026

**Critério:** DAS correcto para as 3 actividades

### E4 ? PIS/COFINS não-cumulativo (ALTO)

**Problema:** créditos opcionais mas não calculados correctamente

**Fix:** `pis_cofins_engine.py` ? créditos sobre entradas tributadas (art. 3º Lei 10.637/2002)

**Critério:** crédito calculado sobre insumos quando regime não-cumulativo

### E5 ? TaxRecovery (MÉDIO)

**Problema:** só detecta ICMS, sem compensação/prazo

**Fix:** expandir para PIS/COFINS pagos a maior, IRPJ/CSLL estimativa antecipada

**Critério:** 3 tipos de crédito recuperável identificados

### E6 ? TaxPlanningEngine (MÉDIO)

**Problema:** `.execute()` usa presunções erradas

**Fix:** substituir por chamada a `simular_regimes`

**Critério:** comparação presumido vs real usa os motores correctos

---

## BLOCO 2 — DADOS NORMATIVOS COMPLETOS

### D1 ? PA alíquota modal (CRÍTICO)

**Problema:** BD tem 0.18, RICMS/PA art. 20 cita 19%

**Fix:** confirmar alíquota vigente 2026 via SEFAZ-PA e actualizar

**Critério:** fonte_legal com artigo confirmado

### D2 ? PMPF SP (ALTO)

**Problema:** `tabela_pmpf` sem dados reais para SP

**Fix:** importar Portaria SRE 89/2025 Anexo II ? valores por marca/embalagem

**Critério:** pelo menos "DEMAIS MARCAS" NCM 22021000 com PMPF real

### D3 ? PMPF RJ (ALTO)

**Problema:** `tabela_pmpf` sem dados reais para RJ

**Fix:** identificar resolução SEFAZ-RJ vigente e importar

**Critério:** pelo menos "DEMAIS MARCAS" NCM 22021000 com PMPF real

#### Decisão Deep ? D2/D3 e encerramento Sprint 2 (2026-05-05)

**D2 (SP):** Para o MVP, não é obrigatório preencher `tabela_pmpf` com todas as marcas/embalagens do Anexo II da Portaria SRE 89/2025. A cobertura operacional para **refrigerantes NCM 2202** (incl. 22021000) em SP fica assegurada pelo **`sefaz_sp_parser`**: MVA subsidiário **66%**, vigências **SRE 89/2025** e continuidade após **SRE 09/2026** (refrigerantes até 2026-06-30 sob SRE 89), com URLs e calibração registadas no próprio parser e referência em `PROTOCOLO.md` (pipeline normativo ? parsers activos). Importação massiva PMPF por marca/embalagem SP mantém-se como **extensão pós-abertura**, em linha com «Cobertura PMPF nacional» na rota Fintech.

**D3 (RJ):** Mantém-se **sem parser PMPF RJ** até haver acto normativo com URL oficial estável e pipeline de importação equivalente ao MG/SP. **Não bloqueia abertura**: quando não há PMPF por UF, a hierarquia de ST já definida em `PROTOCOLO.md` (pipeline normativo) recua para **IVA-ST** (`tabela_mva`), sem inventar valores.

**Sprint 2:** Marcada como **encerrada em 2026-05-05** quanto a D2/D3 com esta decisão documentada; D1 e D4 permanecem itens activos no roadmap conforme abaixo.

### D4 ? DOU automático (ALTO)

**Problema:** INLABS bloqueado por F5, portal dados abertos sem URL estável

**Fix (opção A):** contactar Imprensa Nacional para acesso programático

**Fix (opção B):** implementar cliente `dados.gov.br/dados/api/publico` para descoberta dinâmica de URLs

**Critério:** AG3 detecta publicação nova no DOU sem intervenção humana

---

## BLOCO 3 — INFRAESTRUTURA PRODUÇÃO

### I1 ? Redis Railway (CRÍTICO)

**Problema:** sem Redis, throttle e revogação JWT em memória ? inseguro multi-worker

**Fix:** activar add-on Redis no Railway + definir `REDIS_URL`

**Critério:** `LoginThrottle` e `RevogacaoJti` confirmados com Redis activo

### I2 ? Rotação JWT (ALTO)

**Problema:** `SECRET_KEY` estática ? compromisso permanente se vazar

**Fix:** suporte a `kid` no header JWT + múltiplas chaves activas

**Critério:** rotação de chave sem invalidar tokens activos

### I3 ? Deploy Railway completo (CRÍTICO)

**Problema:** plataforma só existe no PC local

**Fix:** pipeline de deploy automatizado, variáveis de ambiente configuradas

**Critério:** URL pública acessível, migrations rodadas, health check verde

### I4 ? Frontend produção (CRÍTICO)

**Problema:** frontend aponta para localhost

**Fix:** variáveis Vercel apontando para Railway, CORS configurado

**Critério:** utilizador acede via URL pública sem erros

---

## BLOCO 4 — AGENTES NOVOS

### AG-REPARADOR (ALTO)

**Papel:** quando alíquota muda no DOU ? actualiza `tabela_mva`/`tabela_pmpf` ? invalida insights afectados (`superseded=True`) ? notifica utilizador

**Disparo:** AG3 detecta ? AlertaFiscal criado ? AG-REPARADOR age

**Critério:** ciclo completo testado com mock de mudança normativa

### AG-ABERTURA (MÉDIO)

**Papel:** guia utilizador na abertura de empresa (MEI/ME/EPP) via REDESIM

**Critério:** fluxo completo MEI funcional

### AG-ENCERRAMENTO (MÉDIO)

**Papel:** guia baixa de empresa com verificação de pendências fiscais

**Critério:** checklist de pendências gerado correctamente

---

## BLOCO 5 — SEGURANÇA E COMPLIANCE

### S1 ? Penetration test básico (ALTO)

**Fix:** testar endpoints com OWASP Top 10

**Critério:** zero vulnerabilidades críticas

### S2 ? Termos de uso + aviso legal (CRÍTICO)

**Fix:** termos no frontend, aviso "simulação não substitui contador"

**Critério:** utilizador confirma antes de usar

### S3 ? LGPD compliance (ALTO)

**Fix:** política de privacidade, consentimento de dados

**Critério:** documento publicado e consentimento registado

---

## ORDEM DE EXECUÇÃO

SPRINT 1 ? Engines (2 semanas):

E1 IRPJ fix          [CRÍTICO]

E2 CSLL fix          [CRÍTICO]

E3 MEI actualizar    [ALTO]

E4 PIS/COFINS fix    [ALTO]

E6 TaxPlanning fix   [MÉDIO]

SPRINT 2 ? Dados (2 semanas) ? **encerrada 2026-05-05** (D2/D3 via decisão Deep; D1/D4 seguem):

D1 PA confirmar      [CRÍTICO]

D2 PMPF SP           [ALTO] ? baseline parser (ver decisão Deep acima)

D3 PMPF RJ           [ALTO] ? hierarquia IVA-ST até parser (ver decisão Deep acima)

D4 DOU automático    [ALTO]

SPRINT 3 ? Infra + Agentes (1 semana):

I1 Redis Railway     [CRÍTICO]

I3 Deploy Railway    [CRÍTICO]

I4 Frontend prod     [CRÍTICO]

AG-REPARADOR         [ALTO]

SPRINT 4 ? Compliance + Abertura (1 semana):

S1 Pentest           [ALTO]

S2 Termos uso        [CRÍTICO]

S3 LGPD              [ALTO]

I2 Rotação JWT       [ALTO]

AG-ABERTURA          [MÉDIO]

AG-ENCERRAMENTO      [MÉDIO]

---

## ROTA PARA FINTECH (pós-abertura)

FASE FINTECH 1 ? Credibilidade (mês 1-3 pós-abertura):

Assinatura digital contador (ICP-Brasil)

Memorial de cálculo com validade legal

Integração SPED/EFD automática

Certificado digital A1/A3

FASE FINTECH 2 ? Escala (mês 3-6):

API pública para integradores (contabilidades, ERPs)

Cobertura PMPF nacional (todos os estados)

Parser automático portarias SEFAZ (todos os estados)

Multi-tenant com SLA documentado

FASE FINTECH 3 ? Produto Financeiro (mês 6-12):

Antecipação de restituição ST

Crédito fiscal como garantia

Dashboard financeiro integrado

Open Finance / Open Insurance

---

## CHECKLIST DE ABERTURA

Antes de qualquer utilizador real aceder:

- [ ] E1 IRPJ correcto

- [ ] E2 CSLL correcto

- [ ] E3 MEI actualizado

- [ ] E4 PIS/COFINS correcto

- [ ] D1 PA alíquota confirmada

- [x] D2 SP ? baseline ST (`sefaz_sp_parser`, SRE 89/2025 + SRE 09/2026); PMPF marca/embalagem = extensão futura

- [x] D3 RJ ? sem PMPF na BD até parser; uso de IVA-ST conforme hierarquia normativa

- [ ] I1 Redis Railway activo

- [ ] I3 Deploy Railway verde

- [ ] I4 Frontend produção

- [ ] S2 Termos de uso publicados

- [ ] S3 LGPD compliance

---

*Última actualização: 2026-05-05 | HEAD: 1cf6385*

*Critério de abertura: TODOS os itens do checklist ✅*

## NOTA — Backlog pós-Sprint 3
- **Relatório PDF bloqueado**: botão 'Baixar Relatório PDF' chama '/checkout/criar-pagamento' que retorna 404. Endpoint de pagamento não implementado. Resolver antes da abertura ao utilizador real.
