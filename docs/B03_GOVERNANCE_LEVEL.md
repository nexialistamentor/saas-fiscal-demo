# B03 — Nível de Governança (decisão por escrito, antes de código)

## Decisão

B03 usa **git + testes automatizados + log de auditoria leve** (quem rodou,
quando, hash do XML de entrada, hash do resultado). B03 **não** implementa a
cadeia política→decisão→ativação→assinatura nativa usada no B02.

## Por quê

Essa máquina (policy_activations, ratificação, assinatura Ed25519, G4/G5/G13)
só se justifica quando o resultado precisa de servir como **prova forense
perante terceiro externo** (SEFA, auditor, processo administrativo/judicial).
B02 precisava disso porque o resultado final é a prova de proveniência
documental de uma unidade fiscal específica, apresentável a um órgão externo.

B03 produz um **relatório de divergências por item**, para uso interno
(diagnóstico do próprio negócio do cliente da plataforma). Não há, até à data
desta decisão, exigência legal externa concreta que obrigue B03 a produzir
prova forense de terceiro. Se essa exigência surgir no futuro, abre-se uma
nova decisão de governança nesse momento — não se antecipa a máquina pesada
sem necessidade identificada (custo que já consumiu uma sessão inteira em B02).

## O que B03 usa em vez disso

- **Git**: histórico de commits é o rastro de quem mudou o quê.
- **Testes automatizados**: positivo + negativos por jurisdição, conforme
  Fase 2/3 do plano de execução — a prova de correção do motor.
- **Log de auditoria leve**: por execução real de `comparar_item`/orquestração,
  registar `{quem_rodou, quando, hash_sha256(xml_entrada), hash_sha256(resultado)}`.
  Não persiste em tabela com triggers/append-only — fica em log de aplicação
  (ficheiro ou tabela simples sem as garantias append-only/trigger do B02).

## Módulos canónicos confirmados (Fase 0, 2026-11-10)

B03 reaproveita, sem reconstruir, os módulos já confirmados em
`docs/REGISTRO_CANONICO.json`:

| Responsabilidade | Módulo | Status |
|---|---|---|
| Parser-base XML | `app/xml_service.py::ler_xml_unico` | confirmado (via uso) |
| Adaptador de entrada | `app/services/document_ingestion/xml_fiscal_adapter.py` | confirmado |
| Classificação do item | `app/services/document_ingestion/classifier.py` | confirmado |
| Cálculo numérico puro | `app/motor_fiscal.py::MotorFiscal` | confirmado |
| Resolução de regra (UF+NCM+data) | `app/services/tabela_normativa_service.py` | confirmado |
| Resolução de alíquota/MVA | `app/services/fiscal_utils.py::resolver_aliquota_e_mva` | confirmado |
| Comparação de consistência | `app/services/tax_consistency/tax_consistency_engine.py` | confirmado |
| Padrão de orquestração | `app/services/enterprise_g12_st_item_reconciliation.py` | confirmado |

`app/services/enterprise_g14_operational_normative_scope.py` **não** é usado
por B03 — resolve um problema diferente (coerência estrutural de candidatos
normativos + custódia G13), não a resolução de jurisdição que B03 precisa
(já coberta por `tabela_normativa_service`).

## Proibido por desenho (ver REGISTRO_CANONICO.json)

Nenhum PR de B03 cria `motor_fiscal_v2`, `resolver_mva_novo`,
`comparador_B03_alt`, cópia de G12/C5/C6, novo parser XML paralelo a
`xml_service`, ou uso de G14 como resolvedor de regra. Qualquer PR aponta
explicitamente qual módulo existente reutiliza. `tools/check_duplicacao.py`
roda antes de cada commit relevante.

## Revisão desta decisão

Esta decisão é revista se: (a) surgir exigência legal externa concreta de
prova forense para o resultado de B03, ou (b) a cobertura nacional de
jurisdições (`cobertura-nacional-jurisdicoes`, ainda pendente) exigir um
mecanismo de confiança mais forte do que git+testes. Até lá, mantém-se este
nível mínimo.
