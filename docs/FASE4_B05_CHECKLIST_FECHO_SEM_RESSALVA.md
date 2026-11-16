# SOLVERIS — B05 — Checklist consolidado para fecho sem ressalva (empresa_id=4, NCM 22021000, PA)

**Última atualização:** 16/11/2026

Esta é a lista única e viva do que falta para fechar B05 com cálculo real autorizado. Arquitetura e investigação dos itens abaixo estão documentadas nos ficheiros referenciados; isto aqui é só o estado.

| # | Item | Estado | Referência |
|---|---|---|---|
| 1 | Dependência de revisor humano independente | Resolvido — removida, fundida na ratificação de Miguel | docs/FASE4_CORRECAO_P1_P4_SEM_REVISOR_20261116.md |
| 2 | Natureza da assinatura digital do ato soberano | Resolvido — chave própria de Miguel, sem certificadora externa | docs/SOLVERIS_PRINCIPIO_SOBERANIA_SEM_TERCEIROS.md |
| 3 | Como o motor de cálculo consome a autoridade promovida | Resolvido — arquitetura ratificada (I1-I5) | docs/FASE4_RATIFICACAO_I1_I5_MOTOR_CALCULO_20261116.md |
| 4 | Infraestrutura persistente da base PostgreSQL segregada (hosting, credenciais) | Pendente — decisão ainda não pedida | — |
| 5 | Serviço do escritor ADR-020 (ORM segregado, extração real dos decretos) | Pendente — implementação não iniciada | docs/FASE4_ETAPA3_TAREFAB_PROPOSTA_ESCRITOR_ADR020_20261113.md (arquitetura) |
| 6 | Registo da cadeia de ativação (ActivationDecision/Execution/NormativeActivation/Generation) + proteção 0035/0036 como código de aplicação | Pendente — implementação não iniciada | docs/FASE4_RATIFICACAO_D2_FINAL_PROTECAO_APLICACAO_20261116.md (arquitetura) |
| 7 | Confirmar se CEST e categoria de remetente existem/são extraíveis na ingestão de documentos (NFe XML) — `ItemFiscal` hoje não tem estes campos | Pendente — investigação ainda não aberta | achado em docs/FASE4_RATIFICACAO_I1_I5_MOTOR_CALCULO_20261116.md |
| 8 | Preflight em Postgres descartável (Docker, regras já em vigor) para provar a base em 0024 na prática | Pendente — não iniciado | — |
| 9 | Teste ponta-a-ponta com o caso real `empresa_id=4` em ambiente seguro, antes de produção | Pendente — depende de 4-8 | — |

Nenhuma implementação, migração, conexão a base de dados ou escrita de código foi realizada em nenhum dos itens marcados "Resolvido" acima — resolvido significa decisão de arquitetura ratificada, não execução.

## ATUALIZACAO 2026-11-16 — Item 7 reframed e parcialmente resolvido

Ver docs/FASE4_B05_ACHADO_CATEGORIA_REMETENTE_MVA_DUPLA_20261116.md.

O decreto PA ja custodiado (DOE_PA_20230307_EXTRA_35315.pdf) diferencia MVA
por categoria do remetente: CEST 03.010.01 (refrigerante PET, NCM 2202.10.00)
= 140% (industrial/importador/arrematante/engarrafador) ou 40%
(distribuidor/atacadista). O seed de teste usa 40% sem nunca declarar a
categoria assumida — risco de erro de ~100 pontos percentuais se o remetente
real for industrial.

Item 7 deixa de ser "investigar categoria via compra ou Consulta Tributaria"
e passa a ser: implementar no motor o passo CNPJ do remetente -> CNAE
(Receita Federal, publico, nacional, sem terceiro) -> categoria -> coluna de
MVA correta. Isso e construcao, nao investigacao — a investigacao normativa
esta encerrada.
