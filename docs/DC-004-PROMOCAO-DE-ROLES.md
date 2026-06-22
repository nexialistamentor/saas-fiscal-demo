# DC-004 — Promoção de Roles e Autoridade Operacional

**Data:** 2026-06-20

**Natureza:** Decisão operacional. Declara formalmente o processo
  actual de promoção entre os três roles do sistema
  (`user`, `admin`, `contador`), e define os limites do que é
  aceitável para o piloto controlado (Bloco 13 do roadmap).

**Base:** auditoria directa de `app/security.py`, `app/models.py`
  (`ROLES_VALIDOS`), `app/auth_router.py`, `app/main.py`
  (`POST /admin/set-role`) e busca exaustiva por alterações de
  `user.role`.

---

## PRINCÍPIO

> Role dá capacidade ao operador.
> Só vínculo auditável transforma capacidade em autorização.

Esta decisão trata apenas da primeira metade — capacidade. A
segunda metade — autorização sobre documento de empresa — é
matéria da ADR-003, que esta decisão complementa mas não substitui.

---

## ACHADO DA AUDITORIA

Não existe endpoint **público** de auto-promoção. O registo em
`/auth/register` (`app/auth_router.py`) cria sempre
`role = "user"`. O campo `tipo_usuario` do payload distingue
CPF/MEI/Simples e **não** altera role.

Existe um endpoint administrativo `POST /admin/set-role`
(`app/main.py`, requer `require_role("admin")`). Não é endpoint
público, mas **não implementa o protocolo da Decisão 4** e **não
cria `PerfilContador`** ao promover para `"contador"`. Usá-lo como
fluxo de piloto deixa o sistema em estado potencialmente incoerente.

Para o piloto controlado (Bloco 13), a promoção admissível continua
a ser processo **operacional manual**, executado pela **Autoridade
Operacional da Plataforma** directamente na base de dados de
produção (ou equivalente transaccional com protocolo completo).

O endpoint `set-role` **não substitui** esse protocolo enquanto
não criar `PerfilContador` e não produzir trilha institucional do
passo 2.

Isto **não é bug de ausência total de mecanismo** — é estado real,
parcialmente documentado. Esta decisão torna esse processo explícito
e estabelece limites para admissibilidade no piloto.

---

## DECISÃO 1 — Estado actual: autoridade operacional manual

Para o piloto controlado (Bloco 13), promoção de roles é processo
**operacional manual**, executado pela **Autoridade Operacional da
Plataforma** (hoje exercida por Miguel) directamente na base de
dados de produção.

A Autoridade Operacional é papel institucional, não pessoa física.
Esta decisão não hardcoda Miguel como única autoridade legítima —
declara que, no estado actual do sistema, ele exerce esse papel por
ausência de fluxo formal de delegação. Quando esse fluxo existir,
o papel pode ser exercido por outras pessoas devidamente
designadas, sem necessidade de revisão desta decisão.

Este processo é admissível para piloto controlado porque:

1. O conjunto de utilizadores piloto é pequeno e conhecido
   (1-3 empresas, 1 contador parceiro inicial, conforme Bloco 13)
2. A frequência de promoções é baixa (não é fluxo recorrente)
3. Apenas a Autoridade Operacional tem acesso de escrita controlada à
   base de produção via protocolo da Decisão 4 (sem painel admin
   self-service; o endpoint POST /admin/set-role existe tecnicamente
   mas não constitui fluxo admissível de piloto — ver Decisão 2)

**Sobre logs técnicos:** o log SQL do PostgreSQL em ambiente Railway
**não é considerado trilha soberana suficiente** para promoção de
roles. Logs de banco em ambientes geridos podem expirar, podem
não preservar contexto humano da decisão, e podem não estar
acessíveis quando necessário. A trilha soberana exigida está
declarada na Decisão 4 desta DC.

---

## DECISÃO 2 — O que NÃO é admissível, mesmo no piloto

- Endpoint público que permita auto-promoção (ex.: utilizador pedir
  para virar contador através de formulário sem revisão humana)
- Promoção via flag em registo (`tipo_usuario` no payload de
  `/auth/register` virar `role` directamente)
- Promoção via header, cookie, ou qualquer mecanismo que não passe
  pela Autoridade Operacional
- Promoção via `POST /admin/set-role` **sem** protocolo da Decisão 4
  e **sem** criação/validação simultânea de `PerfilContador` quando
  o role destino for `"contador"`
- Confiar exclusivamente no log SQL do banco como trilha de
  auditoria

---

## DECISÃO 3 — Capacidade vs. activação operacional

**Esta decisão é central e tem implicação imediata no código.**

Para todos os endpoints sob `/contador/*` e para qualquer endpoint
futuro que dependa de capacidade de contador, a regra de
autorização mínima é **conjuntiva**:

```
User.role == "contador"
+ PerfilContador.status == "aprovado"
```

Consequências directas:

1. **`require_role("contador")` sozinho é insuficiente.** Nenhum
   endpoint de contador pode usar apenas `require_role("contador")`
   como autorização. Esta regra é vinculativa para qualquer código
   futuro — violá-la exige ADR próprio.

2. **`role == "contador"` + `PerfilContador.status == "pendente"`
   NÃO concede acesso operacional aos endpoints de contador.** O
   utilizador tem a capacidade declarada (role), mas a qualificação
   regulatória ainda não foi validada. Só `status == "aprovado"`
   activa capacidade operacional.

3. **`role == "contador"` sem `PerfilContador` correspondente é
   estado incoerente** e viola explicitamente
   `_get_perfil_contador` em `contador_router.py`. A promoção deve
   sempre criar simultaneamente o registo em `perfis_contador`
   (ver Decisão 4).

**Nota de conformidade actual:** `contador_router.py` já usa
`_get_perfil_contador` (role + status aprovado). A Decisão 3
proíbe regressão futura para `require_role` isolado.

---

## DECISÃO 4 — Protocolo obrigatório de promoção manual

Toda promoção de role executada manualmente segue, sem excepção,
esta sequência:

```
1. SELECT antes da alteração:
   - confirmar utilizador alvo (email/id)
   - confirmar role actual
   - confirmar ausência ou estado de PerfilContador, se aplicável

2. Registo operacional rastreável:
   - issue dedicada no repositório,
   - documento em docs/operacao/,
   - ou commit dedicado em branch operacional
   contendo:
     - identificação do utilizador (email/id)
     - role anterior e role novo
     - justificação
     - data e identificação de quem executa (Autoridade Operacional)

3. UPDATE controlado:
   - alteração explícita, transacional
   - sem alterações colaterais não documentadas

4. SELECT depois da alteração:
   - confirmar que o role foi alterado
   - confirmar que outras colunas não foram afectadas

5. Se promoção a "contador":
   - criação/validação de PerfilContador na mesma janela operacional
   - status inicial deve ser declarado explicitamente
     ("pendente" ou "aprovado") — não default silencioso
   - role="contador" sem PerfilContador correspondente é estado
     incoerente e não deve ser deixado em produção
```

**Nenhum dos cinco passos é opcional.** O registo operacional do
passo 2 é a trilha soberana — o log SQL do banco não a substitui.

---

## DECISÃO 5 — Quando deixar de ser admissível

O processo manual deixa de ser admissível e exige fluxo HTTP
formal quando qualquer destas condições se verificar:

1. Mais de 5 contadores parceiros activos no sistema
2. Mais de 1 promoção de role por semana, em média
3. Necessidade de delegar promoção (a Autoridade Operacional deixa
   de ser exercida por uma única pessoa)
4. Auditoria externa exigir trilha formal de aprovação além do
   registo operacional do passo 2 da Decisão 4

Quando qualquer destas condições for atingida, este processo é
substituído por fluxo HTTP auditável próprio, especificado em
ADR/DC futura — não decidido aqui.

---

## RELAÇÃO COM ADR-003

Esta decisão fecha apenas **promoção de roles** (capacidade) — não
trata de **autorização de contador sobre documento fiscal**, que é
matéria distinta e tratada na ADR-003.

A hierarquia institucional é:

```
DC-004 (esta):       Quem pode receber capacidade (role)?
ADR-003:             Sobre quem essa capacidade pode actuar (vínculo)?
DT-CONTADOR-01:      Como o código vai aplicar a hierarquia anterior?
```

Esta separação é deliberada e resistente ao tempo. Amanhã, com 10
contadores, 100 empresas, atribuição por admin, pool regional ou
escolha pelo cliente, a regra continua válida:

> Role sem vínculo não autoriza.
> Vínculo sem escopo não autoriza.
> Escopo sem auditoria não prova.

---

## FECHO

```
Promoção de role para o piloto:  processo manual, executado pela
                                  Autoridade Operacional da Plataforma,
                                  com protocolo obrigatório de 5 passos
                                  e trilha soberana registada.

Trilha soberana:                  registo operacional rastreável
                                  (issue, docs/operacao, ou commit
                                  dedicado). Log SQL do banco NÃO
                                  conta como trilha soberana.

Autorização mínima de endpoint:   User.role + PerfilContador.status
                                  conjuntivos. require_role sozinho
                                  é insuficiente.

Limite de admissibilidade:        4 condições de transição declaradas
                                  (5 contadores, frequência semanal,
                                  delegação, auditoria externa).

Endpoint público de promoção:     não autorizado nem no piloto, nem
                                  na abertura inicial.
```

---

*O conhecimento não está na conversa. Está no repositório.*
