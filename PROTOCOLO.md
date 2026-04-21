# PROTOCOLO OBRIGATÓRIO — INÍCIO DE SESSÃO

## 1. ESTADO DO REPOSITÓRIO (executar antes de qualquer código)

```
git branch                             # branch actual
git status --short                     # ficheiros modificados
git log --oneline -5                   # últimos commits locais
git branch -r                          # todas as branches remotas
git log --oneline origin/main -3       # estado de produção
git log --oneline origin/principal -3  # estado de produto
```

## 2. CONFIRMAR ANTES DE QUALQUER BRANCH NOVA

- Qual branch é produção?
- Qual branch é a base correcta para o PR?
- A branch local está sincronizada com o remoto?
- Existem conflitos potenciais com outras branches activas?

## 3. IDENTIFICAR RISCOS ANTES DE AGIR

- Mapear todos os pontos de dependência antes de escrever código
- Identificar pontos fracos e fortalecer antes de avançar
- Nunca assumir comportamento sem prova (log, diff, output real)
- Se algo parece estranho — parar e investigar antes de continuar

## 4. NÚCLEO DE DADOS — REGRA ABSOLUTA

- Nunca tocar no núcleo da verdade de dados sem isolamento suficiente
- Nunca alterar lógica de dados sem decompor por intenção primeiro
- Cada alteração ao núcleo = uma intenção = um commit
- Sem prova de que o isolamento está garantido → não avançar

## 5. REGRAS DE COMMIT

- 1 commit = 1 intenção
- Ver git diff completo antes de qualquer commit
- Nunca commitar ficheiros não auditados
- Build limpo obrigatório antes de push

## 6. REGRAS DE PR

- Confirmar base do PR antes de criar
- Confirmar que a base está sincronizada com produção
- Nunca force push em branches partilhadas
- Verificar git log base..head antes de abrir PR

## 7. MOTOR FISCAL = CÓDIGO (lei do projecto)

- Cálculo fiscal → backend sempre
- API externa → tradução/orientação, nunca verdade
- Frontend → apresenta, nunca calcula
- Qualquer excepção a esta regra exige aprovação explícita
