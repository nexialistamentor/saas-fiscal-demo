# ADR-007 — Wrapper Canónico `/upload-xml` (DT-FLUXO-01)

**Data:** 2026-07-10
**Estado:** ACEITE
**Autores:** Miguel Moreira, Claude (Anthropic)
**Referências:** DC-002-ESTATUTO-ROTAS-ORFAS.md · commit `0ca02ee` · B13-OPS-12

---

## Contexto

DC-002 (2026-06-20) classificou `POST /upload-xml` como risco L3 alto e BLOQUEANTE para abertura ao utilizador, por duas razões:

1. Rota com persistência mas fora do caminho canónico (`/fiscal/analisar-xml`)
2. Lógica própria de pipeline: gravação em disco, imports directos de `processar_e_persistir_xml`, tratamento interno de `DuplicataFiscalError`

DC-002 prescreveu duas saídas possíveis:
- **(a)** wrapper canónico — rota mantida mas delegando para o pipeline soberano
- **(b)** desactivação — rota removida do router

O documento comprometeu-se a emitir ADR próprio após resolução. Este é esse ADR.

---

## Decisão

Opção **(a)** foi implementada no commit `0ca02ee` (2026-06-24):

`POST /upload-xml` foi reescrito como wrapper canónico sobre `executar_e_registrar_analise_xml` — o pipeline soberano de execução e registo usado no eixo canónico XML.

### Alterações do commit `0ca02ee`

| Antes | Depois |
|-------|--------|
| Gravação em disco (`app/xmls_testes/`) | Sem disco — bytes em memória |
| `processar_e_persistir_xml` (pipeline próprio) | `executar_e_registrar_analise_xml` (pipeline canónico) |
| `DuplicataFiscalError` tratado localmente | Tratamento unificado no pipeline soberano |
| Resposta `{"documento_id": ...}` | Resposta `{"relatorio_id", "empresa_id", "status"}` |
| Imports globais de serviços de XML | Imports locais dentro da função |

---

## Consequências

### Positivas
- `/upload-xml` deixa de ser risco L3 alto sem mitigação
- Qualquer melhoria ao pipeline soberano beneficia automaticamente ambas as rotas
- Scripts de smoke/dedup existentes continuam funcionais com a nova assinatura de resposta
- Risco E1 passa de **alto sem mitigação** para **alto mitigado** (wrapper canónico provado)

### Restrições mantidas
- `/upload-xml` continua reservado a scripts internos — não é caminho canónico para o utilizador final
- O caminho canónico para o frontend permanece `POST /fiscal/analisar-xml` (E2), conforme DC-002
- Esta decisão não altera o estatuto de `/lote/analisar-lote` (DC-002: ferramenta interna, não-bloqueante)

---

## Estado do risco após este ADR

| Endpoint | Risco L3 | Estado |
|----------|----------|--------|
| E1 — `POST /upload-xml` | alto | mitigado por wrapper canónico (ADR-007) |

`Risco L3 alto sem mitigação: 1 → 0`

---

## Referências técnicas

- `DC-002-ESTATUTO-ROTAS-ORFAS.md` — decisão de estatuto original
- `commit 0ca02ee` — implementação do wrapper canónico
- `commit 4a5ddab` — correcção DT-FLUXO-03 (pré-condição do DC-002)
- `docs/B13_OPS_10_MAPA_FUNCIONALIDADES.md` — mapa de endpoints (E1 linha 206)
