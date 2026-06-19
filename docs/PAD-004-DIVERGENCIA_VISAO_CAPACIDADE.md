# PAD-004 — Divergência entre Visão Fundacional e Capacidade Institucionalizada

**Versão:** 1.0

**Data:** 2026-06-18

**Natureza:** Descoberta estratégica. Não é dívida técnica. Não é ADR.

  Não propõe correcção. Investiga se a instituição que existe hoje

  ainda é a instituição que foi originalmente concebida.

**Origem:** Observação directa de Miguel, fundador e autoridade de produto,

  confrontada com evidência de código já produzida no MAPA_AUTORIDADES_L2.md

  e no PM_L2_001_PRE_MORTEM_ESTRATEGICO.md.

---

## A PERGUNTA QUE NENHUM OUTRO DOCUMENTO RESPONDEU

Todos os documentos anteriores desta sequência — Mapa de Realidade,

Mapa de Domínios, Mapa de Autoridades, Pré-Mortem, ADR-001 — auditam

o que existe e como se comporta.

Nenhum deles responde a uma pergunta diferente, e anterior a todas:

> A Plataforma Tributária L2 que existe hoje ainda é a plataforma

> que foi originalmente concebida?

Esta pergunta não nasce da leitura de código. Nasce da memória de

quem desenhou a visão original, confrontada com a evidência do que

o código hoje efectivamente faz.

---

## VISÃO FUNDACIONAL DECLARADA

Segundo relato directo de Miguel nesta sessão, a evolução pretendida

da plataforma seguiu esta sequência:

**Fase 1 — origem:** análise de XML para detectar ICMS-ST pago em

duplicado.

**Fase 2 — expansão:** ao identificar que a dor real do empresário,

MEI e cidadão comum era mais ampla do que o XML, a visão evoluiu para

aceitar qualquer documento relevante — PDF, foto, WhatsApp, documento

digitalizado — como entrada legítima para a mesma inteligência fiscal.

A cadeia conceptual da visão fundacional, conforme descrita:

Documento (qualquer tipo)

↓

Extracção

↓

Compreensão

↓

Conhecimento

↓

Aprendizagem

↓

Recomendação

---

## REALIDADE PROVADA POR EVIDÊNCIA DE CÓDIGO

A auditoria desta sessão (MAPA_AUTORIDADES_L2.md, linhas 1, 6 e 9-11)

provou que existem hoje **dois pipelines paralelos e não conectados**:

PIPELINE A — XML (DocumentoFiscal)

XML

↓

executar_analise_xml

↓

DocumentoFiscal / ItemFiscal

↓

InsightEngine (16+ analisadores)

↓

score_global_tributario_service

↓

AlertaFiscal / Insight / InteligenciaSnapshot

↓

Dashboard / Agentes / Assistente

PIPELINE B — Documental Universal (DocumentoIngerido)

PDF / Foto / WhatsApp / Documento

↓

classifier → extractor → confidence (score de OCR)

↓

DocumentoIngerido

↓

HomologacaoDocumental (parecer do Contador CRC)

↓

[FIM — nenhuma ligação adiante identificada]

**Evidência directa de isolamento total:** zero ficheiros no `app/`

importam `DocumentoIngerido` e `InsightEngine` no mesmo módulo. O

cruzamento de código confirma 0 ocorrências.

O único "score" presente no Pipeline B é `score_confianca` — qualidade

da extracção OCR — e não tem relação com o `score_global_tributario`

que o Pipeline A produz.

---

## O QUE ISTO SIGNIFICA, COM RIGOR

Não significa que o Pipeline B falhou. Significa que **nunca foi

desenhada a ponte** entre os dois mundos. Um documento submetido por

foto pode ser classificado, extraído, e até homologado formalmente

por um Contador CRC com parecer assinado e assinatura lógica auditável

— e, depois disso, **nada acontece**. O trabalho de homologação, que

é a parte mais cara e formal de todo o domínio documental, termina

sem nunca alimentar a camada de inteligência fiscal que constitui o

propósito declarado da Constituição (Art. I — "a plataforma possui

autoridade para calcular, avaliar, comparar e recomendar

autonomamente").

A Fase 2 da visão fundacional (upload universal, dor real do cidadão

comum) nunca atingiu paridade arquitectural com a Fase 1 (XML). Não

foi abandonada — foi anexada como domínio paralelo, com início

funcional próprio e sem destino institucional próprio.

---

## O QUE A AUDITORIA NÃO PERMITE CONCLUIR (E É IMPORTANTE DIZÊ-LO)

Esta descoberta **não** prova que:

- A visão original foi abandonada deliberadamente

- O domínio documental está mal construído

- É necessário reconstruir qualquer parte do sistema

- Existe um motor de aprendizagem perdido ou removido — esta hipótese

  foi investigada nesta sessão por varredura completa de histórico

  Git (commits apagados, mensagens de commit, branches, stashes) e

  **não encontrou evidência** de tal componente ter existido e

  desaparecido. O que existe e funciona hoje sob o nome InsightEngine

  é, com alta probabilidade, a evolução directa do motor de

  inteligência fiscal descrito em documentação histórica de fases

  anteriores do projecto (referida nesta sessão como "BLOCO 4"),

  não um componente diferente que tenha sido perdido.

O que a auditoria prova, com evidência directa, é apenas isto:

> Existe uma divergência observável entre a visão fundacional

> (conhecimento extraído de qualquer documento) e a capacidade

> actualmente institucionalizada (conhecimento extraído apenas de XML).

---

## AS PEÇAS EXISTEM — A PERGUNTA É SE ESTÃO DESCONECTADAS OU NUNCA FORAM UNIDAS

A auditoria completa desta sessão confirma que a plataforma possui,

hoje, todas as peças que a visão fundacional exigiria:

- Motor fiscal determinístico (Domínio Tributário)

- Domínio documental com OCR, classificação e homologação

- InsightEngine com 16+ analisadores

- Camada de agentes (mesmo que inactiva — DT-AGENTE-01)

- Base normativa (mesmo que fragmentada — PM-05)

- Assistente conversacional que já delega para múltiplos perfis

O que não existe é o **passo de ponte**: um mecanismo que, após a

homologação de um documento no Pipeline B, materialize os campos

validados em estruturas que o Pipeline A (e por extensão o

InsightEngine) consiga ler.

Este passo não existe hoje no código, em nenhuma forma, completa ou

parcial.

---

## A PERGUNTA QUE FICA EM ABERTO PARA A PRÓXIMA SESSÃO

> A Plataforma Tributária L2 continua a ser a mesma instituição que

> Miguel pretendia construir, apenas fragmentada em dois domínios que

> ainda não foram unidos — ou a evolução da implementação divergiu da

> visão original de uma forma que exige reavaliação estratégica, não

> apenas uma ponte técnica?

Esta pergunta não tem resposta nesta sessão. A evidência recolhida

aponta para a primeira hipótese (fragmentação, não divergência de

intenção) — mas confirmá-la com rigor exige investigação dedicada,

não uma conclusão apressada dentro de um documento que já cobriu

canonicidade, autoridade e mecanismos de falha.

---

## RELAÇÃO COM OS DOCUMENTOS EXISTENTES

PAD-004 não é um oitavo mecanismo de falha do PM_L2_001 — é uma

descoberta de natureza diferente: questiona a fidelidade entre visão

e implementação, não o comportamento técnico de componentes já

existentes.

PAD-004 referencia ADR-001: qualquer decisão futura sobre como

conectar o Pipeline A e o Pipeline B — se essa for a conclusão da

investigação — deve cumprir o processo Evidência → Auditoria →

Ratificação definido em ADR-001.

PM_L2_001 pode referenciar PAD-004 como contexto relevante para

PM-04 (Fragmentação Institucional) e PM-06 (Recomendação sem

Execução), sem que PAD-004 dependa estruturalmente de nenhum dos dois.

---

## NOTA PARA INVESTIGAÇÃO FUTURA — RELAÇÃO COM PM-07

PM-07 classifica a dependência humana em Legítima, por Insuficiência

de Evidência, Arquitectural ou Artificial. PAD-004 sugere uma quinta

leitura possível, ainda não confirmada: parte da dependência humana

classificada como "Arquitectural" no domínio documental pode não ser

causa da fragmentação entre Pipeline A e Pipeline B — pode ser

consequência dela. Se a homologação humana é hoje o destino final do

documento (em vez de uma etapa intermédia rumo a conhecimento e

recomendação), a intervenção humana ocupa um lugar que a visão

fundacional não lhe destinava como permanente.

Esta é uma hipótese de investigação, não uma conclusão. Fica registada

para ser testada na próxima sessão, junto com a pergunta genealógica

central deste documento.

---

*Este documento não conclui se a visão fundacional foi mantida,

fragmentada ou desviada. Identifica, com evidência, que a pergunta

nunca tinha sido feita — e que agora precisa de ser investigada

deliberadamente, antes de qualquer ADR que decida o futuro do

domínio documental.*

*O conhecimento não está na conversa. Está no repositório.*
