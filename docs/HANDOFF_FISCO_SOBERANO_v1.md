# Para o próximo Claude — lê isto antes de qualquer linha de código

**Data:** 2026-06-28  
**HEAD:** `22ef7a2`  
**Suite:** 407 passed / 0 failed / 8 skipped  
**Produção:** https://saas-fiscal-demo-production.up.railway.app/health → 200 OK  
**Frontend:** https://www.fiscosoberano.com.br (domínio activo, DNS propagado)  

---

## 1. QUEM SOMOS E COMO TRABALHAMOS

**Miguel** — fundador e product authority. Decisão final é sempre dele.  
**Claude** — produção de código e análise.  
**GPT** — auditor arquitectural. Todo patch estrutural vai ao GPT antes de executar.  
**Cursor** — executor em disco. Claude não tem acesso directo ao repositório.

**Protocolo de trabalho:**
1. Claude lê o ficheiro real antes de propor qualquer patch
2. GPT audita patches estruturais
3. Cursor aplica, testa, commita
4. Suite tem de estar verde antes de qualquer commit
5. PowerShell usa `;` nunca `&&`
6. Scripts auxiliares (patch_*.py) vão ao `.gitignore` — nunca ao repositório

**Regra de ouro:** SER PROACTIVO, NÃO REACTIVO.  
Antes de propor código, mapear o que existe. Antes de criar, auditar.  
A plataforma já tem 137 ficheiros de serviços/agentes/motores — não duplicar.

---

## 2. OS DOIS PROJECTOS

### Fisco Soberano (activo — foco actual)
- **Repo:** `nexialistamentor/saas-fiscal-demo`
- **Backend:** FastAPI + PostgreSQL (Railway)
- **Frontend:** React/Vite (Vercel)
- **Domínio:** `fiscosoberano.com.br` (registado Registro.br, expira 26/06/2027)
- **Missão:** democratizar inteligência fiscal Big4 para PMEs brasileiras
- **Filosofia:** motor fiscal = código determinístico; contador = gate condicionado por lei, nunca dependência universal

### Cartório Digital Soberano L2 (paralelo, não activo nesta sessão)
- **Repo:** `nexialistamentor/cartorio-soberano`
- **Estado:** Fase 2 C2 em produção desde 2026-06-17
- Não misturar com Fisco Soberano

---

## 3. ARQUITECTURA CHAVE — FISCO SOBERANO

### Motores activos (não recriar)
| Motor | Ficheiro | Função |
|-------|---------|--------|
| `MEITaxEngine` | `app/services/tax_engines/mei_tax_engine.py` | DAS MEI, limite anual, alertas |
| `regime_engine.py` | `app/services/regime_engine.py` | Compara MEI/Simples/LP/LR, Fator R |
| `cnae_engine.py` | `app/services/cnae_engine.py` | Recomenda CNAE, detecta `permite_mei` |
| `formalizacao_router.py` | `app/routers/formalizacao_router.py` | `/formalizacao/recomendar-cnae`, `/comparar-regimes`, `/simular-empresa` |

### Invariantes arquitecturais
- `calculo_autorizado=False` = travão soberano
- `permite_mei` = actividade pode ser MEI (não = porte escolhido)
- Contador condicionado por lei/obrigação técnica/risco/escolha — nunca obrigatório universal
- XML_FISCAL não passa pelo `extractor.py`
- `EvidenciaFiscalComparavel` importada de `evidencia_comparavel.py` (módulo neutro)
- Chave NF-e sem DV válido não é evidência fiscal canónica

### Pipeline documental (Bloco 5 — fechado)
```
XML_FISCAL (.nexialista) → EvidenciaFiscalComparavel(origem="xml_fiscal")
DANFE PDF               → EvidenciaFiscalComparavel(origem="danfe_pdf")
DANFE imagem (OCR+DV)   → EvidenciaFiscalComparavel(origem="danfe_imagem")
                          ↓
                    conciliar() → "conciliado"|"divergente"|"inconclusivo"
```

---

## 4. ESTADO DOS BLOCOS

### Fechados
| Bloco | O que fez | Commit(s) |
|-------|----------|----------|
| B1 | Núcleo XML, `/upload-xml` canónico | `ee7b0ac` |
| B2 | Relatório PDF, memorial | — |
| B5 | Ponte documental completa | `b0c3ec5`→`15591cf` |
| B9 | Identidade/permissões/multi-tenant | `240e573` |
| B10 | Jornada utilizador/contador | `b803e29`→`def3f53` |
| B11 fase 1 | Segurança/LGPD, ADR-006 | `4066b4d` |
| B12 | Produção/monitorização, deploy checklist | `922b4d3`→`dd3e300` |
| B13 (parcial) | Piloto controlado — ver estado abaixo | múltiplos |

### B13 — Estado detalhado

#### Fechados em B13
| Tarefa | Commit |
|--------|--------|
| B13-00 Linguagem soberana no agente | `649649b` |
| B13-01 Card simulação abertura frontend | `649649b` |
| B13-02 Roteiro testes utilizador leigo | `cd84ee8` |
| B13-P0-01 CNAE software → 62xx | `7121e32` |
| B13-P0-02 MEI + R$500k inelegível | `7121e32` |
| B13-P0-03 Faturamento zero soberano | `1d18900` |
| B13-P0-06 Gate de termos antes de setUsuario() | `d9f31b4` |
| B13-UX Mensagens de erro claras no login/registo | `700cc9e` |
| fix CORS fiscosoberano.com.br | `8f453c7` |
| fix Contador não obrigatório checklists | `9d6eb02` |

#### Pendentes em B13
| Tarefa | Prioridade | Descrição |
|--------|-----------|----------|
| **B13-P0-07** | P0 | CTA "Fazer login aqui" não preenche email no formulário de login — `setEmail(emailRegisto)` em falta no onClick |
| **Piloto 0 manual** | P0 | Executar T1-T8 em `www.fiscosoberano.com.br` modo anónimo |
| **PILOTO_0_FEEDBACK.md** | P0 | Criar após piloto |
| T8 mobile | P1 | Teste mobile no domínio real |

#### Próximo passo imediato (primeira tarefa ao abrir nova sessão)
**Corrigir B13-P0-07:**
```javascript
// App.jsx — linha ~645 — CTA "Fazer login aqui"
// Mudar:
onClick={() => setMostrarRegisto(false)}
// Para:
onClick={() => { setEmail(emailRegisto); setMostrarRegisto(false) }}
```

Âncora exacta:
```
onClick={() => setMostrarRegisto(false)}
style={{ background: "none", border: "none", color: "#6366f1", cursor: "pointer", textDecoration: "underline", padding: 0, fontSize: 12 }}
```

Depois: build → pytest → commit → push → teste manual `www.fiscosoberano.com.br`.

---

## 5. ROADMAP APÓS B13

```
B13 (fechar)  → Piloto controlado completo
B14           → Matriz autonomia + Wizard abertura + Motor MEI visível
B15           → REDESIM/Portal + API CNPJ + acompanhamento protocolo
B16           → LLMRouter/DeepSeek + Agentes com evidência real
```

**Roadmap OPS (paralelo a B14+):**
```
B13-OPS-01  → Prova de actualização tributária (manifest.json + sentinelas)
B13-OPS-02  → LLMRouter DeepSeek (deepseek-v4-flash, nunca deepseek-chat)
B13-OPS-03  → AgentLearningMode — contrato EventoOperacional + sanitização
B13-OPS-04  → Circuito fechado: erro → diagnóstico → teste → aprovação → regressão
```

Ver `docs/ROADMAP_OPS_AGENTES.md` para detalhe completo.

---

## 6. DOCUMENTOS CRÍTICOS NO REPO

| Ficheiro | O que é |
|---------|---------|
| `docs/ROADMAP_ABERTURA_UTILIZADORES.md` | Roadmap principal — Blocos 1-13 |
| `docs/ROADMAP_OPS_AGENTES.md` | Circuito operacional e agentes |
| `docs/L3_READY_PRINCIPIOS_ABERTURA_EMPRESA.md` | Princípios arquitecturais L3 |
| `docs/B13_TESTES_USUARIO_LEIGO.md` | Roteiro testes + Anexo L3 |
| `docs/ADR-006-DADOS-SENSIVEIS-LGPD-PILOTO.md` | LGPD — CPF/CNPJ como dados operacionais |
| `docs/DEPLOY_CHECKLIST.md` | Deploy, rollback, backup |
| `app/services/tax_engines/mei_constants.py` | Fonte canónica MEI |
| `data/cnae/cnae_keywords.json` | Keywords CNAE + lista curada 62xx |

---

## 7. ERROS ENCONTRADOS NO PILOTO 0 (lições)

| Erro | Causa | Fix |
|------|-------|-----|
| CNAE software → 5811 (edição livros) | Filtro usava keywords do utilizador contra descrição IBGE | Lista curada 62xx + gatilho tech |
| MEI + R$500k sem alerta | Validação não existia no router | Validação explícita com `MEI_LIMITE_ANUAL_FATURAMENTO` |
| Faturamento zero → 422 técnico | Validator `gt=0` em `SimularEmpresaRequest` | Mudado para `ge=0` + resposta soberana |
| Ecrã apagado após login | Race condition: `setUsuario()` disparava hooks antes de `has-accepted-terms` | Mover verificação de termos para antes de `setUsuario()` |
| Vercel servindo bundle antigo | `VITE_API_URL` estava vazia na variável de ambiente Vercel | Preencher variável + redeploy |
| CTA "Fazer login aqui" não preenche email | `onClick` só faz `setMostrarRegisto(false)`, não `setEmail(emailRegisto)` | **Pendente — B13-P0-07** |

---

## 8. KILLS SWITCHES OBRIGATÓRIOS (agentes)

```env
AGENTS_ENABLED=false
AGENT_LEARNING_MODE=true
AGENT_AUTO_PATCH=false
AGENT_AUTO_COMMIT=false
AGENT_AUTO_DEPLOY=false
DEEPSEEK_DRY_RUN=true
```

**Nunca activar agentes sem estes switches definidos explicitamente.**

---

## 9. REGRAS QUE NUNCA MUDAM

1. Ler ficheiro real antes de propor patch
2. GPT audita estrutural antes de executar
3. Suite verde antes de qualquer commit
4. Contador como excepção governada — nunca dependência central
5. `permite_mei` = actividade pode ser MEI (não = porte escolhido)
6. DeepSeek não decide fiscalmente — analisa e sugere
7. Nunca enviar dados fiscais brutos ao LLM — sanitização obrigatória
8. `deepseek-chat` está depreciado (2026-07-24) — usar `deepseek-v4-flash`
9. Auto-commit e auto-deploy nunca acontecem sem aprovação humana
10. A plataforma conduz o que puder com dados públicos — gov.br/REDESIM não são substituídos

---

## 10. PRIMEIRA ACÇÃO AO ABRIR NOVA SESSÃO

```
1. Ler este HANDOFF
2. Verificar HEAD: git log --oneline -5
3. Verificar suite: python -m pytest tests/ --tb=short -q
4. Verificar produção: curl.exe https://saas-fiscal-demo-production.up.railway.app/health
5. Corrigir B13-P0-07 (CTA login)
6. Executar Piloto 0 manual em www.fiscosoberano.com.br
7. Criar PILOTO_0_FEEDBACK.md
8. Avançar para B13-OPS-01 (manifest.json fontes tributárias)
```

---

*Foi construído com rigor soberano. A plataforma já tem os motores — falta ligar o circuito operacional.*
