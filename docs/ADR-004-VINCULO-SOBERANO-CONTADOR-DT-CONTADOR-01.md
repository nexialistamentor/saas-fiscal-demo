# ADR-004 — VÍNCULO SOBERANO CONTADOR↔EMPRESA/DOCUMENTO (DT-CONTADOR-01)

**Data:** 2026-06-23

**Estado:** Decidido — arquitectura definida; implementação pendente (DT-CONTADOR-01)

**Natureza:** Decisão arquitectural que concretiza ADR-003. Define o modelo
  operacional de autorização para acesso de contadores a empresas e documentos
  fiscais. Substitui o pool aberto V1 por vínculo soberano com elegibilidade,
  score, complexidade e escalação.

**Base:** ADR-003, MT-08 (XFAIL confirmado em `55789a0`), HANDOFF_TRIBUTARIA_L2_v2,
  DC-004, sessão 2026-06-23

**Relação com ADR-003:** Esta ADR **não revoga** ADR-003. Concretiza a
  implementação técnica de DT-CONTADOR-01. Os Modelos A/B/C abaixo **substituem
  apenas a nomenclatura provisória** de ADR-003 § "Modelos admissíveis" para
  fins de schema e código. A proibição de claim-by-ID permanece inalterada.

---

## CONTEXTO

O sistema actual opera em **pool aberto V1**: qualquer contador com
`role=contador` e `PerfilContador.status=aprovado` pode assumir qualquer
documento via `POST /contador/homologacoes/{documento_id}/assumir` se souber
o ID.

ADR-003 proibiu este padrão para utilizadores reais e classificou-o como vector
de captura operacional. O teste MT-08 confirmou a vulnerabilidade activa (XFAIL
em `55789a0`).

Evidência de código (`app/routers/contador_router.py`, `homologacao_service.py`):

- `assumir` valida apenas role + perfil aprovado + `decisao=fila_homologacao`
- Não verifica `DocumentoIngerido.empresa_id` contra vínculo do contador
- `criar_fila_homologacao` cria `HomologacaoDocumental` directamente — sem
  camada de atribuição prévia

Lacunas estruturais actuais:

- Não existe tabela de vínculo `contador↔empresa`
- Não existe tabela de atribuição `documento↔contador`
- `PerfilContador` regista elegibilidade regulatória, não autorização operacional
- `HomologacaoDocumental` liga contador a documento, mas sem vínculo prévio validado
- `reputacao_score` existe mas não entra no encaminhamento
- Não existe classificação de complexidade por documento
- Casos complexos não têm caminho de escalação para Autoridade Operacional

---

## O PADRÃO QUE ESTAMOS A PROIBIR

> **Pool aberto com claim-by-ID:** contador aprovado assume qualquer documento
> cujo ID conheça, sem vínculo com a empresa, sem atribuição prévia, sem
> auditoria da origem do acesso.

Consequências deste padrão:

- Qualquer contador aprovado vira potencial capturador de carteira alheia
- Score de reputação perde sentido — quem for mais rápido a capturar ganha
  (Efeito Cobra)
- Cliente não tem visibilidade nem controlo sobre quem acede aos seus documentos
- Auditoria regista o acto mas não a autorização que o deveria preceder

Padrões adicionais proibidos:

- **Score como substituto de vínculo** — encaminhar para o "melhor contador"
  sem autorização prévia
- **Vínculo tácito por histórico** — "já trabalhou com esta empresa" sem
  registo explícito
- **Vínculo por role** — `role=contador` é elegibilidade regulatória, não
  autorização operacional
- **Atribuição sem escopo** — contador vê toda a empresa em vez do
  documento/acto específico
- **Vínculo retroactivo** — criado após o acesso para regularizar captura
  já ocorrida
- **Matching autónomo sem policy auditável** — `origem=sistema` sem
  `policy_version` referenciada

---

## PRINCÍPIO DE AUTORIZAÇÃO

> O vínculo deve preceder o acesso. Se nasce depois do acesso, não é
> autorização — é captura regularizada.

```
DOCUMENTO FISCAL
        │
        ▼
┌───────────────────────────────┐
│  1. ELEGIBILIDADE             │  CRC válido? Status aprovado? UF/domínio?
│     PerfilContador            │
└───────────────┬───────────────┘
                │ passa
                ▼
┌───────────────────────────────┐
│  2. VÍNCULO                   │  Empresa autorizou? Admin atribuiu?
│     contador_empresa_vinculo  │  Activo, não expirado, não revogado
└───────────────┬───────────────┘
                │ vínculo válido
                ▼
┌───────────────────────────────┐
│  3. SCORE                     │  Entre elegíveis e autorizados:
│     reputacao_score           │  rapidez, qualidade, devoluções, histórico
└───────────────┬───────────────┘
                │ ranqueado
                ▼
┌───────────────────────────────┐
│  4. COMPLEXIDADE              │  Baixa → automático
│     homologacao_atribuicao    │  Média → recomendação + confirmação
└───────────────┬───────────────┘  Alta  → escalação para Autoridade Operacional
                │ atribuído (única atribuição activa por documento/acto)
                ▼
┌───────────────────────────────┐
│  5. ACESSO AO DOCUMENTO       │  Escopo limitado ao documento/empresa/acto
│     HomologacaoDocumental     │  empresa_id coerente em todas as camadas
└───────────────────────────────┘  Toda acção auditada
```

**Regras:**

- Score entra depois do vínculo, nunca antes
- Elegibilidade sem vínculo não dá acesso
- Vínculo sem atribuição não dá acesso ao documento
- Atribuição sem escopo definido é inválida
- Auditoria é obrigatória em cada transição

**Nota sobre elegibilidade regional:** compatibilidade UF/domínio (`uf_crc`,
  escopo) é critério de **elegibilidade**, não substituto de vínculo. ADR-003
  Modelo C (pool regional) fica absorvido nesta camada — nunca dispensa
  vínculo activo.

---

## DECISÃO PRINCIPAL — MODELO D-SOBERANO

A plataforma adopta o **Modelo D-Soberano: Vínculo + Elegibilidade + Score +
Complexidade + Escalação + Auditoria**.

**No piloto:** vínculo criado manualmente por Admin/Autoridade Operacional
(Miguel), com `origem="admin"`.

**Na escala:** matching autónomo dentro de vínculos autorizados pelo cliente
ou por regra aprovada, com `policy_version` obrigatória.

O mesmo motor técnico serve ambos os momentos. A diferença é a origem do
vínculo.

Actos abrangidos (não apenas `assumir`):

- `POST /contador/homologacoes/{documento_id}/assumir` — bloqueado sem vínculo
  + atribuição válida
- `POST /contador/homologacoes/{homologacao_id}/decidir` — bloqueado se
  homologação não derivar de atribuição aceite
- `GET /contador/homologacoes/pendentes` — filtrado por atribuições válidas,
  nunca por pool global
- Qualquer endpoint futuro de acesso contador↔empresa
- Qualquer encaminhamento automático de documentos para contadores

---

## REGRA FUNDAMENTAL — VÍNCULO PRECEDE ACESSO

> Nenhum contador pode actuar sobre documento de empresa sem vínculo activo,
> atribuição válida e escopo definido.

Sequência institucional obrigatória:

1. **Elegibilidade** — `PerfilContador.status == "aprovado"`, CRC válido,
   UF/domínio compatível
2. **Vínculo** — `contador_empresa_vinculo` activo, não expirado, não revogado,
   sem duplicado activo para mesmo contador/empresa/escopo
3. **Score** — ranqueamento dentro do universo elegível e autorizado
4. **Complexidade** — classificação determina modo de atribuição
5. **Atribuição** — `homologacao_atribuicao` criada, única activa por
   documento/acto, `empresa_id` coerente
6. **Aceite** — contador confirma a atribuição (`status=aceite`)
7. **Acesso** — `HomologacaoDocumental` criada; documento visível apenas para
   aquele contador, aquela empresa, aquele acto
8. **Auditoria** — cada transição registada com timestamp, actor e origem

---

## MODELOS DE AUTORIZAÇÃO ADMISSÍVEIS

### Modelo D-Soberano (adoptado — arquitectura alvo)

Vínculo + Score + Complexidade + Escalação. Motor único serve piloto e escala.

```
Piloto:    Admin cria vínculo (origem=admin) → sistema atribui → contador aceita
Escala:    Cliente autoriza (origem=cliente) → sistema ranqueia → atribui → contador aceita
Autónomo:  Regra aprovada (origem=sistema, policy_version obrigatória) → atribui → aceita
Sensível:  qualquer camada → escalação para Autoridade Operacional
```

### Modelo A (núcleo — vínculo directo cliente↔contador)

Cliente autoriza explicitamente. Máxima soberania do contribuinte. Base para o
modo escala. Corresponde ao Modelo A preferencial de ADR-003.

### Modelo B (modo piloto provisório — operação manual)

Admin/Autoridade Operacional cria o primeiro vínculo com `origem="admin"`.
**Não é arquitectura permanente.** Todos os vínculos criados por este modo
ficam rastreáveis por `criado_por_user_id`. Corresponde ao Modelo B de ADR-003.

### Modelo C (regra automática dentro de vínculos existentes)

Sistema encaminha dentro de vínculos já autorizados. `policy_version` e
`regra_matching_id` obrigatórios. Score decide quem recebe dentro do universo
autorizado. **Não confundir** com o "pool regional" provisório de ADR-003 —
regionalidade é elegibilidade, não autorização.

---

## INVARIANTES SOBERANOS

### INV-VINCULO-01 — Coerência de empresa entre camadas

> `DocumentoIngerido.empresa_id`, `homologacao_atribuicao.empresa_id` e
> `contador_empresa_vinculo.empresa_id` devem ser iguais. Qualquer divergência
> invalida a atribuição antes de ser criada.

**Pré-condição:** documentos sem `empresa_id` (`nullable` no schema actual)
não são elegíveis para atribuição contador↔empresa até resolução de empresa.
DT-CONTADOR-01 deve rejeitar com erro explícito, não inferir empresa.

### INV-VINCULO-02 — Uma atribuição activa por documento/acto

> Um documento não pode ter mais de uma `homologacao_atribuicao` com
> `status IN ('atribuida', 'aceite')` para o mesmo acto/escopo. Estados finais
> (`concluida`, `recusada`, `expirada`) não contam.

Constraint futura: `UNIQUE PARTIAL (documento_ingerido_id, escopo) WHERE status IN ('atribuida', 'aceite')`.

### INV-VINCULO-03 — Sem duplicado de vínculo activo

> Não pode existir mais de um `contador_empresa_vinculo` com `status=activo`
> para o mesmo contador, empresa e escopo. Vínculos anteriores devem ser
> revogados, expirados ou versionados antes de criar novo.

### INV-VINCULO-04 — Revogação bloqueia acesso e atribuições pendentes

> Revogar ou suspender um vínculo bloqueia imediatamente novas atribuições e
> novo acesso. Atribuições pendentes vinculadas (`status IN ('atribuida',
> 'aceite')`) devem ser expiradas, suspensas ou revalidadas. A revogação nunca
> apaga histórico — regista `revogado_em` e `revogado_por_user_id`.

### INV-VINCULO-05 — Matching autónomo exige policy auditável

> Toda atribuição com `origem='sistema'` ou `modo_atribuicao='automatico'`
> deve referenciar `policy_version` ou `regra_matching_id` que justifique a
> decisão. Matching autónomo sem rastreio de política não é admissível.

---

## ENTIDADES TÉCNICAS NECESSÁRIAS

### `contador_empresa_vinculo`

```
id
contador_id            FK → perfis_contador.id
empresa_id             FK → empresas.id
origem                 ENUM: admin | cliente | sistema
status                 ENUM: activo | suspenso | revogado | expirado
escopo                 JSONB (opcional — limitar por tipo de documento/acto)
criado_por_user_id     FK → usuarios.id  (identificador soberano)
criado_por_email       String (snapshot legível — não identificador primário)
criado_em              DateTime
validade               DateTime (nullable — sem validade = permanente até revogação)
policy_version         String (nullable — obrigatório se origem=sistema)
revogado_em            DateTime (nullable)
revogado_por_user_id   FK → usuarios.id (nullable)
```

**Nota:** `criado_por_user_id` é o identificador soberano. `criado_por_email`
é snapshot legível — emails mudam, IDs não.

Nome alternativo admissível em ADR-003: `contador_empresa_autorizacao`. O nome
canónico para DT-CONTADOR-01 é `contador_empresa_vinculo`.

### `homologacao_atribuicao`

```
id
documento_ingerido_id  FK → documentos_ingeridos.id
empresa_id             FK → empresas.id          (deve ser == documento.empresa_id)
contador_id            FK → perfis_contador.id
vinculo_id             FK → contador_empresa_vinculo.id
                         (vínculo activo coerente com empresa_id e contador_id)
status                 ENUM: atribuida | aceite | concluida | recusada | expirada
complexidade           ENUM: baixa | media | alta
modo_atribuicao        ENUM: automatico | recomendado | manual
escopo                 String (tipo de acto autorizado)
policy_version         String (nullable — obrigatório se modo=automatico)
regra_matching_id      String (nullable — referência à regra que gerou a atribuição)
atribuido_em           DateTime
aceite_em              DateTime (nullable)
concluido_em           DateTime (nullable)
auditoria              JSONB   (trilha operacional V1 — ver nota abaixo)
```

**Nota sobre auditoria JSONB:** aceitável como trilha operacional inicial em
V1. A direcção soberana é ledger/eventos append-only para transições críticas
(criação, aceite, recusa, revogação, expiração, conclusão). JSONB mutável não
substitui ledger imutável.

**Invariante de criação:** `HomologacaoDocumental` só pode ser criada após
`homologacao_atribuicao` com `status=aceite`. O endpoint `assumir` deixa de
criar homologação directamente — passa a aceitar atribuição pendente ou a
invocar serviço que valida vínculo antes de criar `HomologacaoDocumental`.

**Ressalva de legado:** registos de `HomologacaoDocumental` existentes antes
de DT-CONTADOR-01 não têm `homologacao_atribuicao` correspondente. São dados
legados tolerados, não padrão futuro admissível.

---

## FLUXO ALVO DO `/assumir` (DT-CONTADOR-01)

Estado actual (proibido para piloto):

```
contador aprovado + documento_id → criar_fila_homologacao → HomologacaoDocumental
```

Estado alvo:

```
contador aprovado
  → verificar contador_empresa_vinculo (activo, empresa_id == documento.empresa_id)
  → verificar homologacao_atribuicao (atribuida, contador_id == perfil.id)
  → aceitar atribuição (status=aceite)
  → criar HomologacaoDocumental (status=pendente)
  → auditoria em cada passo
```

Implementação em `homologacao_service.py` — **não** duplicar lógica no router.

---

## RELAÇÃO COM A CONSTITUIÇÃO TRIBUTÁRIA L2

Esta ADR materializa princípios já declarados, com referência aos artigos
**canónicos** da Constituição v1.0:

- **Preâmbulo + Art. II:** o contribuinte é beneficiário; contador é actor
  regulatório — acesso exige autorização explícita, não capacidade genérica
- **Art. VI (Auditabilidade):** cada transição de vínculo e atribuição é
  evento auditável; quem viu, quem assumiu, quem decidiu
- **Art. VII (Contador Parceiro):** contador actua só nos domínios atribuídos
  por lei ou política de confiança documental
- **Art. I §3 + princípio HANDOFF ("IA propõe, nunca decide"):** score ranqueia
  e recomenda; cliente ou Autoridade Operacional ratificam casos complexos;
  matching autónomo exige policy versionada

**Conflito declarado — Art. VII §3:**

A Constituição v1.0 declara: *"O pool de contadores é aberto — nenhum contador
tem exclusividade sobre um contribuinte."*

Esta ADR **não** adopta pool aberto claim-by-ID. Interpretação institucional
para ratificação:

- §3 proíbe **monopólio/exclusividade** imposta ao contribuinte
- §3 **não** autoriza acesso sem vínculo prévio
- DT-CONTADOR-01 requer **emenda à Constituição Art. VII §3** antes do
  Bloco 13, para eliminar ambiguidade entre "pool aberto" e "vínculo soberano"

Até emenda ratificada, prevalece ADR-003 + ADR-004 sobre a redacção literal
de §3 para efeitos de autorização operacional.

---

## EFEITO IMEDIATO

1. `POST /contador/homologacoes/{documento_id}/assumir` permanece bloqueado
   para utilizadores reais (ADR-003 em vigor)
2. MT-08 mantém XFAIL como sentinela activa — não remover até DT-CONTADOR-01
   implementado e INV-VINCULO-02 e INV-VINCULO-03 protegidos por constraint
3. Nenhum endpoint novo de pool deve ser criado antes das duas entidades
   existirem no schema
4. No piloto, Miguel/Admin cria vínculos manualmente com `origem="admin"` e
   `criado_por_user_id` — sem código de matching autónomo até policy versionada
5. Emenda Constituição Art. VII §3 entra no backlog de ratificação Miguel

---

## ESCOPO DT-CONTADOR-01 (implementação — não decidido aqui em detalhe)

Entregáveis mínimos derivados desta ADR:

1. Migrations: `contador_empresa_vinculo`, `homologacao_atribuicao`
2. Models SQLAlchemy + constraints parciais (INV-VINCULO-02, INV-VINCULO-03)
3. Serviço de autorização contador (vínculo → atribuição → homologação)
4. Refactor `assumir` + guards em `decidir` e `pendentes`
5. Testes: MT-08 passa com 403; testes de invariantes de unicidade
6. Emenda Constituição Art. VII §3 (documento separado, ratificação Miguel)

---

## PRINCÍPIO DE FECHO

> Score melhora eficiência. Vínculo garante soberania. Complexidade decide se
> automatiza ou escala. Auditoria prova tudo.

> A plataforma deve automatizar o encaminhamento, não automatizar o acesso.

> Autonomia da plataforma deve encaminhar dentro de vínculos soberanos, não
> substituir o consentimento por conveniência operacional.

> O vínculo impede captura. A unicidade impede corrida. A revogação impede
> acesso morto. A auditoria impede esquecimento.

---

*O conhecimento não está na conversa. Está no repositório.*
