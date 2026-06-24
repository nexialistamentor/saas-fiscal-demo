# ADR-005 — Carteira Contador Anti-Captura

**Data:** 2026-06-24  
**Estado:** Aprovado  
**Autores:** Miguel (produto), Claude (análise), GPT (auditoria arquitectural)  
**Repositório:** nexialistamentor/saas-fiscal-demo

---

## Contexto

A plataforma Tributária L2 admite contadores parceiros que trazem as suas carteiras de clientes (empresas). O risco identificado é de captura: a plataforma poderia usar o acesso aos dados para substituir o contador, contactar directamente os clientes ou favorecer outro contador.

O modelo actual de `ContadorEmpresaVinculo` regista `origem` (quem criou tecnicamente o vínculo), mas não distingue de onde veio a **relação comercial** do cliente.

---

## Decisão

### 1. Separação de responsabilidades no vínculo

O campo `origem` representa **quem criou tecnicamente o vínculo**:
- `admin` — acto técnico feito pelo administrador da plataforma
- `cliente` — vínculo criado pelo próprio cliente/empresa
- `sistema` — criação automática por regra determinística

O novo campo `origem_cliente` representa **de onde veio a relação comercial**:
- `contador_parceiro` — empresa veio da carteira de um contador parceiro
- `plataforma_directa` — empresa entrou directamente pela plataforma
- `empresa_directa` — empresa estabeleceu relação directa sem intermediário
- `legado` — vínculos anteriores a esta ADR (backfill retroactivo apenas)

**Nunca misturar os dois campos.** Exemplo correcto no piloto:

```
origem = "admin"                      # admin criou o vínculo tecnicamente
origem_cliente = "contador_parceiro"  # empresa veio da carteira do contador
```

### 2. Invariantes anti-captura

**INV-CARTEIRA-01:** Cliente originado por contador parceiro fica vinculado à carteira desse contador enquanto houver vínculo activo, salvo revogação expressa, consciente e auditada pela empresa.

**INV-CARTEIRA-02:** A plataforma não pode substituir, sugerir troca ou capturar cliente de contador parceiro sem acto explícito e auditado.

**INV-CARTEIRA-03:** O contador não pode prender o cliente. A empresa mantém direito de revogação, portabilidade e troca auditada.

**INV-CARTEIRA-04:** Nenhuma empresa entra na carteira do contador só porque foi declarada. Ela entra quando o dossiê está apto e o vínculo é ratificado pelo admin.

**INV-CARTEIRA-05:** `origem_cliente = "contador_parceiro"` só pode ser definido no momento da criação do vínculo — nunca alterado retroactivamente para capturar carteira alheia.

**INV-CARTEIRA-06:** `origem_cliente = "legado"` é permitido apenas para vínculos anteriores à ADR-005 (backfill histórico da migration 0014). Novos vínculos devem declarar `origem_cliente` explicitamente. O service e o endpoint deverão rejeitar omissão de `origem_cliente` em vínculos novos.

### 3. Modelo de aptidão para piloto

Para o piloto, o fluxo soberano é:

```
contador apresenta empresa
→ plataforma valida documentos/CNPJ
→ agente trata pendências
→ empresa classificada como "apta_para_ratificacao"
→ admin ratifica com 1 clique
→ vínculo nasce com origem="admin", origem_cliente="contador_parceiro"
```

O admin não faz trabalho operacional. O admin exerce autoridade final sobre dossiê já preparado.

### 4. Troca de contador

Troca de contador exige acto explícito:

```
empresa solicita troca
→ sistema mostra aviso claro
→ contador actual é notificado
→ motivo fica registado
→ período de transição opcional
→ novo vínculo só nasce com aceite explícito
```

Nunca automático. Nunca silencioso.

### 5. Estados do PerfilContador

Para implementação futura de auto-candidatura controlada:

```
pendente          — aguarda verificação
em_verificacao    — plataforma/agente a processar
pre_verificado    — apto para ratificação
aprovado          — ratificado pelo admin
reprovado         — não passa nos critérios
suspenso          — acesso suspenso temporariamente
revogado          — acesso permanentemente encerrado
```

Para o piloto V1, apenas `pendente` e `aprovado` são utilizados.

---

## Consequências

### O que muda

- `ContadorEmpresaVinculo` recebe coluna `origem_cliente` (migration 0014)
- `app/models.py` deverá incluir `origem_cliente` e `CheckConstraint` correspondente
- `VinculoAdminService.criar_vinculo_contador_empresa` deverá aceitar e validar `origem_cliente`
- Endpoint `POST /admin/contadores/vinculos` deverá aceitar `origem_cliente` no payload
- Listagem `GET /admin/contadores/vinculos` deverá expor `origem_cliente` para auditoria
- Novos vínculos deverão declarar `origem_cliente` explicitamente — omissão deverá ser rejeitada

### O que não muda

- `origem` continua com semântica de "quem criou tecnicamente"
- Vínculos existentes recebem `origem_cliente = "legado"` por backfill (migration 0014)
- Escopos V1 fechados: `homologacao_documental`, `parecer_tecnico`, `analise_xml`
- INV-VINCULO-01 a INV-VINCULO-05 permanecem activos

### Dívida registada

- B10-CARTEIRA-02: fila de aptidão de empresas trazidas por contador (agente prepara, admin ratifica)
- Fluxo de convite público de contador fica para fase posterior (não piloto V1)
- Teste mínimo: criar vínculo com/sem `origem_cliente` e validar rejeição de omissão

---

## Alternativas rejeitadas

- **Campo JSON no `escopo`:** rejeitado porque `origem_cliente` é regra de negócio central — deve ser pesquisável, indexável, testável e visível no modelo de dados.
- **`server_default="legado"` permanente:** rejeitado — permitiria que código futuro omitisse `origem_cliente` silenciosamente, destruindo a auditoria.
- **Auto-candidatura pública imediata:** rejeitada por risco de fraude, CNPJ falso e captura de carteira.
- **Contador cria vínculo sozinho:** rejeitado — vínculo nasce de ratificação, não de declaração unilateral.

---

## Frase de controlo

> A plataforma não rouba carteira.  
> O contador não prende cliente.  
> O vínculo protege a relação, e a auditoria protege todos.  
> `origem` diz quem criou o vínculo. `origem_cliente` diz de quem é a carteira.  
> `legado` explica o passado. Não pode esconder omissão no futuro.
