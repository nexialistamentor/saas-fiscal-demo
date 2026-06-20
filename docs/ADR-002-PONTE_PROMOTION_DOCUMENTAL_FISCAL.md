# ADR-002 — Ponte de Promotion Documental-Fiscal

**Status:** Proposto

**Data:** 2026-06-19

**Ratificação institucional:** Autoridade Final de Produto (Constituição Art. X)

**Auditoria arquitectural:** Papel de Auditoria Independente

**Evidência:** Produzida por leitura directa de código e documentação

**Pré-requisito:** ADR-001 (Governação da Canonicidade) — este ADR cumpre
  o processo Evidência → Auditoria → Ratificação nele definido.

**Contexto institucional:** PAD-004 (Divergência entre Visão Fundacional
  e Capacidade Institucionalizada) — anexo de fecho genealógico,
  Cenário A confirmado: fragmentação por âmbito V1→V2 declarado, não
  divergência de visão.

---

## 1. CONTEXTO

A genealogia provada em PAD-004 estabeleceu que a plataforma possui
dois pipelines paralelos, intencionalmente separados desde a origem:

Pipeline A — Fiscal Canónico (DocumentoFiscal)

XML → executar_analise_xml → DocumentoFiscal/ItemFiscal
→ InsightEngine → score_global_tributario → dashboard

Pipeline B — Documental (DocumentoIngerido)

PDF/Foto/WhatsApp → classifier → extractor → confidence
→ DocumentoIngerido → HomologacaoDocumental (quando aplicável)
→ [historicamente, sem destino seguinte]

O código do Pipeline B, desde o seu primeiro commit (`24bf9d9`),
declara explicitamente: *"V1 síncrono. V2: service layer transacional
com fila/OCR/ledger."* O elo em falta — promoção de evidência
documental validada para entidade fiscal canónica — foi nomeado, não
esquecido.

Este ADR institucionaliza esse elo, cumprindo o processo definido em
ADR-001: a canonicidade da ponte (o que entra em `DocumentoFiscal`,
quando, e sob que condições) não pode ser declarada por implementação
directa sem primeiro passar por Evidência, Auditoria e Ratificação.

---

## 2. EVIDÊNCIA

### 2.1 — O que existe hoje, com precisão

**`DocumentoFiscalNormalizado`** (dataclass em `normalizer.py`) extrai,
por heurística regex sobre texto plano: `cnpj_emitente`,
`cnpj_destinatario`, `cpf_destinatario`, `chave_acesso`, `cfop`, `ncm`,
`valor_total`, `base_calculo`, `aliquota_icms`, `aliquota_pis`,
`aliquota_cofins`, `data_emissao`. Cada campo é embrulhado em
`CampoNormalizado` (valor, confiança, origem, validado_humano).

**Lacuna de implementação confirmada:** `valor_icms` está declarado
no dataclass mas nunca é populado pelo `normalizar()` actual — só
`aliquota_icms` é preenchida.

**`DocumentoIngerido`** (modelo persistido) guarda `campos_extraidos`
como `list[str]` — apenas os **nomes** dos campos identificados, não
os seus valores estruturados. Após a ingestão, o schema tipado de
`DocumentoFiscalNormalizado` não sobrevive à persistência.

**`DocumentoFiscal`** (entidade fiscal canónica) tem cabeçalho com
`chave_nfe`, `numero_nota`, `data_emissao`, `tipo` (entrada/saída),
`valor_total`, `mva_utilizada`, `uf_emit`, `uf_dest`. `ItemFiscal`
associado tem `ncm`, `cfop`, `valor_produto`, `base_icms`,
`valor_icms`.

**Mapeamento parcial confirmado:** `chave_acesso`, `data_emissao` e
`valor_total` são directamente mapeáveis. `ncm`/`cfop`/valores fiscais
mapeiam para `ItemFiscal`, exigindo síntese de um item único (sem
linhas de produto reais). `numero_nota`, `tipo`, `uf_emit`, `uf_dest`,
`cnpj_emitente`, `cnpj_destinatario` **não têm captação actual** no
normalizer.

### 2.2 — Classificação de tipo, com precisão

`classifier.py` distingue **formato/canal**, não tipo fiscal de
negócio: `pdf_digital`, `pdf_scan`, `image`, `danfe` (único subtipo
fiscal explícito, detectado por marcadores estruturais — "DANFE",
"Chave de Acesso", "CFOP" entre outros), `unknown` (rejeitado).

Um `pdf_digital` ou `image` pode ser uma nota fiscal, um recibo, um
contrato, ou qualquer outro documento — o classificador não distingue
estes casos. Apenas `danfe` é, por desenho, identificável como
fiscal sem ambiguidade adicional.

### 2.3 — Política de confiança existente

`confidence.py`: score ≥ 95 → `AUTO_PROCESSAR`; 70-94 →
`FILA_HOMOLOGACAO`; < 70 → `REJEITAR`. Esta política mede **qualidade
da extracção** (OCR, completude de campos), não **natureza fiscal**
do documento. Os dois julgamentos são distintos e não devem ser
confundidos.

---

## 3. DECISÃO

### 3(a) — `DocumentoIngerido` permanece ledger probatório

`DocumentoIngerido` não é, nem se torna, uma entidade fiscal. É e
permanece o registo imutável de que um documento foi recebido,
classificado, extraído e (quando aplicável) homologado. A promotion
não remove, substitui, nem subordina este registo.

### 3(b) — `DocumentoFiscal` permanece entidade fiscal canónica

`DocumentoFiscal` continua a ser a única entidade reconhecida pelo
Pipeline A — InsightEngine, motor fiscal, score, dashboard. A
promotion não cria um segundo tipo de `DocumentoFiscal`, nem um
caminho alternativo de persistência fiscal.

### 3(c) — Promotion é acto institucional controlado

> A promotion não é extracção.
> A promotion não é homologação.
> A promotion é a criação controlada de uma entidade fiscal canónica
> a partir de evidência documental validada.

A promotion é um terceiro acto, distinto e posterior aos dois
primeiros. OCR extrai. Contador homologa. A plataforma promove —
e só promove quando as condições de 3(d), 3(e) e 3(f) estão
simultaneamente satisfeitas.

### 3(d) — Promotion exige elegibilidade fiscal

Elegibilidade fiscal precede confiança. Um documento só é candidato
a promotion se for, pela sua natureza, um documento fiscal elegível
para materialização como `DocumentoFiscal` — não um contrato, recibo,
comprovativo ou outro documento legítimo mas não-fiscal, e não um
documento fiscal cujos dados extraídos sejam insuficientes para
preencher o mapeamento exigido em 3(f). A classificação de
elegibilidade fiscal é uma decisão distinta da classificação de
formato (`TipoDocumento`) e da política de confiança
(`DecisaoProcessamento`), e deve ser tratada como tal.

### 3(e) — Promotion exige confiança ou homologação

Promotion automática só é admissível para documentos com score ≥ 95
**e** elegibilidade fiscal confirmada **e** mapeamento explícito
completo. Documentos com score entre 70 e 94 nunca promovem antes de
homologação humana concluída e registada (`validado_humano=True`).
Documentos rejeitados (score < 70) nunca promovem, independentemente
de qualquer outra condição.

### 3(f) — Promotion exige mapeamento explícito

Nenhum campo de `DocumentoIngerido`/`DocumentoFiscalNormalizado`
entra em `DocumentoFiscal`/`ItemFiscal` sem correspondência
explicitamente definida e nomeada. JSON bruto nunca é despejado
directamente numa entidade fiscal canónica.

### 3(g) — Promotion preserva rastreabilidade

Toda entidade `DocumentoFiscal` criada por promotion mantém ligação
explícita e consultável ao `DocumentoIngerido` que a originou. A
entidade fiscal canónica nunca fica institucionalmente separada da
evidência documental que a fundamenta.

### 3(h) — Regras negativas explícitas

Para evitar ambiguidade de implementação futura, este ADR declara
explicitamente o que **não** autoriza promotion, isoladamente:

- **Score ≥ 95, sozinho, não autoriza promotion.** Confiança de
  extracção não substitui elegibilidade fiscal nem mapeamento
  explícito.

- **Homologação humana, sozinha, não autoriza promotion.** O parecer
  do contador valida o documento como evidência confiável; não
  declara, por si, que o documento deve tornar-se `DocumentoFiscal`.

- **Documento genérico, mesmo bem extraído ou bem homologado, não
  promove para `DocumentoFiscal`** sem elegibilidade fiscal e
  mapeamento explícito simultaneamente satisfeitos.

---

## 4. PRÉ-CONDIÇÕES TÉCNICAS

Este ADR não autoriza promotion canónica em produção enquanto as
seguintes pré-condições não estiverem resolvidas. Trabalho
preparatório — schema, normalizer, testes, service em modo
não-canónico — pode prosseguir; o que permanece bloqueado é a
promotion válida e reconhecida como canónica até estas três
condições estarem satisfeitas.

**DT-DOC-01** — `DocumentoIngerido` não persiste valores extraídos
estruturados, apenas nomes de campos (`campos_extraidos: list[str]`).
A promotion exige valores tipados disponíveis após a ingestão, não
apenas metadados de evidência.

**DT-DOC-02** — `DocumentoFiscalNormalizado` não cobre todos os
campos exigidos por `DocumentoFiscal` (`numero_nota`, `tipo`,
`uf_emit`, `uf_dest`, CNPJs do emitente/destinatário ausentes do
normalizer; `valor_icms` declarado mas não populado).

**DT-DOC-03** — `classifier.py` distingue formato/canal, não
elegibilidade fiscal de negócio. Não existe hoje um árbitro de
elegibilidade fiscal distinto da classificação de formato.

---

## 5. CONSEQUÊNCIAS

A partir da adopção deste ADR:

- Nenhuma implementação de promotion documental-fiscal é válida sem
  resolver DT-DOC-01, DT-DOC-02 e DT-DOC-03 primeiro.

- Qualquer service de promotion futuro deve demonstrar conformidade
  com 3(a) a 3(h) antes de ser considerado canónico, segundo o
  processo de ADR-001.

- PAD-004 passa a ter caminho institucional de resolução — mas não
  está resolvido por este ADR; está governado por ele.

- O domínio Documental (Constituição Art. IV) e o domínio Tributário
  permanecem distintos; a promotion não os funde, cria uma ponte
  controlada entre eles.

---

## 6. O QUE ESTE ADR NÃO DECIDE

Este ADR não implementa código, não altera schema, não cria service.
Não decide:

- O algoritmo exacto de mapeamento campo a campo

- Como sintetizar `ItemFiscal` a partir de um documento sem linhas
  de produto reais

- Como ou quando `classifier.py` deve evoluir para distinguir
  elegibilidade fiscal

- Se a promotion é síncrona (no momento da homologação/auto-processo)
  ou assíncrona (job posterior)

Estas decisões pertencem à fase de implementação, que só pode
começar depois de DT-DOC-01, DT-DOC-02 e DT-DOC-03 estarem
resolvidas, através de contrato técnico ou ADR subsequente, conforme
o alcance da alteração — cumprindo sempre o processo Evidência →
Auditoria → Ratificação definido em ADR-001.

---

*Este é o segundo ADR da Plataforma Tributária L2. O primeiro decidiu
quem tem legitimidade para declarar canonicidade. Este decide o que
é a canonicidade da ponte entre dois domínios que a visão fundacional
sempre pretendeu unidos — sem fundir o que a evidência provou que
deve permanecer distinto.*

*O conhecimento não está na conversa. Está no repositório.*
