# CT-DOC-001 — Contrato Técnico da Promotion Documental-Fiscal

**Versão:** 1.0
**Data:** 2026-06-19
**Natureza:** Contrato técnico. Traduz ADR-002 em critérios verificáveis.
  Não decide legitimidade institucional (já decidida em ADR-001 e
  ADR-002). Define o que deve ser verdade no código para que a
  promotion seja considerada válida.
**Pré-requisito:** ADR-001, ADR-002
**Base factual:** auditoria directa de código — `audit.py`,
  `ingestion_router.py`, `models.py`, `0004_create_documentos_ingeridos.py`,
  `test_document_audit.py`. Vocabulário fechado, sem variações
  estruturais a migrar.

---

## PRINCÍPIO DO CONTRATO

Este contrato não introduz decisão nova. Aplica ADR-002 a campos,
tipos e testes concretos. Onde o contrato for omisso, ADR-002
prevalece. Onde ADR-002 for omisso sobre detalhe técnico, este
contrato preenche — mas nunca o contrário.

---

## 1. CAMPOS MÍNIMOS EXIGIDOS PARA PROMOTION

Promotion só é elegível quando os seguintes campos estão presentes,
com valor não-nulo, em `DocumentoFiscalNormalizado`:

**Obrigatórios para qualquer promotion:**
- `chave_acesso` — mapeia para `DocumentoFiscal.chave_nfe`
- `data_emissao` — mapeia para `DocumentoFiscal.data_emissao`
- `valor_total` — mapeia para `DocumentoFiscal.valor_total`

**Obrigatórios para síntese de `ItemFiscal`:**
- `ncm`
- `cfop`
- pelo menos um de: `base_calculo`, `valor_icms`

Se qualquer campo obrigatório estiver ausente (`None` em
`CampoNormalizado.valor`), o documento não é elegível para promotion,
independentemente do score de confiança ou estado de homologação —
conforme 3(d) e 3(h) de ADR-002.

**Importante:** a presença destes campos é condição **necessária**,
não suficiente. A suficiência exige também evidência fiscal forte,
conforme secção 5.

**Campos com mapeamento ainda não implementado** (ver DT-DOC-02,
secção 3): `numero_nota`, `tipo` (entrada/saída), `uf_emit`, `uf_dest`,
`cnpj_emitente`, `cnpj_destinatario`. Promotion não pode ser
considerada canónica em produção enquanto estes campos não tiverem
captação no normalizer ou justificação explícita de ausência aceitável.

---

## 2. MAPEAMENTO DocumentoFiscalNormalizado → DocumentoFiscal / ItemFiscal

### 2.0 — Tipo numérico fiscal

Todo campo monetário ou de base de cálculo deve ser convertido de
`str` para um tipo numérico fiscal canónico (`Decimal` ou
equivalente de precisão fixa) — **nunca `float`**. Esta regra aplica-se,
sem excepção, a: `valor_total`, `base_calculo`, `valor_icms`,
`valor_produto`, `base_icms`. Em domínio fiscal, `float` introduz
erro de arredondamento silencioso e é incompatível com a disciplina
já estabelecida na plataforma (`Numeric(10,2)`, nunca `Float`).

### 2.1 — Cabeçalho (`DocumentoFiscal`)

| Campo normalizado | Campo `DocumentoFiscal` | Transformação |
|---|---|---|
| `chave_acesso.valor` | `chave_nfe` | Validar 44 dígitos antes de mapear |
| `data_emissao.valor` | `data_emissao` | Parse `str` (DD/MM/YYYY) → `Date` |
| `valor_total.valor` | `valor_total` | Parse `str` → `Decimal` (ver 2.0) |
| — | `numero_nota` | **Sem origem hoje — DT-DOC-02** |
| — | `tipo` | **Sem origem hoje — DT-DOC-02** |
| — | `uf_emit`, `uf_dest` | **Sem origem hoje — DT-DOC-02** |
| — | `mva_utilizada` | Não vem do documento — derivado pelo motor fiscal após promotion, fora do escopo deste contrato |
| (contexto da ingestão) | `empresa_id` | Vem de `DocumentoIngerido.empresa_id`, não do normalizer |
| (gerado na promotion) | `conteudo_sha256` | Reutilizar `DocumentoIngerido.conteudo_sha256` — mesma evidência, mesmo hash |

### 2.2 — Item sintético (`ItemFiscal`)

Como o documento não tem linhas de produto reais identificadas pelo
normalizer actual, a promotion sintetiza **um único `ItemFiscal`**
representando o documento como item agregado:

| Campo normalizado | Campo `ItemFiscal` | Transformação |
|---|---|---|
| `ncm.valor` | `ncm` | Validar 8 dígitos |
| `cfop.valor` | `cfop` | Directo |
| `valor_total.valor` | `valor_produto` | Reutiliza o total do documento (item único); `Decimal` (ver 2.0) |
| `base_calculo.valor` | `base_icms` | Parse `str` → `Decimal` (ver 2.0) |
| `valor_icms.valor` | `valor_icms` | `Decimal` (ver 2.0). **Hoje nunca populado pelo normalizer — DT-DOC-02** |

**Nota de força probatória (obrigatória, não opcional):**
`ItemFiscal` sintetizado por promotion **não possui a mesma força
probatória** que item extraído de XML estruturado. É uma aproximação
declarada de um documento agregado, não uma linha de produto real.

Qualquer consumidor de `ItemFiscal` — InsightEngine, motores de
análise, dashboards — deve poder distinguir item sintético de item
real (ver secção 4, campo de proveniência) e deve poder degradar,
excluir ou sinalizar explicitamente análises que dependam de
granularidade real de item quando o item subjacente for sintético.
Tratar item sintético como equivalente a item real, sem esta
distinção, viola este contrato.

---

## 3. PERSISTÊNCIA EXIGIDA EM DocumentoIngerido (DT-DOC-01)

**Estado actual provado por evidência:** `campos_extraidos` é
`list[str]` — vocabulário fechado de 13 nomes de campo
(`cnpj_emitente`, `cnpj_destinatario`, `cpf_destinatario`,
`chave_acesso`, `cfop`, `ncm`, `valor_total`, `base_calculo`,
`aliquota_icms`, `valor_icms`, `aliquota_pis`, `aliquota_cofins`,
`data_emissao`). Sem valores, sem confiança, sem origem por campo.

**Exigência do contrato:** `DocumentoIngerido` deve passar a
persistir, para cada campo do vocabulário fechado, a estrutura
completa de `CampoNormalizado` (valor, confiança, origem,
validado_humano), não apenas o nome.

**Forma mínima aceitável** (nova coluna ou estrutura dentro de coluna
existente — decisão de implementação, não deste contrato):

```json
{
  "chave_acesso": {"valor": "...", "confianca": 0.97, "origem": "regex", "validado_humano": false},
  "valor_total":  {"valor": "1234.56", "confianca": 0.91, "origem": "ocr", "validado_humano": false},
  ...
}
```

**Compatibilidade com registos existentes:** não há legado estrutural
a converter automaticamente — o vocabulário é fechado e sem variações
históricas detectadas na auditoria de código. No entanto, registos já
persistidos com `campos_extraidos: list[str]` permanecem válidos
como evidência histórica e **não são elegíveis para promotion** sem
reprocessamento explícito dos bytes originais (fora do escopo deste
contrato). A implementação deve ser **retrocompatível na leitura**:
não pode quebrar consulta ou exibição de registos antigos, mesmo que
estes nunca venham a ser promovidos sem reprocessamento.

---

## 4. RASTREABILIDADE DocumentoFiscal → DocumentoIngerido (CONFORME 3(g) DE ADR-002)

Todo `DocumentoFiscal` criado por promotion deve conter referência
explícita e consultável ao `DocumentoIngerido` de origem.

**Exigência mínima:** `DocumentoFiscal` deve ganhar um campo de
referência (`origem_documento_ingerido_id` ou equivalente — nome
exacto é decisão de implementação) que aponte para
`DocumentoIngerido.id`.

**Exigência de proveniência:** `ItemFiscal` sintetizado por promotion
deve ser distinguível de item extraído de XML estruturado — campo
ou flag de proveniência (`origem: "xml" | "promotion_documental"`),
para que consumidores futuros (InsightEngine, dashboards, auditoria)
não tratem item sintético e item real como equivalentes sem
distinção. Esta exigência reforça directamente a nota de força
probatória da secção 2.2.

Sem esta rastreabilidade implementada, nenhum service de promotion
cumpre ADR-002, independentemente de qualquer outra condição estar
satisfeita.

---

## 5. ELEGIBILIDADE DE TIPO DE DOCUMENTO (DT-DOC-03)

**Estado actual provado por evidência:** `classifier.py` distingue
apenas formato/canal (`pdf_digital`, `pdf_scan`, `image`, `danfe`,
`unknown`). Apenas `danfe` é, por desenho, identificável como fiscal
sem ambiguidade adicional.

**Regra de elegibilidade — campos completos são necessários, não
suficientes:**

Para documentos classificados como `danfe`, a presença dos campos
obrigatórios da secção 1 é suficiente para elegibilidade, dado que a
classificação `danfe` já exige marcadores estruturais fortes
(presença de "DANFE", "Chave de Acesso", "CFOP", entre outros, no
texto).

Para documentos **não classificados como DANFE**
(`pdf_digital`, `pdf_scan`, `image` genéricos), a presença dos campos
obrigatórios é **necessária mas não suficiente**. É exigida,
adicionalmente, evidência fiscal forte:

- `chave_acesso` válida de 44 dígitos (não apenas presente — validada
  estruturalmente), **e**
- `cfop` e `ncm` sintacticamente válidos (formato correcto, não
  apenas não-nulos), **e**
- marcadores documentais compatíveis com nota fiscal/DANFE no texto
  de origem (reaproveitando a mesma lógica de detecção estrutural já
  usada por `classifier.py` para `danfe`)

Um documento genérico pode conter CNPJ, valor, data e até um código
que sintacticamente pareça CFOP, sem ser uma nota fiscal. A regra
desta secção existe precisamente para impedir que campos
sintacticamente válidos, isoladamente, sejam interpretados como prova
de natureza fiscal.

**O que este contrato não resolve:** um árbitro de elegibilidade
fiscal mais sofisticado que esta verificação de marcadores estruturais
está fora do escopo de DT-DOC-03 nesta versão. Esta limitação deve
ser registada como dívida técnica residual no momento da
implementação, não resolvida silenciosamente.

---

## 6. TESTES QUE PROVAM QUE A PONTE ESTÁ SEGURA

Nenhuma implementação de promotion é considerada canónica sem
cobertura de teste para, no mínimo, os seguintes casos — cada um
espelhando directamente uma regra de ADR-002 ou deste contrato:

| Caso de teste | Resultado exigido | Regra que prova |
|---|---|---|
| Score ≥ 95 + elegibilidade fiscal + campos completos | Promove | 3(e) |
| Score ≥ 95 + campos incompletos | **Não promove** | 3(h), regra negativa 1 |
| Score 70-94 sem homologação | **Não promove** | 3(e) |
| Score 70-94 + homologação aprovada + campos completos + evidência fiscal forte | Promove | 3(e) |
| Score < 70 | **Nunca promove**, mesmo com homologação manual posterior | 3(e) |
| Documento `danfe` com campos completos | Elegível | Secção 5 |
| Documento `pdf_digital` genérico com campos sintacticamente preenchidos, **mas sem evidência fiscal forte** (chave inválida, marcadores ausentes) | **Não promove** | Secção 5 — necessário, não suficiente |
| `DocumentoFiscal` promovido contém referência válida a `DocumentoIngerido` de origem | Rastreabilidade presente | Secção 4 |
| `ItemFiscal` sintetizado tem proveniência distinguível de item de XML | Proveniência marcada | Secção 4 |
| Valores monetários de `ItemFiscal`/`DocumentoFiscal` promovidos são `Decimal`, nunca `float` | Tipo correcto | Secção 2.0 |
| JSON bruto de `campos_extraidos` nunca é escrito directamente em `DocumentoFiscal` sem passar pelo mapeamento da secção 2 | Sem despejo directo | 3(f) |
| Consulta/exibição de registo antigo (`campos_extraidos: list[str]`) não quebra após mudança de schema | Retrocompatibilidade de leitura | Secção 3 |

---

## ORDEM DE RESOLUÇÃO DAS PRÉ-CONDIÇÕES

Conforme decisão de Miguel: DT-DOC-01 primeiro, porque sem
persistência estruturada qualquer trabalho em DT-DOC-02 ou DT-DOC-03
fica sem dados para operar.

```
1. DT-DOC-01 — DocumentoIngerido passa a persistir valores
                estruturados (retrocompatível na leitura)
2. DT-DOC-02 — normalizer.py completa campos em falta (numero_nota,
                tipo, uf_emit, uf_dest, CNPJs, valor_icms) e adopta
                tipo numérico fiscal canónico
3. DT-DOC-03 — elegibilidade fiscal aplicada conforme secção 5 deste
                contrato (campos necessários + evidência fiscal forte
                para documentos não-DANFE)
4. Service de promotion — implementado conforme secções 1-5,
                incluindo proveniência e força probatória de item
                sintético
5. Testes — conforme secção 6, antes de qualquer promotion canónica
            em produção
```

---

*Este contrato não decide. Verifica. ADR-002 decidiu o que a
promotion é institucionalmente. Este documento decide o que tem de
ser verdade no código para que essa decisão seja cumprida — e fecha
explicitamente o atalho que campos sintacticamente válidos, por si
só, poderiam abrir.*

*O conhecimento não está na conversa. Está no repositório.*
