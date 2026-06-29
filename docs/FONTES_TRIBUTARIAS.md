# FONTES TRIBUTÁRIAS — B13-OPS-01

**Versão:** 1.0.0  
**Data:** 2026-06-29  
**Manifesto canónico:** `data/fontes_tributarias_manifest.json`  
**Testes:** `tests/test_fontes_tributarias_manifest.py`  
**Hierarquia:** Lei → `CONSTITUICAO_TRIBUTARIA_L2.md` → ADRs → Invariantes → este documento → `data/fontes_tributarias_manifest.json` → Código → Testes

---

## 1. Princípio soberano

**Fonte normativa oficial internalizada é a única que pode fundamentar decisão fiscal.**

Nenhum outro tipo de fonte — operacional, informativa, auxiliar, LLM ou externa — pode substituir norma internalizada e versionada pelo motor determinístico da plataforma.

---

## 2. Taxonomia de fontes

### 2.1 `normativa_oficial`

Lei, resolução, convênio ou norma emitida por autoridade estatal competente.

- Pode fundamentar decisão fiscal **se e somente se** internalizada, versionada e referenciada por hash.
- Exemplos: Lei Complementar 123/2006, Resoluções CGSN, Convênios ICMS/CONFAZ.
- `pode_fundamentar_decisao=true` exige **todas** as condições abaixo:
  - `tipo=normativa_oficial`
  - `status=activa`
  - `hash_referencia != null`
  - `forma_internalizacao` ∈ `{manual_curada, ingestao_controlada, tabela_versionada}`
  - Artefacto interno versionado referenciado e usado pelo motor determinístico

**Enquanto estas condições não forem cumpridas, a fonte normativa deve ter `pode_fundamentar_decisao=false` e `status=em_revisao`.**

### 2.2 `operacional_oficial`

Fonte oficial que valida factos operacionais — cadastros, classificações, situações, existência.

- Não fundamenta decisão fiscal.
- Pode ter `pode_validar_fato_operacional=true`.
- Exemplos: Receita Federal (CNPJ), IBGE/CNAE 2.3, REDESIM, PGFN.
- A plataforma pode consumir estas fontes para validar dados, mas o motor fiscal não as usa como base de cálculo.

### 2.3 `informativa_oficial`

Página ou recurso oficial de comunicação institucional — explicativo, orientativo.

- Não fundamenta decisão fiscal.
- Não valida facto operacional.
- Pode apoiar UX, explicação e documentação interna.
- Exemplos: gov.br Portal MEI, gov.br Portal Simples Nacional.

### 2.4 `auxiliar_nao_normativa`

Material técnico, estatístico ou orientativo produzido por entidade não estatal.

- Nunca fundamenta decisão.
- Pode apoiar contexto humano e análise auxiliar supervisionada.
- Exemplos: IBPT (tabela NCM), SEBRAE (materiais PME).

### 2.5 `proibida_para_decisao`

Fonte institucionalmente vedada para qualquer uso em decisão fiscal.

- `pode_fundamentar_decisao=false` — sem excepção.
- `pode_ser_usada_por_llm=false` — sem excepção.
- `forma_internalizacao=proibida` — sem excepção.
- Inclui qualquer modelo de linguagem (LLM) usado como fonte de verdade fiscal.

---

## 3. LLM não é fonte tributária

**DeepSeek, GPT, Kimi, Claude e qualquer outro LLM são processadores auxiliares supervisionados — nunca fontes de verdade fiscal.**

- LLM não emite norma.
- LLM não homologa acto.
- LLM não substitui motor determinístico.
- LLM pode analisar, resumir e sugerir — sempre sob supervisão humana e BudgetGuard.

DeepSeek/GPT/Kimi/Claude pertencem a um futuro **manifesto de provedores de inferência** (`data/provedores_inferencia_manifest.json`), separado deste manifesto fiscal.

A entrada `VEDACAO-LLM-001` no manifesto é uma vedação institucional explícita, não uma fonte.

---

## 4. Invariante `pode_fundamentar_decisao`

```
pode_fundamentar_decisao=true

↔ tipo=normativa_oficial

∧ status=activa

∧ hash_referencia != null

∧ forma_internalizacao ∈ {manual_curada, ingestao_controlada, tabela_versionada}

∧ artefacto interno versionado usado pelo motor
```

Se qualquer condição falhar → `pode_fundamentar_decisao=false`.

Este invariante é verificado automaticamente em `tests/test_fontes_tributarias_manifest.py`.

---

## 5. Relação com documentos constitucionais

| Documento | Papel |
|-----------|-------|
| `CONSTITUICAO_TRIBUTARIA_L2.md` | Princípios que o código não pode violar — camada superior |
| `MAPA_AUTORIDADES_L2.md` | Quem exerce autoridade: normativa (Estado), analítica (Plataforma), executiva (Contador CRC) |
| `MAPA_REALIDADE_TRIBUTARIA_L2.md` | O que o sistema é hoje — capacidades provadas vs. parciais |
| `docs/FONTES_TRIBUTARIAS.md` | Este documento — taxonomia e regras de uso de fontes |
| `data/fontes_tributarias_manifest.json` | Camada executável — lista canónica e testável de fontes |

**Hierarquia de autoridade (da Constituição L2):**

```
Normativa  → Estado (define regras)
Analítica  → Plataforma (calcula, compara, recomenda)
Executiva  → Contador CRC (actos que a lei reserva à assinatura)
```

Nenhuma fonte pode inverter esta hierarquia. Uma fonte operacional oficial (Receita, IBGE) valida factos na camada analítica — nunca exerce autoridade normativa.

---

## 6. Processo de promoção de fonte

Para promover uma fonte normativa de `pode_fundamentar_decisao=false` para `true`:

1. Identificar o artefacto normativo (lei, resolução, convênio).
2. Internalizar/versionar o conteúdo relevante (tabela, alíquota, limite).
3. Calcular e registar `hash_referencia` do artefacto internalizado.
4. Actualizar `status=activa` e `forma_internalizacao`.
5. Ligar o artefacto ao motor determinístico (código + teste de regressão).
6. Aprovação Miguel + auditoria GPT.
7. Actualizar manifesto + re-executar suite.

**Sem aprovação e sem hash, a fonte não fundamenta decisão — mesmo que seja oficial.**

---

## 7. Revisão

| Frequência | Critério |
|------------|---------|
| Semestral (mínimo) | Fontes com `risco_se_desatualizada=critico` |
| Anual | Todas as fontes |
| A qualquer momento | Se lei/resolução for alterada ou substituída |

Responsável: Miguel Moreira (product authority).
