# ROADMAP SOBERANO — Plataforma L2 → FinTech
**Auditado em:** 2026-05-12  
**HEAD:** f2e569b  
**Testes:** 104 passando (87 fiscais + 17 domínio financeiro)  
**Princípio:** persistir primeiro → enriquecer depois → só então usar inteligência

---

## ESTADO ACTUAL — O QUE ESTÁ COMPLETO

| Módulo | Estado | Notas |
|--------|--------|-------|
| Engines fiscais (IRPJ, CSLL, MEI, PIS/COFINS, CPF, TaxPlanning) | ✅ Produção | Motor soberano — nunca delegar a API externa |
| Dashboard frontend (Vercel) + Backend (Railway) | ✅ Produção | |
| Compliance LGPD (termos, consentimento, my-data, eliminação) | ✅ Produção | |
| Redis centralizado + JWT multi-chave | ✅ Produção | |
| AG-REPARADOR, AG-ABERTURA, AG-ENCERRAMENTO | ✅ Produção | |
| Assistente fiscal conversacional | ✅ Produção | |
| Security headers, dependências pinadas | ✅ Produção | |
| Alembic chain soberana (0000→0001→0002→0003) | ✅ Produção | Rebase concluído |
| Modelo Pagamento + PagamentoTentativa | ✅ Produção | Ledger auditável |
| PagamentoService (máquina de estados, idempotência, ledger) | ✅ Código | Aguarda credenciais MP |
| Parsers (DOU, SEFAZ MG/SP, InLabs) | ✅ Código | |
| Pipeline normativo | ✅ Código | |
| Núcleo regulatório V1 (PerfilContador, HomologacaoDocumental, API contador) | ✅ Produção | HomologacaoService + assinatura lógica SHA-256 |
| Núcleo empresarial V1 (CNAE, regime tributário, formalização stateless, extensão `empresas`) | ✅ Produção | `cnae_engine`, `regime_engine`, `formalizacao_router`, migration `0008` |
| Serviço PDF | ✅ Código | A auditar |

---

## BLOCOS A COMPLETAR — POR PRIORIDADE

---

### 🔴 BLOCO 1 — Núcleo Financeiro (próximo a desbloquear)
**Dependência:** credenciais Mercado Pago (sandbox) — aguardar amanhã

| Tarefa | Ficheiro | Estado |
|--------|----------|--------|
| Camada gateway abstrata | `app/services/gateways/base_gateway.py` | ❌ |
| Adaptador Mercado Pago | `app/services/gateways/mercadopago_gateway.py` | ❌ |
| Factory de gateways | `app/services/gateways/gateway_factory.py` | ❌ |
| Router checkout | `app/routers/checkout_router.py` | ❌ |
| Webhook MP (validação activa) | `app/routers/webhook_router.py` | ❌ |
| Variáveis Railway | `MERCADO_PAGO_ACCESS_TOKEN`, `PUBLIC_KEY`, `WEBHOOK_SECRET` | ❌ |
| Testes integração pagamento | `tests/test_checkout_integration.py` | ❌ |

**Princípio:** webhook nunca é verdade final — validar activamente via API MP

---

### 🟢 BLOCO 2 — Pipeline Documental Soberano V1 — PRODUÇÃO
**Commit:** 24bf9d9

| Módulo | Estado |
|--------|--------|
| `classifier.py` | ✅ Produção |
| `extractor.py` | ✅ Produção |
| `confidence.py` | ✅ Produção |
| `normalizer.py` | ✅ Produção |
| `audit.py` | ✅ Produção |
| `ingestion_router.py` | ✅ Produção |
| Migration `0004_documentos_ingeridos` | ✅ Produção |

**Escopo V1 — limites documentados:**

- ✅ Pipeline determinístico auditável
- ✅ Deduplicação por SHA-256
- ✅ Trilha probatória (EvidenciaDocumental)
- ❌ OCR automático (requer pytesseract + Tesseract)
- ❌ Antifraude ML
- ❌ Assinatura ICP-Brasil
- ❌ Persistência S3/distribuída
- ❌ Fila assíncrona

---

### 🟢 BLOCO 3 — Núcleo Regulatório (Contadores Parceiros) — PRODUÇÃO
**Commit:** 5eab23a  
**Dependência:** Bloco 2 satisfeito (contador homologa o que a plataforma processou)

| Tarefa | Ficheiro | Estado |
|--------|----------|--------|
| Modelo `PerfilContador` (CRC, UF, status, reputação) | `app/models.py` | ✅ Produção |
| Modelo `HomologacaoDocumental` (parecer + assinatura lógica V1) | `app/models.py` | ✅ Produção |
| Migration perfis contador | `migrations/versions/0005_create_perfis_contador.py` | ✅ Produção |
| Migration homologações documentais | `migrations/versions/0006_create_homologacoes_documentais.py` | ✅ Produção |
| API parceiro contador | `app/routers/contador_router.py` | ✅ Produção |
| Fluxo homologação (fila → parecer → assinatura lógica SHA-256) | `app/services/homologacao_service.py` | ✅ Produção |
| `assinatura_service.py` modular (PKI / rotas dedicadas) | — | 🔮 Fase futura |
| Assinatura ICP-Brasil V2 | — | 🔮 Fase futura |
| Testes domínio homologação | `tests/test_homologacao_service.py` | ✅ Produção |

**Escopo V1 — limites documentados:**

- ✅ Perfil regulatório do contador (CRC, estados pendente/aprovado/suspenso, reputação)
- ✅ Fila de homologação documental com uma homologação activa relevante por documento (regra no serviço V1)
- ✅ Decisão aprovado/rejeitado com parecer textual auditável
- ✅ Assinatura lógica V1 (SHA-256 sobre parecer + identidades + timestamp — não PKI)
- ✅ Endpoints de assumir homologação e registar parecer (`contador_router`)
- ❌ Assinatura criptográfica / ICP-Brasil / e-CNPJ
- ❌ Serviço `assinatura_service.py` separado da lógica já encapsulada em `HomologacaoService`
- ❌ Portal UI dedicado ao parceiro (fora do núcleo API V1)

**Princípio:** contador não bloqueia operação — é camada premium de confiança

---

### 🟢 BLOCO 4 — Núcleo Empresarial V1 — PRODUÇÃO
**Commit:** f2e569b (stack: CNAE → regime → formalização)  
**Dependência:** independente — V1 stateless; persistência via fluxos existentes de empresa

| Tarefa | Ficheiro | Estado |
|--------|----------|--------|
| Motor de enquadramento CNAE (keywords + parser soberano) | `app/services/cnae_engine.py` | ✅ Produção |
| Motor regime tributário (MEI/Simples/LP/LR + Fator R + comparação) | `app/services/regime_engine.py` | ✅ Produção |
| Router formalização stateless (recomendar CNAE, comparar regimes, simular empresa) | `app/routers/formalizacao_router.py` | ✅ Produção |
| Migration extensão `empresas` (CNAE, localização, porte, tributário, métricas) | `migrations/versions/0008_expand_empresa_nucleo_empresarial.py` | ✅ Produção |
| Checklist abertura empresa (estrangeiros incluídos) | `app/services/abertura_service.py` | 🔍 Auditar AG-ABERTURA |
| Viabilidade municipal | `app/services/viabilidade_service.py` | ❌ |
| Wizard persistido multi-passo / portal guiado | — | 🔮 Fase futura |

**Escopo V1 — limites documentados:**

- ✅ Recomendação CNAE heurística (sem ML)
- ✅ Comparação de regimes com Fator R onde aplicável
- ✅ Endpoints stateless sob `/formalizacao/*`
- ✅ Modelo `empresas` enriquecido para perfil operacional (migration `0008`)
- ❌ Viabilidade municipal e integrações prefectura
- ❌ OCR ou ingestão automática de contrato social na formalização

---

### 🟢 BLOCO 5 — Observabilidade e Resiliência (pós-abertura)
| Tarefa | Estado |
|--------|--------|
| Sentry (monitorização erros produção) | ❌ |
| `/payment-health` — monitor tentativas/falhas | ❌ |
| ReconciliacaoService (pending presos, webhooks perdidos) | ❌ |
| Pentest externo | ❌ |
| Testes de integração com PostgreSQL real | ❌ |
| Unificação `routers/` vs `routes/` | ❌ |
| Migração `legacy/` → arquivo ou remoção | ❌ |

- [ ] `CheckConstraint` comprimento CNPJ em `empresas` — evitar chaves contaminadas

---

## ARQUITECTURA DOS 4 NÚCLEOS

```
Plataforma Soberana L2
│
├── Núcleo Fiscal          ← COMPLETO (motor soberano)
│   ├── motor_fiscal.py
│   ├── tax_engines/
│   └── parsers/
│
├── Núcleo Financeiro      ← EM CONSTRUÇÃO
│   ├── pagamento_service.py ✅
│   ├── gateways/          ← próximo
│   └── reconciliacao_service.py
│
├── Núcleo Documental      ← A AUDITAR → CONSTRUIR
│   ├── parsers/ (existente)
│   ├── document_ingestion/ (novo)
│   └── [contador homologa baixa-confiança]
│
├── Núcleo Empresarial     ← PRODUÇÃO V1 (stateless + empresas expandido)
│   ├── cnae_engine.py
│   ├── regime_engine.py
│   └── formalizacao_router.py
│
└── Núcleo Regulatório     ← PRODUÇÃO V1 (API + homologação)
    ├── contador_router.py
    ├── homologacao_service.py
    └── assinatura_service.py (PKI — futuro)
```

---

## PRINCÍPIOS INEGOCIÁVEIS

| Princípio | Aplicação |
|-----------|-----------|
| `Numeric(10,2)` para dinheiro | Nunca `Float` |
| `idempotency_key` obrigatório em pagamentos | UNIQUE no DB |
| Webhook valida activamente via API MP | Nunca confia em notificação passiva |
| `user.consulta_paga` é estado derivado | Não é verdade financeira |
| PostgreSQL Railway = fonte da verdade | SQLite = descartável |
| Um commit = uma intenção | Mensagem descritiva |
| Nunca commitar `.env` | Variáveis só no Railway |
| PowerShell usa `;` não `&&` | Ambiente Windows |
| Testar via código antes de teste manual | Sempre |
| Motor fiscal = código | Nunca delegar cálculo a API externa |
| OCR < 95% confiança → fila humana | Contador valida, não corrige |
| Contador assina — não opera | Camada premium, não dependência |

---

## PRÓXIMA SESSÃO

**Amanhã (credenciais MP disponíveis):**
1. Adicionar variáveis Railway (`MERCADO_PAGO_ACCESS_TOKEN`, `PUBLIC_KEY`, `WEBHOOK_SECRET`)
2. Criar `app/services/gateways/base_gateway.py`
3. Criar `app/services/gateways/mercadopago_gateway.py`
4. Criar `app/services/gateways/gateway_factory.py`
5. Criar `app/routers/checkout_router.py`

**Hoje (sem credenciais MP):**
1. Auditar `app/services/parsers/` — o que já lê PDF/prints?
2. Auditar `app/services/pdf*.py` — capacidade actual
3. Definir schema `document_ingestion` antes de construir
