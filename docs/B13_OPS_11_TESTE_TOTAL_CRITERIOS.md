# B13-OPS-11 — Critérios do Teste Total

**Data:** 2026-06-29  
**Referência:** B13-OPS-10 — `docs/B13_OPS_10_MAPA_FUNCIONALIDADES.md`

---

## Regra fundamental

**1 funcionalidade prometida = 1 teste mínimo obrigatório.**

Sem teste → estado = `nao_provado` → não existe para L3.

---

## Critérios por estado

| Estado | Critério mínimo | Acção |
|--------|----------------|-------|
| `provado` | Pelo menos UMA das evidências abaixo + suite verde | Manter + regressão |
| `parcial` | Evidência existe mas incompleta ou < 80% dos casos | Completar |
| `nao_provado` | Sem nenhuma evidência | Criar teste obrigatório |
| `bloqueado` | Dependência externa ou decisão pendente | Documentar ADR |
| `falso_positivo` | Endpoint existe mas não faz o que declara | ADR + correcção |

---

## Tipos de evidência aceites (por ordem de força)

| Tipo | Descrição | Suficiente sozinho? |
|------|-----------|-------------------|
| E2E/manual documentado | Teste manual registado em PILOTO_0_FEEDBACK.md | Sim, se documentado |
| Teste integração endpoint | `TestClient` com auth + request + assert status + assert body | Sim |
| Teste contrato/schema | Valida estrutura da resposta contra schema Pydantic | Parcial |
| Teste unitário do motor | Testa o serviço isolado, sem endpoint | Parcial |
| Evidência de produção | curl/log de Railway com resposta esperada | Sim, se registado |

**Teste unitário isolado não prova funcionalidade pública.**  
Para passar de `parcial` para `provado`, endpoint público exige teste de integração ou evidência E2E.

---

## Critério adicional para endpoints públicos

Para funcionalidade com endpoint público (`/fiscal/*`, `/imposto/*`, `/formalizacao/*`, etc.):

provado = endpoint existe  
+ auth/termos correctos validados  
+ resposta esperada validada (status + body mínimo)  
+ erro esperado validado (4xx para input inválido)

Endpoint que só tem teste do motor subjacente → `parcial`, não `provado`.

---

## Prioridade de execução

### P0 — Risco alto (6 funcionalidades)

Normativa sem hash a alimentar cálculo fiscal real:

- G1 POST /imposto/calcular
- G2 POST /imposto/simular-ano  
- G3 POST /imposto/simples-nacional
- D2 POST /formalizacao/comparar-regimes
- D3 POST /formalizacao/simular-empresa
- O1 POST /perguntar (heurística fiscal sem fonte)

### P1 — Não provados (13 funcionalidades)

- A2 GET /health/ready
- A3 GET /
- A4 GET /system/metrics
- E4 DELETE /fiscal/analise/cancelar/{job_id}
- J8 GET /dashboard/alertas/timeline/{id}
- J9 GET /dashboard/alertas/agentes/{id}
- J10 PATCH /dashboard/alertas/silenciar/{id}
- J11 PATCH /dashboard/alertas/restaurar/{id}
- J12 GET /dashboard/alertas/grafico/{id}
- N2 GET /estoque/divergencias
- E5 POST /lote/analisar-lote (auditabilidade)

### P2 — Parciais críticos (41 funcionalidades)

- Domínio I — 18 endpoints inteligência
- Domínio J — dashboard parcial
- Domínio D — formalização parcial

---

## Critério de conclusão OPS-11

Suite completa verde

todos os 90 itens com estado "provado"

nenhum risco L3 "alto" sem mitigação documentada

Railway /health OK

working tree limpa

---

Só após este critério: Piloto 0 manual + PILOTO_0_FEEDBACK.md.
