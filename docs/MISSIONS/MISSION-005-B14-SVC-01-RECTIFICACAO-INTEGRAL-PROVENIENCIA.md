# MISSION-005 — B14-SVC-01 — Rectificação integral da auditoria de proveniência

**Estado:** PRONTA PARA EXECUÇÃO  
**Autoridade arquitectural:** GPT  
**Autoridade de ratificação:** Miguel  
**Executor técnico:** Codex  
**Gate:** ADR-011-PROVENIENCIA-001  
**Missão de origem:** MISSION-004  
**Relatório a rectificar:** REPORT-004  
**Baseline esperada:** `HEAD = origin/main = 2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f`

---

## 1. Natureza e objectivo

Missão documental, correctiva, probatória e estritamente delimitada.

Executar numa única passagem:

1. comprovar novamente, directamente no código, o inventário canónico do `DataSanitizationContext`;
2. corrigir integralmente o `REPORT-004`, que omitiu `base_calculo` e tratou `regime` como campo contratual;
3. auditar `base_calculo` com a mesma profundidade aplicada aos restantes campos;
4. reposicionar `regime` exclusivamente como dependência auxiliar da fonte candidata e campo extra proibido pela fronteira L3;
5. recolher correctamente o teste autorizado, com preflight de ambiente;
6. criar um relatório de rectificação e evidência;
7. preservar integralmente código, testes, ADRs, contratos, migrations e alterações preexistentes.

Não executar nova auditoria geral do ADR-011. Corrigir apenas o defeito identificado e completar a prova em falta.

---

## 2. Regra de preservação histórica

A `MISSION-004` contém o inventário errado dos oito campos.

Ela é um artefacto histórico já executado e **não pode ser reescrita**.

Não alterar:

`docs/MISSIONS/MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md`

O `REPORT-005` deve registar explicitamente:

- que a origem do erro foi o escopo da MISSION-004;
- que o Codex executou correctamente o inventário que lhe foi fornecido;
- que a MISSION-005 substitui apenas a lista factual de campos e a evidência incompleta;
- que nenhuma responsabilidade arquitectural é atribuída ao executor.

---

## 3. Artefactos autorizados

Pode ser alterado exclusivamente:

`docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md`

Deve ser criado exclusivamente:

`docs/REPORTS/REPORT-005-RECTIFICACAO-INTEGRAL-PROVENIENCIA-DATASANITIZATION.md`

Esta missão pode apenas ser lida:

`docs/MISSIONS/MISSION-005-B14-SVC-01-RECTIFICACAO-INTEGRAL-PROVENIENCIA.md`

Nenhum outro ficheiro pode ser criado, alterado, apagado, renomeado, movido, formatado, restaurado ou adicionado ao stage.

---

## 4. Alterações locais protegidas

Preservar integralmente:

- `app/agents/adapters/ag_encerramento.py`
- `app/agents/engines/ag_encerramento.py`
- `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md`
- `tests/test_ag_encerramento_mission_adapter.py`

É proibido usar:

- `git restore`
- `git checkout`
- `git reset`
- `git add`
- `git stash`

Não limpar o working tree.

Para os quatro ficheiros, comparar índice e working tree normalizado antes e depois:

```text
git rev-parse ":CAMINHO"
git hash-object --path="CAMINHO" "CAMINHO"
```

Não concluir alteração real apenas pela marcação `M` do `git status`.

---

## 5. Estado inicial obrigatório

Executar e registar no `REPORT-005`:

```text
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git status --short
git diff --name-only
git diff --cached --name-only
```

Confirmar:

- branch `main`;
- `HEAD == origin/main`;
- baseline esperada;
- stage vazio;
- `MISSION-004` existe;
- `MISSION-005` existe;
- `REPORT-004` existe;
- `REPORT-005` não existe.

Se `REPORT-005` já existir, interromper sem sobrescrever.

Se existir alteração adicional não autorizada, não corrigir, não restaurar e interromper.

Calcular e registar antes da edição:

- SHA-256 de `MISSION-004`;
- SHA-256 de `REPORT-004`;
- SHA-256 de `MISSION-005`.

Criar cópia temporária do `REPORT-004` fora do repositório para comparação. Apagá-la antes de terminar.

---

## 6. Fonte de verdade obrigatória

Não confiar apenas nesta missão. Confirmar directamente no código.

### 6.1 Inventário canónico

Ler:

- `app/agents/contracts/data_sanitization.py:31-40`
- `app/agents/contracts/data_sanitization.py:143-159`
- definição de `CAMPOS_FISCAIS_CANONICOS`

O conjunto canónico esperado é exactamente:

1. `faturamento`
2. `custos`
3. `lucro_contabil`
4. `lucro`
5. `base_calculo`
6. `icms_pago`
7. `icms_devido`
8. `custo_fiscal_entradas`

`regime` **não** integra `DataSanitizationField` nem `DataSanitizationContext`.

O contexto contém ainda `empresa_id`, que é identidade e não um dos oito campos fiscais.

Se o código observado divergir desta lista, parar e registar a divergência sem editar o relatório.

### 6.2 Fonte candidata

Confirmar directamente:

- `app/services/insights_engine.py:98-121`

Estado esperado a comprovar:

```text
regime = (empresa.regime_tributario or "presumido").lower()
         se Empresa existir; caso contrário "presumido"

lucro = faturamento - custos

base_calculo = lucro
               se regime == "real"
               caso contrário faturamento * 0.08
```

Confirmar também que o dicionário candidato contém:

- os oito campos canónicos;
- `empresa_id`;
- extras como `db`, `data_referencia`, `regime`, `atividade` e `context_flags`.

---

## 7. Correcção obrigatória do inventário no REPORT-004

Corrigir todas as passagens que:

- incluem `regime` entre os oito campos contratuais;
- omitem `base_calculo`;
- chamam os oito campos de “numéricos” de forma absoluta;
- sugerem que `regime` integra o contrato;
- descrevem “base_calculo e os oito campos” como se fossem nove.

Formulação factual obrigatória:

```text
O DataSanitizationContext contém empresa_id e oito campos fiscais
canónicos: faturamento, custos, lucro_contabil, lucro, base_calculo,
icms_pago, icms_devido e custo_fiscal_entradas.

regime não integra o contrato. Na fonte candidata, regime é uma
dependência auxiliar usada para escolher a fórmula de base_calculo
e é também um campo extra rejeitado por extra="forbid" quando o
dicionário bruto é entregue directamente ao adapter.
```

Não remover `regime` do relatório por completo. Mantê-lo apenas nas secções relativas a:

- dependência da fórmula de `base_calculo`;
- default silencioso;
- ausência de validade temporal;
- ausência de domínio formal;
- campo extra incompatível com `extra="forbid"`;
- decisão ainda não ratificada.

---

## 8. Auditoria obrigatória de base_calculo

Adicionar `base_calculo` à matriz dos oito campos, substituindo a linha contratual indevida de `regime`.

A linha e as conclusões devem comprovar, sem inferência:

### Fonte

- deriva de `faturamento`, `custos` e `Empresa.regime_tributario`;
- não deriva de coluna própria persistida;
- depende do estado actual da Empresa.

### Fórmula observada

```text
lucro = faturamento - custos

base_calculo = lucro, se regime == "real"
base_calculo = faturamento * 0.08, nos restantes casos
```

### Lacunas obrigatórias

- semântica fiscal canónica não ratificada;
- percentual `0.08` hardcoded na fonte candidata;
- nenhum fundamento normativo provado nesta missão;
- `regime` ausente, vazio, nulo ou Empresa inexistente conduz silenciosamente a `presumido`;
- regime actual é aplicado a todo o histórico agregado;
- não existe vigência histórica do regime;
- ausência de faturamento/custos já foi colapsada em zero;
- no ramo `real`, resultado negativo de `faturamento - custos` é preservado por esta atribuição;
- no ramo não real, a fórmula não representa prejuízo e depende do valor agregado de faturamento;
- unidade monetária não está formalizada;
- todo o histórico, sem cutoff;
- apenas `empresa_id`, sem actor/tenant/proprietário;
- reproduzibilidade limitada por BD mutável, regime mutável e ausência de snapshot.

Estado esperado, salvo evidência contrária:

`INCOMPATÍVEL COM A FRONTEIRA L3`

Não declarar a fórmula correcta ou canónica. Declarar apenas que está implementada.

---

## 9. Reclassificação obrigatória de regime

Criar no `REPORT-004` uma conclusão clara:

```text
regime é dependência auxiliar da fonte candidata, não campo fiscal
canónico do DataSanitizationContext.
```

Auditar e manter as seguintes lacunas:

- origem `Empresa.regime_tributario`;
- texto sem constraint de domínio comprovada;
- default silencioso `presumido`;
- Empresa inexistente também resulta em `presumido`;
- ausência, vazio e nulo tornam-se indistinguíveis;
- estado actual, sem validade histórica;
- usado para escolher a fórmula de `base_calculo`;
- campo extra rejeitado pelo contrato se enviado directamente.

Não criar linha de `regime` na matriz dos oito campos.

Pode existir uma tabela ou subseção separada de “dependências auxiliares não contratuais”.

---

## 10. Correcções específicas no REPORT-004

Rever e corrigir, no mínimo:

### Secção 4 — Contrato L3 observado

Declarar `empresa_id + oito campos fiscais`, listar os oito exactos e excluir `regime`.

### Secção 6 — Matriz dos oito campos

- remover a linha contratual de `regime`;
- inserir a linha completa de `base_calculo`;
- manter oito linhas exactas.

### Secção 8 — Ausência, zero, negativos e defaults

Distinguir:

- defaults e truncamentos dos campos contratuais;
- `regime` como dependência auxiliar que afecta `base_calculo`.

### Secção 10 — Compatibilidade com extra="forbid"

Declarar:

- o contrato aceita `empresa_id` e os oito campos exactos;
- os valores fiscais aceitam tipos estritos previstos pelo contrato, não apenas numéricos;
- `db`, `data_referencia`, `regime`, `atividade` e `context_flags` são extras;
- Session não pode atravessar a fronteira;
- o dicionário bruto não pode ser entregue directamente.

### Secção 12 — Requisitos mínimos

Acrescentar que o futuro projector deve:

- projectar `base_calculo` apenas após decisão ratificada de fórmula;
- não transportar `regime`;
- utilizar `regime` somente como input autorizado e temporalmente coerente, se a decisão futura o ratificar.

### Secção 13 — Decisões ainda não ratificadas

Incluir explicitamente:

- significado canónico de `base_calculo`;
- fórmula por regime;
- autoridade normativa do percentual;
- vigência temporal do regime;
- comportamento perante regime ausente.

### Secção 15 — Matriz do gate

Substituir a cobertura indevida de `regime` por itens separados:

- `Base de cálculo — fonte/fórmula/semântica`
- `Dependência auxiliar regime — domínio/default/vigência`

Ambos devem continuar a bloquear integração produtiva enquanto não ratificados.

### Secção 16 — Riscos

Incluir:

- regime actual aplicado a histórico integral;
- default presumido;
- fórmula não ratificada de `base_calculo`;
- percentual hardcoded;
- omissão anterior de `base_calculo` corrigida por esta missão.

### Secção 19 — Estado da execução

Actualizar o estado do teste de acordo com a recolha correcta.

---

## 11. Protocolo único de teste

Executar a partir da raiz exacta:

`C:\dev\saas-fiscal-demo`

### 11.1 Preflight obrigatório

Registar:

```text
Get-Location
python --version
python -c "import os,sys; print(os.getcwd()); print(sys.executable); import app; print(app.__file__)"
```

Critérios:

- directório actual deve ser `C:\dev\saas-fiscal-demo`;
- `sys.executable` deve apontar para o Python esperado do ambiente;
- `import app` deve funcionar antes de iniciar pytest.

### 11.2 Teste autorizado

Executar exclusivamente:

```text
python -m pytest -q tests/test_data_sanitization_mission_adapter.py
```

Não executar a suite completa.

Não modificar testes.

### 11.3 Diagnóstico permitido se o preflight falhar

Pode executar somente:

```text
python -c "import os,sys; print(os.getcwd()); print(sys.executable); print(sys.path)"
Get-ChildItem -Name app
```

Não alterar `PYTHONPATH`, configurações, ambiente, código ou testes.

Se o preflight comprovar que o comando foi lançado fora da raiz, mudar apenas o directório de trabalho para a raiz e repetir uma vez.

Se `import app` continuar a falhar na raiz com o Python correcto, registar e parar a recolha do teste.

### 11.4 Interpretação obrigatória

Mesmo que todos os testes passem:

- isso prova apenas contrato, engine e adapter isolados cobertos pelo ficheiro;
- não prova a fonte produtiva candidata;
- não prova reader/projector;
- não fecha ADR-011;
- não autoriza integração produtiva.

Actualizar a matriz do gate para reflectir exactamente essa fronteira de prova.

---

## 12. Validação textual obrigatória

Após a rectificação, confirmar no `REPORT-004`:

### Presença obrigatória

- `base_calculo`
- `regime é dependência auxiliar`
- `regime não integra o contrato`
- `faturamento * 0.08`
- `regime == "real"`
- `extra="forbid"`
- `CONTEXTO_SEM_CAMPOS_FISCAIS`
- resultado literal do teste autorizado
- gate permanece aberto

### Ausência obrigatória de formulações erradas

- lista dos oito campos contendo `regime`;
- matriz dos oito campos com linha contratual de `regime`;
- lista dos oito campos sem `base_calculo`;
- “base_calculo e os oito campos”;
- afirmação de que `regime` integra o contrato;
- afirmação de que os oito campos são necessariamente apenas numéricos.

Confirmar que a matriz contém exactamente oito linhas de campos contratuais.

---

## 13. Comparação antes e depois

Comparar o `REPORT-004` rectificado com a cópia temporária.

Alterações permitidas exclusivamente nos grupos:

1. inventário canónico;
2. auditoria de `base_calculo`;
3. reclassificação de `regime`;
4. compatibilidade contratual;
5. decisões/riscos/matriz do gate relacionados;
6. resultado do teste;
7. estado final coerente.

Não reescrever o documento inteiro.

Não normalizar conteúdo não relacionado.

Registar hashes antes e depois e resumo dos hunks no `REPORT-005`.

Apagar a cópia temporária antes do fim.

---

## 14. Estrutura obrigatória do REPORT-005

Criar:

`docs/REPORTS/REPORT-005-RECTIFICACAO-INTEGRAL-PROVENIENCIA-DATASANITIZATION.md`

Estrutura:

```text
# REPORT-005 — Rectificação integral da auditoria de proveniência

## 1. Identificação da missão
## 2. Origem arquitectural do defeito
## 3. Estado inicial do repositório
## 4. Hashes iniciais
## 5. Inventário canónico comprovado
## 6. Rectificação de base_calculo
## 7. Reclassificação de regime
## 8. Rectificações aplicadas ao REPORT-004
## 9. Preflight do ambiente
## 10. Resultado do teste autorizado
## 11. Limites da prova de teste
## 12. Validação textual
## 13. Comparação antes e depois
## 14. Hashes finais
## 15. Estado do gate
## 16. Estado final do repositório
## 17. Declaração de preservação
## 18. Estado da execução
```

Para cada rectificação:

```text
Estado: APLICADA | NÃO APLICADA | INTERROMPIDA
Local rectificado:
Evidência do código:
Formulação anterior:
Formulação correcta:
Validação:
```

O `REPORT-005` deve declarar expressamente que o defeito teve origem na MISSION-004 e não numa decisão autónoma do Codex.

---

## 15. Estado final obrigatório

Executar e registar:

```text
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git status --short
git diff --name-only
git diff --cached --name-only
```

Recalcular:

- SHA-256 de `MISSION-004`;
- SHA-256 de `REPORT-004`;
- SHA-256 de `MISSION-005`.

Confirmar:

- hash de `MISSION-004` inalterado;
- `REPORT-004` rectificado;
- apenas `REPORT-005` criado pelo executor;
- `MISSION-005` não alterada;
- quatro ficheiros protegidos preservados;
- cópia temporária removida;
- stage vazio;
- nenhum commit;
- nenhum push;
- `HEAD == origin/main`.

Estado final permitido:

```text
M app/agents/adapters/ag_encerramento.py
M app/agents/engines/ag_encerramento.py
M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
M tests/test_ag_encerramento_mission_adapter.py

?? docs/MISSIONS/MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md
?? docs/MISSIONS/MISSION-005-B14-SVC-01-RECTIFICACAO-INTEGRAL-PROVENIENCIA.md
?? docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md
?? docs/REPORTS/REPORT-005-RECTIFICACAO-INTEGRAL-PROVENIENCIA-DATASANITIZATION.md
```

Nenhum outro ficheiro pode aparecer.

---

## 16. Critério de conclusão

A missão será `EXECUTADA` apenas se:

- o inventário canónico for comprovado directamente no código;
- `base_calculo` integrar a matriz dos oito campos;
- `regime` deixar de ser tratado como campo contratual;
- a fórmula observada e todas as suas lacunas forem documentadas;
- o teste for executado com preflight correcto ou a impossibilidade ambiental for provada;
- o REPORT-004 for rectificado integralmente;
- o REPORT-005 for criado;
- a MISSION-004 permanecer imutável;
- nenhum código, teste, ADR, contrato ou migration for alterado;
- stage permanecer vazio;
- nenhum commit ou push for efectuado.

---

## 17. Conclusão permitida

O Codex deve terminar apresentando:

```text
Estado da execução:
EXECUTADA | EXECUTADA COM PENDÊNCIAS | INTERROMPIDA

Relatório rectificado:
docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md

Relatório criado:
docs/REPORTS/REPORT-005-RECTIFICACAO-INTEGRAL-PROVENIENCIA-DATASANITIZATION.md

MISSION-004:
PRESERVADA — hash inalterado

Teste autorizado:
RESULTADO LITERAL

Outros ficheiros alterados:
NENHUM

Gate ADR-011-PROVENIENCIA-001:
ABERTO — decisão GPT e ratificação Miguel pendentes

Stage:
VAZIO

Commit:
NÃO EFECTUADO

Push:
NÃO EFECTUADO

Auditoria:
PENDENTE — autoridade GPT

Ratificação:
PENDENTE — autoridade Miguel
```

---

## 18. Regra final

Perante dúvida, conflito, alteração inesperada ou evidência divergente:

```text
PARAR
REGISTAR
NÃO CORRIGIR FORA DO ESCOPO
NÃO REESCREVER A MISSION-004
NÃO IMPLEMENTAR
NÃO AMPLIAR
NÃO COMMITAR
NÃO FAZER PUSH
```
