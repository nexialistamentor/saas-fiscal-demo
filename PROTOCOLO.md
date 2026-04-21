# PROTOCOLO SOBERANO L2 — OBRIGATÓRIO EM CADA SESSÃO

---

## 0. ANTES DE QUALQUER ACÇÃO — ESTADO DO REPOSITÓRIO

```powershell
git branch                              # branch actual
git status --short                      # ficheiros modificados
git log --oneline -5                    # últimos commits locais
git branch -r                           # todas as branches remotas
git log --oneline origin/main -3        # estado de produção
git log --oneline origin/principal -3   # estado de produto
```

---

## 1. CONFIRMAR ANTES DE QUALQUER BRANCH NOVA

- Qual branch é produção?
- Qual branch é a base correcta para o PR?
- A branch local está sincronizada com o remoto?
- Existem conflitos potenciais com outras branches activas?

---

## 2. IDENTIFICAR RISCOS ANTES DE AGIR

- Mapear todos os pontos de dependência antes de escrever código
- Identificar pontos fracos e fortalecer antes de avançar
- Nunca assumir comportamento sem prova (log, diff, output real)
- Se algo parece estranho — parar e investigar antes de continuar

---

## 3. NÚCLEO DE DADOS — REGRA ABSOLUTA

- Nunca tocar no núcleo da verdade de dados sem isolamento suficiente
- Nunca alterar lógica de dados sem decompor por intenção primeiro
- Cada alteração ao núcleo = uma intenção = um commit
- Sem prova de que o isolamento está garantido → não avançar

---

## 4. ARQUITECTURA OFICIAL — NÃO VIOLAR

Pipeline obrigatório para todo XML:

`executar_analise_xml` (núcleo)

→ `executar_e_registrar_analise_xml` (persistência)

→ `processar_e_persistir_xml` (integração empresa)

→ InsightEngine (enriquecimento)

→ dados estruturados no banco

→ agents sob gatilho (não automático)

**PRINCÍPIO CENTRAL:**

persistir primeiro → enriquecer depois → só então usar inteligência

---

## 5. REGRAS CRÍTICAS DE CÓDIGO

- NÃO criar novos fluxos de análise XML
- NÃO duplicar lógica existente
- NÃO criar novas rotas se já existir equivalente
- NÃO alterar `motor_fiscal` sem necessidade explícita
- NÃO usar LLM para processamento primário
- NÃO ler XML bruto se já existe dado persistido
- NÃO ignorar base normativa (TabelaMVA)

**Antes de gerar qualquer código, verificar:**

- Isso já existe?
- Isso cria duplicação?
- Isso quebra arquitectura?
- Isso escala?
- Isso aumenta custo?

Se qualquer resposta for "sim" → NÃO gerar código novo.

---

## 6. BASE NORMATIVA

- Fonte de verdade: `tabela_mva`
- NÃO usar fallback JSON como fonte primária
- NÃO hardcodar regras tributárias
- SEMPRE usar: `buscar_mva`, `carregar_mva`

---

## 7. AGENTS — LIMITES ESTRITOS

Agents NÃO fazem:

- Processamento de XML
- Leitura directa de XML bruto

Agents SÓ fazem:

- Interpretação de dados já persistidos
- Geração de insights
- Alertas sob gatilho

---

## 8. CONTROLO DE CUSTO

- Evitar chamadas desnecessárias a LLM
- Evitar reprocessamento de XML
- Usar cache sempre que possível
- Priorizar lógica determinística

---

## 9. REGRAS DE COMMIT

- 1 commit = 1 intenção
- Ver `git diff` completo antes de qualquer commit
- Nunca commitar ficheiros não auditados
- Testar localmente antes de commitar
- Build limpo obrigatório antes de push

---

## 10. REGRAS DE PR

- Confirmar base do PR antes de criar
- Confirmar que a base está sincronizada com produção
- Nunca force push em branches partilhadas
- Verificar `git log base..head` antes de abrir PR

---

## 11. MOTOR FISCAL = CÓDIGO (lei do projecto)

- Cálculo fiscal → backend sempre
- API externa → tradução/orientação, nunca verdade
- Frontend → apresenta, nunca calcula
- Qualquer excepção exige aprovação explícita

---

## 12. STACK E CONTEXTO

- Backend: FastAPI + SQLAlchemy + PostgreSQL
- Processamento: Motor fiscal + InsightEngine
- Fila: Redis + RQ
- Frontend: React (Vite)
- Agents: AgentScheduler, AgentExecutor, AgentRegistry
- Produção: Railway (backend) + Vercel (frontend)
- Branch de produção: `main` → Railway
