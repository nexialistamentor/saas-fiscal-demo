# SOLVERIS — Fase 2, fonte legal para PA / NCM 22021000 — 2026-11-12

## Decisão ratificada

**FONTE OFICIAL IDENTIFICADA; APLICABILIDADE À LINHA GENÉRICA NÃO COMPROVADA.**

Miguel ratificou expressamente esta conclusão e a preservação do bloqueio.
Não preencher `fonte_legal` nem `url_fonte` do registo
`tabela_mva(estado="PA", ncm="22021000")` com uma referência de alcance
mais restrito. Não autorizar cálculo financeiro em consequência da pesquisa.

Esta entrega é documental, sem execução de script de atualização, sem escrita
em `test.db`, sem alterações nos serviços, sem alteração de testes, sem
migrações, sem PostgreSQL de produção, sem merge e sem deploy.

## Fonte verificada

- **Ato:** Decreto Estadual nº 2.588, de 29 de agosto de 2022,
  do Poder Executivo do Estado do Pará; publicado no Diário Oficial do
  Estado em 30 de agosto de 2022.
- **Objeto:** alterações no RICMS/PA (Decreto nº 4.676/2001),
  incluindo tabelas de mercadorias sujeitas à antecipação/ST.
- **Cópia em órgão oficial estadual, com errata:**
  https://www.cge.pa.gov.br/sites/default/files/2023-03/decreto_estadual_n_2588_de_29_08_2022_com_errata.pdf
- **Trecho inspecionado:** Apêndice I do Anexo I, grupo
  'Cervejas, chopes, refrigerantes, águas e outras bebidas',
  itens 9.0, 9.1, 9.2 e 10.0 (página 6 do PDF, contagem física).
- **CEST e especificação:**
  - `03.010.00` — refrigerante em vidro descartável;
  - `03.010.01` — refrigerante em embalagem PET;
  - `03.010.02` — refrigerante em lata.
  Esses três itens abrangem `2202.10.00` e `2202.99.00`.
- **Margens na tabela citada:** 140% para industrial, importador,
  arrematante e engarrafador; **40% para distribuidor, depósito ou
  estabelecimento atacadista** nas categorias acima, segundo as colunas de
  remetente e de alíquota interestadual. O item 10.0 ('demais
  refrigerantes') apresenta outra margem, **70%** na coluna de
  distribuidor/depósito/atacadista.

A existência da norma e da margem de 40% é comprovável. Isso **não**
comprova que uma linha sem CEST, embalagem e tipo de remetente corresponda
ao caso normativo específico. O documento citado não foi adotado como
`fonte_legal` do registo genérico.

## Confronto com a linha existente no SQLite

Dado reportado e efetivamente testado na Fase 1:

- `estado="PA"`, `ncm="22021000"`;
- `mva=40.0`, `aliquota_interna=0.18`;
- `vigencia_inicio=2024-01-01`, `vigencia_fim=NULL`;
- `nivel_confianca_fonte="oficial"`;
- `fonte_legal=NULL`, `url_fonte=NULL`.

A linha não identifica CEST, embalagem, tipo de remetente, operação
concreta ou fundamento independente para a alíquota interna de 18% na data
de referência. Assim, nem a margem de 40% nem a alíquota de 18% podem ser
consideradas **universalmente aplicáveis** à chave genérica PA/NCM.
A confiança declarada pelo seed não substitui esses elementos.

Não se alterou o `seed_mva.py`, nem se presumiu alíquota alternativa.
A validade material para um documento concreto continua a exigir exame
específico da versão normativa vigente na data do facto gerador.

## Fecho funcional preservado

- Cadastro PA/NCM existente: **sim**.
- Fonte oficial relacionada ao grupo: **identificada**.
- Aplicabilidade à linha genérica: **não comprovada**.
- `fonte_legal` na base real: **permanece NULL**.
- `autoridade_normativa_verificada`: **False**.
- `calculo_autorizado`: **False**.
- Resposta prevista pela guarda da Fase 1:
  `REGRA_CADASTRADA_AUTORIDADE_NAO_COMPROVADA`,
  `motivo="fonte_legal_ausente"`.
- Isolamento para outras UFs e NCMs: **inalterado**.

## Testes e limites desta entrega

A Fase 2 foi iniciada **exatamente** em
`f868f21ef526743073d7e72192f9a0ff1ea3e95d`, HEAD validado
da Fase 1. Não houve alteração programática nesta Fase 2.
A prova do predecessor, executada em Windows, é
**72 testes PASS** e **catraca anti-duplicação PASS**; a mesma
árvore de código e testes foi utilizada. Não se declara uma
nova execução independente da suíte ou uma prova de alteração
de bytes da base local nesta etapa documental.

Esta missão encerra a investigação e decisão **apenas para PA /
NCM 22021000**, com resultado condicionado e sem preencher campos
normativos não fundamentados. Nenhuma declaração de ampliação de
cobertura jurisdicional é feita.
