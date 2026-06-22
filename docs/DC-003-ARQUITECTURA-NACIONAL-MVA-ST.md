# DC-003 — Arquitectura Nacional do Motor MVA/ST

**Data:** 2026-06-20

**Natureza:** Decisão arquitectural. Fecha DT-MVA-01
  (ROADMAP_ABERTURA_UTILIZADORES.md, Bloco 1.2).

**Base:** auditoria directa de `app/models.py` (TabelaMVA),
  `app/services/tabela_normativa_service.py` (buscar_mva),
  `app/services/motor_fiscal.py` (carregar_mva),
  `app/services/pipeline_normativo.py`, e
  `app/services/normative_update_service.py`.

---

## PRINCÍPIO DESTA DECISÃO

> A arquitectura deve ser nacional.
> A verdade fiscal só existe onde há fonte validada.

DT-MVA-01 não fecha como "Pará apenas". Fecha como decisão de
arquitectura nacional soberana, com cobertura progressiva por dados
normativos versionados.

A cobertura pode começar com os dados já existentes (Pará e
quaisquer outras UFs já carregadas). A arquitectura não pode nascer
regional, porque isso cria dívida com data de validade curta: quando
a segunda UF entrar, seria necessário refazer o motor em vez de
apenas adicionar dados.

---

## ESTADO DO MOTOR (confirmado por auditoria)

O motor MVA/ST **não está vazio nem hardcoded para Pará**. As
dimensões principais já existem:

| Dimensão | Estado no modelo | Nomenclatura actual |
|----------|-----------------|---------------------|
| UF | `TabelaMVA.estado` | `estado` (sinónimo de `uf`) |
| NCM | `TabelaMVA.ncm` | — |
| Vigência início | `TabelaMVA.vigencia_inicio` | Date, nullable no schema |
| Vigência fim | `TabelaMVA.vigencia_fim` | Date, nullable — None = vigente |
| Fonte normativa | `TabelaMVA.fonte_legal` | + `url_fonte`, `nivel_confianca_fonte` |
| Nível de confiança | `TabelaMVA.nivel_confianca_fonte` | oficial / candidata_oficial / convenio_base / estimativa / sem_fonte |

A query principal (`buscar_mva`) já filtra por UF + NCM + janela de
vigência, ordena por prioridade de fonte, e devolve `None` quando
não há regra.

**Lacunas de formalização identificadas (a resolver, não decisões
novas):**

1. `vigencia_inicio` é nullable no schema — devia ser NOT NULL para
   registos com `nivel_confianca_fonte == "oficial"`. O
   `NormativeValidationAgent` já exige isto para promoção a oficial,
   mas o schema não obriga.
2. `carregar_mva` (adaptador legado em `motor_fiscal.py`) chama
   `buscar_mva` **sem** `data_referencia` — ignora vigência; ainda
   tem fallback para `mva.json`. Deve ser descontinuado.
3. `tabela_mva` não tem `UniqueConstraint` para
   `(estado, ncm, vigencia_inicio)` — permite duplicatas onde
   `tabela_pmpf` já tem protecção. Lacuna a corrigir.
4. Nomenclatura inconsistente: `estado` vs `uf`, `fonte_legal` vs
   `fonte_normativa` — não é erro, mas dificulta leitura de código
   e documentação.

---

## OS DEZ INVARIANTES DO MOTOR MVA/ST SOBERANO

Estes invariantes regem o motor agora e em toda expansão futura.
Nenhum código que os viole pode entrar em produção sem ADR próprio.

**I-MVA-01 — UF como dimensão obrigatória**
`UF` é dimensão obrigatória de qualquer cálculo MVA/ST. Nenhum
cálculo pode ser efectuado sem UF definida. Nenhuma UF pode ser
hardcoded como regra especial ou como fallback implícito.

**I-MVA-02 — NCM como dimensão obrigatória**
`NCM` é dimensão obrigatória. Cálculos de MVA/ST sem NCM definido
não são permitidos.

**I-MVA-03 — Vigência obrigatória**
Toda regra MVA deve ter `vigencia_inicio` definido. `vigencia_fim`
é opcional (None = vigente até revogação). Regras sem `vigencia_inicio`
só são aceites com `nivel_confianca_fonte == "estimativa"` ou
inferior — nunca como `oficial`.

**I-MVA-04 — Fonte normativa obrigatória**
Toda regra MVA deve ter fonte identificável: portaria, convénio,
protocolo, decisão SEFAZ. `fonte_legal` + `url_fonte` quando
disponível. Regras sem fonte só entram com nível `estimativa` ou
`sem_fonte`, nunca como `oficial`.

**I-MVA-05 — Nível de confiança explícito**
Toda regra MVA deve declarar explicitamente o nível de confiança
da sua fonte. Níveis válidos (já definidos no modelo):
`oficial` | `candidata_oficial` | `convenio_base` |
`convenio_base_sem_aliquota` | `estimativa` | `sem_fonte`.
O motor usa este nível para ordenar resultados e para decidir
se apresenta o cálculo como definitivo ou como estimativa.

**I-MVA-06 — Lacuna normativa é resposta válida**
Se não existir regra vigente para a combinação
UF / NCM / data_referencia, o sistema **não calcula**. A resposta
correcta é `"cobertura_indisponivel"` ou `"lacuna_normativa"`,
não fallback silencioso, não MVA zero, não MVA médio nacional.
Apresentar um cálculo sem fonte é erro fiscal, não degradação
aceitável.

**I-MVA-07 — Cobertura progressiva por dados, não por arquitectura**
A arquitectura é nacional desde já. A cobertura real depende dos
dados carregados em `tabela_mva`. Adicionar cobertura para uma nova
UF é operação de dados (importar tabela + validar fonte), não
operação de código. O motor não precisa de ser alterado para cobrir
uma nova UF.

**I-MVA-08 — data_referencia obrigatória em todos os callers**
Todo caller que consulte MVA deve passar `data_referencia` (data de
emissão do documento fiscal). Chamadas sem `data_referencia`
ignoram vigência e são comportamento incorrecto. O adaptador
`carregar_mva` (que hoje omite `data_referencia`) deve ser
descontinuado ou corrigido.

**I-MVA-09 — Sem fallback silencioso para ficheiro estático**
O fallback para `mva.json` em `carregar_mva` viola I-MVA-03 e
I-MVA-04 (sem vigência, sem fonte verificável). Deve ser removido.
Durante o período de transição, se o fallback for invocado, deve
registar aviso explícito e devolver `None`, não um valor calculado.

**I-MVA-10 — Unicidade sobre a chave normativa canónica vigente**
A tabela `tabela_mva` deve ter `UniqueConstraint` sobre a chave
normativa canónica vigente. No schema actual, a chave mínima é
`(estado, ncm, vigencia_inicio)`. Se o modelo evoluir para incluir
segmento, CEST, regime tributário, protocolo ICMS, tipo de operação
ou outras dimensões normativas, essas dimensões passam
automaticamente a integrar a chave canónica — sem necessidade de
ADR próprio, porque a regra é "unicidade sobre a chave normativa
real", não "unicidade sobre estas três colunas". Espelha o padrão
já aplicado em `tabela_pmpf` (que tem cinco dimensões na chave).
Registos duplicados para a mesma chave canónica vigente são
ambiguidade normativa, não enriquecimento.

---

## O QUE ESTA DECISÃO NÃO FAZ

Esta decisão **não** exige cobertura nacional completa no
lançamento. O Pará pode ser a única UF coberta no piloto inicial —
isso é coerente com I-MVA-07 (cobertura por dados) e não viola
nenhum dos dez invariantes. O que esta decisão proíbe é:

- Hardcodar Pará como única UF suportada no código
- Devolver cálculo de outra UF baseado em dados do Pará
- Silenciar a lacuna quando uma UF não tiver cobertura
- Usar `mva.json` como fonte normativa em produção

---

## TRABALHO DE FORMALIZAÇÃO (não decisões novas)

As quatro lacunas identificadas na auditoria devem ser resolvidas
**antes** do service de promotion (Bloco 5 do roadmap), porque a
promotion usa MVA:

| # | Lacuna | Impacto |
|---|--------|---------|
| F1 | `vigencia_inicio` nullable para `oficial` | Regras sem vigência podem ser usadas em cálculo |
| F2 | `carregar_mva` sem `data_referencia` | Ignora vigência em callers legados |
| F3 | Sem `UniqueConstraint` em `tabela_mva` | Permite duplicatas normativas |
| F4 | Nomenclatura `estado`/`uf`, `fonte_legal`/`fonte_normativa` | Dificulta manutenção e auditoria |
| F5 | `TabelaMVA.mva` e `aliquota_interna` usam `Float` | Risco de precisão em cálculo fiscal — migrar para `Numeric`/`Decimal` quando o motor MVA/ST for formalizado em código, alinhado com CT-DOC-001 §2.0 |

Estas formalizações **não exigem ADR** — são alinhamento do código
com invariantes já decididos neste documento. Qualquer desvio aos
invariantes (I-MVA-01 a I-MVA-10) exige ADR próprio.

---

## FECHO DE DT-MVA-01

```
DT-MVA-01: resolvido como decisão arquitectural.
Escopo: motor nacional por desenho,
        cobertura activada por dados versionados,
        lacuna explícita quando faltar fonte.
```

Bloco 1 do roadmap fica agora completamente fechado:

```
1.1a  Inventário completo              ✔
1.1b  Testes mínimos do eixo canónico  ✔
      DT-FLUXO-01 (/upload-xml)        ✔ bloqueante para Bloco 13
      DT-FLUXO-02 (/lote)              ✔ interno não-bloqueante
      DT-FLUXO-03 (dedup TOCTOU)       ✔ corrigido e confirmado em produção
      DT-MVA-01 (escopo MVA/ST)        ✔ arquitectura nacional, dados progressivos
```

Próximo bloco: Bloco 9 — Identidade, Permissões e Multi-tenant.

---

*O conhecimento não está na conversa. Está no repositório.*
