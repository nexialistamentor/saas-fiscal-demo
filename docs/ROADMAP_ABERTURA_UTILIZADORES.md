# ROADMAP_ABERTURA_UTILIZADORES.md — Plataforma Tributária L2

**Versão:** 2.0
**Data:** 2026-06-20
**Natureza:** Roadmap operacional. Organiza, em blocos sequenciais com
  critério de saída explícito, tudo o que falta antes de abrir a
  plataforma a utilizadores reais.
**Base:** MAPA_REALIDADE_TRIBUTARIA_L2, CONSTITUICAO_TRIBUTARIA_L2,
  MAPA_DOMINIOS_SOBERANOS, MAPA_AUTORIDADES_L2, PM_L2_001, ADR-001,
  ADR-002, CT-DOC-001 (+ adendo v1.1 + correcção A.5), alinhamento
  GPT de 2026-06-20 (DANFE bloqueado, XML livre; reforço de
  blocos de abertura real).
**Princípio:** cada bloco tem critério de saída verificável. Não se
  avança para o bloco seguinte sem o critério anterior estar
  cumprido e documentado.

**Mudança de v1.0 para v2.0:** a versão 1.0 cobria um roadmap
técnico-institucional (motor, dados, agentes, infra). A auditoria do
GPT identificou que isso não basta — motor correcto não é, por si só,
produto pronto para abertura. v2.0 acrescenta cinco blocos de
abertura real: identidade/permissões, jornada de utilizador,
segurança/LGPD, produção/rollback, e piloto controlado.

---

## PRINCÍPIO FINAL DE ABERTURA

A plataforma só deve abrir a utilizadores reais quando estes cinco
pontos estiverem verdadeiros, simultaneamente:

1. O motor XML produz resultado consistente.
2. O utilizador entende o resultado.
3. O contador sabe onde entra.
4. Os dados estão protegidos.
5. A operação consegue responder a erro real.

> Não estamos só a abrir código. Estamos a abrir responsabilidade fiscal.

---

## ESTADO HERDADO (não repetir, já resolvido)

| Item | Estado | Commit |
|------|--------|--------|
| Fundação institucional completa (Constituição → Pré-Mortem) | ✔ | 448a959…f796a8e |
| ADR-001 — Governação da Canonicidade | ✔ | bdafc62 |
| ADR-002 — Ponte de Promotion Documental-Fiscal | ✔ | 029d709 |
| CT-DOC-001 + adendo v1.1 + correcção A.5 | ✔ | 7552e0d, b75f891, bcc15ee |
| DT-DOC-01 — `campos_estruturados` | ✔ | fcba03d |
| DT-DOC-03 — elegibilidade fiscal conservadora | ✔ | 1b7948a |
| 0009 — `conteudo_sha256` em `documentos_fiscais` | ✔ | d1dc8b6 |

**Bloqueado por desenho, não esquecido:**
- DT-DOC-02a (`valor_icms`) e DT-DOC-02c (`numero_nota`, `tipo`,
  `uf_emit`, `uf_dest`) — aguardam amostra real de DANFE/OCR (pedida
  a contador). **Não retomar sem essa amostra.**
- A.4 / candidata DT-DOC-04 — destino de CNPJ/CPF em `DocumentoFiscal`
  — pendência separada, não bloqueante.
- Service de promotion documental-fiscal — depende dos dois pontos
  acima.

---

## BLOCO 0 — DISCIPLINA TRANSVERSAL (aplica-se a todos os blocos)

- [ ] Toda alteração estrutural segue ADR-001: Evidência → Auditoria
      → Ratificação
- [ ] Nenhum service novo escreve directamente em `DocumentoFiscal`
      fora do pipeline canónico sem ADR próprio
- [ ] Nenhum valor monetário novo usa `float` — sempre `Decimal`/`Numeric`
- [ ] PowerShell: `;` nunca `&&`
- [ ] Nenhum código sem ler o ficheiro real primeiro
- [ ] Nenhuma regex sobre texto/formato não confirmado por amostra real
- [ ] Cada bloco fechado actualiza este roadmap (marcar `[x]`) antes
      de avançar para o seguinte

---

## BLOCO 1 — NÚCLEO FISCAL XML (PRIORIDADE IMEDIATA)

**Objectivo:** o motor fiscal por XML, já canónico e auditável, fica
robusto, demonstrável e sem dívida activa conhecida.

### 1.1 — Auditoria de estado actual
- [ ] Confirmar estado real de `/fiscal/analisar-xml`, `/upload-xml`,
      `/lote/analisar-lote` — reconfirmar DT-FLUXO-01/02/03
- [ ] Listar testes existentes do pipeline XML, correr suite isolada
- [ ] Confirmar cobertura real do `InsightEngine` (16+ analisadores)

### 1.2 — Resolução de dívidas já nomeadas
- [ ] DT-FLUXO-01 — `/upload-xml`: integrar no pipeline canónico ou
      declarar formalmente como caminho secundário não-auditável
- [ ] DT-FLUXO-02 — mesma decisão para `/lote/analisar-lote`
- [ ] DT-FLUXO-03 — corrigir ordem de dedup em
      `registro_analise_service.py`
- [ ] DT-MVA-01 — decidir escopo realista para o lançamento (nacional
      vs. só Pará com aviso explícito)

**Critério de saída:** suite XML 100% verde; três dívidas de fluxo
decididas; MVA com escopo declarado.

---

## BLOCO 9 — IDENTIDADE, PERMISSÕES E MULTI-TENANT

**Objectivo:** garantir que cada utilizador, empresa e contador vê
apenas o que tem autorização para ver. Sem isto, o motor pode estar
certo, mas a abertura fica frágil — qualquer correcção a posteriori
é mais cara do que desenhar isto agora.

**Por que vem já a seguir ao núcleo XML:** permissões mal desenhadas
contaminam todos os blocos seguintes (dashboard, jornada, segurança).
Resolver depois é retrabalho; resolver agora é fundação.

### 9.1 — Auditoria
- [ ] Auditar autenticação actual: login, JWT, roles e permissões reais
- [ ] Confirmar separação por `empresa_id` em todos os endpoints sensíveis
- [ ] Confirmar que contador parceiro só vê documentos/empresas
      atribuídos ou disponíveis no pool autorizado

### 9.2 — Matriz e testes de acesso cruzado
- [ ] Definir matriz de permissões: admin, utilizador, empresa,
      contador, suporte
- [ ] Testar acesso cruzado: utilizador A não pode ver empresa B
- [ ] Testar contador sem autorização: não pode ver documento
      pendente fora do seu escopo
- [ ] Confirmar processo de revogação de acesso de contador

**Critério de saída:** nenhum endpoint sensível permite acesso
cruzado entre empresas, utilizadores ou contadores — provado por
teste, não por inspecção visual.

---

## BLOCO 2 — RELATÓRIO E DASHBOARD DEMONSTRÁVEIS

**Objectivo:** transformar o que o motor já calcula em algo que um
cliente, contador ou investidor consiga ver e entender.

### 2.1 — Relatório PDF
- [ ] Auditar `pdf_report_service.py` — confirmar o que já gera
      (Memorial de Cálculo, rodapé com fingerprint)
- [ ] Confirmar se o relatório reflecte os dados reais do InsightEngine
      ou está desactualizado
- [ ] Testar geração ponta a ponta com XML real de exemplo

### 2.2 — Dashboard
- [ ] Auditar `dashboard_router.py` — confirmar que todos os
      endpoints devolvem dados reais, não placeholders
- [ ] Confirmar consumo no frontend (hooks `useEmpresaDashboard.js`,
      `useCpfDashboard.js`, `useMeiDashboard.js`)
- [ ] Validar visualmente em ambiente local com dados de teste

**Critério de saída:** demonstração completa e reproduzível — upload
de XML real → relatório PDF correcto → dashboard com os mesmos números.

---

## BLOCO 10 — JORNADA REAL DO UTILIZADOR E DO CONTADOR

**Objectivo:** garantir que a plataforma é usável por alguém que não
conhece o sistema por dentro. Abertura real exige fluxo simples, não
apenas endpoint funcional.

### 10.1 — Jornada mínima do utilizador
- [ ] Criar conta
- [ ] Aceitar termos/LGPD
- [ ] Cadastrar empresa
- [ ] Enviar XML
- [ ] Ver estado da análise
- [ ] Ver resultado em linguagem simples (não JSON bruto)
- [ ] Baixar relatório PDF
- [ ] Entender o que fazer a seguir
- [ ] Saber quando precisa de contador

### 10.2 — Jornada mínima do contador parceiro
- [ ] Entrar como contador
- [ ] Ver documentos ou empresas atribuídas
- [ ] Assumir análise pendente
- [ ] Ver evidências
- [ ] Emitir parecer/homologação
- [ ] Registar decisão auditável
- [ ] Devolver ao utilizador resultado compreensível

**Critério de saída:** um utilizador novo consegue, sem Miguel
explicar por fora, carregar XML, receber análise e entender o
próximo passo.

---

## BLOCO 11 — SEGURANÇA, LGPD E DADOS SENSÍVEIS

**Objectivo:** impedir que o produto abra com risco jurídico ou
vazamento de dados fiscais. A plataforma lida com XML, CNPJ, CPF,
notas fiscais, valores e documentos — exige regra explícita, não
suposição de que "está protegido por defeito".

- [ ] Confirmar política de armazenamento de XMLs e documentos
- [ ] Confirmar se dados sensíveis são guardados em texto puro ou
      precisam de máscara/criptografia
- [ ] Confirmar logs: nenhum deve expor XML completo, CPF, CNPJ
      sensível, chave de acesso ou dados pessoais desnecessários
- [ ] Criar regra de anonimização para amostras reais usadas em testes
      (aplica-se directamente às amostras DANFE pedidas ao contador
      no Bloco 5)
- [ ] Definir tempo de retenção de documentos
- [ ] Confirmar consentimento LGPD antes do upload
- [ ] Confirmar que o utilizador pode solicitar exclusão/exportação
      dos seus dados
- [ ] Separar dados reais de produção de fixtures de desenvolvimento

**Critério de saída:** nenhum dado fiscal/pessoal real entra no
repositório, logs ou testes sem anonimização e autorização.

---

## BLOCO 3 — MOTOR DE ANOMALIAS / DETECÇÃO AVANÇADA

**Objectivo:** consolidar e expandir o que o `InsightEngine` já faz,
antes de pensar em IA externa.

- [ ] Resolver DT-AUD-01 — alinhar campos entre `AuditorFiscalAgent`
      e `InsightEngine`
- [ ] Decidir e documentar: activar `AgentScheduler` ou manter
      desligado para o lançamento inicial (DT-AGENTE-01 precisa de
      decisão explícita)
- [ ] Avaliar DT-NORM-01 (`NormativeAgent` vazio) — decisão explícita
- [ ] Expandir cobertura de MVA além do Pará, se 1.2 decidiu que é
      necessário para o lançamento

**Critério de saída:** cada dívida técnica de agente tem decisão
registada — nenhuma fica em limbo silencioso.

---

## BLOCO 4 — AGENTES SEM IA EXTERNA OBRIGATÓRIA

**Objectivo:** preparar a estrutura de agentes para uso futuro de
LLM como apoio — sem que isso seja pré-requisito para funcionar hoje.

- [ ] Confirmar que os 11 agentes do `AgentRegistry` continuam
      funcionalmente correctos nos seus alertas determinísticos,
      independentemente de qualquer LLM
- [ ] Não implementar `LLMRouter`/adapters nesta fase — directriz
      estratégica registada (Bloco 6.x), não trabalho actual

**Critério de saída:** agentes existentes funcionam 100% sem
dependência de qualquer API externa de IA.

---

## BLOCO 12 — PRODUÇÃO, MONITORIZAÇÃO E ROLLBACK

**Objectivo:** garantir que a plataforma consegue operar em produção
sem Miguel depender de prints ou adivinhação quando algo falha.

- [ ] Confirmar ambiente Railway actual
- [ ] Confirmar variáveis de ambiente obrigatórias
- [ ] Confirmar migrations aplicadas em produção (alinhar com `0010`
      já commitada — confirmar que correu no deploy)
- [ ] Confirmar `/health`
- [ ] Confirmar logs de erro legíveis
- [ ] Definir processo de rollback
- [ ] Definir backup do banco
- [ ] Confirmar que falha de Redis/RQ não quebra análise básica
      (relaciona-se com DT-REDIS-01, Bloco 6)
- [ ] Confirmar limite de upload e comportamento em ficheiros inválidos
- [ ] Criar checklist de deploy

**Critério de saída:** se uma análise falhar em produção, é possível
saber porquê, corrigir ou reverter sem improviso.

---

## BLOCO 6 — INFRAESTRUTURA E ESCALA

**Objectivo:** itens que não bloqueiam o lançamento inicial mas
precisam de decisão antes de escala real de utilizadores.

- [ ] DT-REDIS-01 — Redis/RQ inactivo, fallback síncrono. Decidir:
      activar antes do lançamento, ou aceitar fallback síncrono para
      volume inicial baixo (com critério de quando reavaliar)
- [ ] DT-DB-01 — import circular em `database.py` (bloqueia
      `alembic current` localmente; não afecta produção)
- [ ] DT-DB-02 — `test.db` local desactualizado face ao repo
- [ ] **Bloco 6.x — LLMRouter (DeepSeek/Kimi):** registado como
      directriz estratégica futura pelo GPT em 2026-06-20. **Não
      implementar agora.** Regra fixada: IA externa propõe, nunca
      decide; motor fiscal valida; ledger regista; humano ratifica
      quando necessário. Arquitectura prevista, sem implementação:
      `AgentScheduler → LLMRouter → ProviderAdapter (DeepSeek/Kimi/
      OpenAI/Local)`. Nenhum provider externo pode alterar banco
      directamente, criar decisão fiscal canónica, promover documento,
      ou substituir regra normativa.

**Critério de saída:** decisão explícita e registada para cada item
— "resolvido", "aceite com data de reavaliação", ou "adiado para
pós-lançamento".

---

## BLOCO 13 — OPERAÇÃO, SUPORTE E PILOTO CONTROLADO

**Objectivo:** abrir primeiro de forma controlada — piloto com
poucos utilizadores reais antes de qualquer lançamento amplo.

- [ ] Definir 1 contador parceiro inicial
- [ ] Definir 1 a 3 empresas piloto
- [ ] Definir que tipo de XML será aceite no piloto
- [ ] Definir canal de suporte: WhatsApp, e-mail ou painel
- [ ] Criar mensagem padrão para erro de XML inválido
- [ ] Criar mensagem padrão para "análise inconclusiva"
- [ ] Criar mensagem padrão para "precisa de contador"
- [ ] Criar checklist de recolha de feedback
- [ ] Criar métrica mínima: tempo de análise, erro, clareza do
      relatório, valor percebido

**Critério de saída:** piloto real concluído com pelo menos uma
empresa e um contador, com relatório gerado, feedback registado e
correcções priorizadas.

---

## BLOCO 7 — AUTORIDADE E CONTADOR PARCEIRO (FORMAL)

**Objectivo:** fechar o GAP já declarado na Constituição §I-4 antes
de abrir a plataforma a actos com exigência legal de assinatura CRC.

- [ ] Modelar "lei exige CRC" como entidade do sistema (hoje o único
      gatilho é score de confiança documental, não tipo de acto fiscal)
- [ ] Resolver a "Lacuna V1" do pool de contadores: criar endpoint
      que liste documentos em `fila_homologacao` ainda não assumidos
      por ninguém (sem isso, o pool aberto não escala — já
      identificado em PM-07 e MAPA_REALIDADE)
- [ ] Confirmar processo real de onboarding de contador parceiro
      (`PerfilContador.status == "aprovado"` — quem aprova hoje?)

**Critério de saída:** um contador parceiro consegue, sem
intervenção manual de Miguel, descobrir, assumir e decidir sobre um
documento pendente.

---

## BLOCO 5 — PONTE DOCUMENTAL-FISCAL (BLOQUEADO ATÉ AMOSTRA REAL)

**Objectivo:** retomar DT-DOC-02a, DT-DOC-02c e o service de
promotion — **só quando a amostra real chegar do contador.** Corre
em paralelo aos restantes blocos, sem os bloquear.

**Pré-requisito de entrada, sem excepção:**
- [ ] 1 PDF DANFE digital real
- [ ] 1 XML correspondente (ground truth fiscal)
- [ ] 1 foto de DANFE impresso (para robustez de OCR)
- [ ] 1 chave de acesso de NF-e real
- [ ] Amostras anonimizadas conforme regra do Bloco 11 antes de
      entrarem em qualquer teste ou fixture do repositório

**Quando desbloqueado, ordem de trabalho:**
- [ ] DT-DOC-02a — regex `valor_icms` com base em texto real
- [ ] DT-DOC-02c — regex `numero_nota`, `tipo`, `uf_emit`, `uf_dest`
- [ ] A.4 / DT-DOC-04 — destino de CNPJ/CPF em `DocumentoFiscal`
- [ ] Service de promotion (CT-DOC-001 secções 1-6 completas)
- [ ] Testes de promotion (12 casos mínimos já definidos)

**Critério de saída:** promotion canónica funcional e testada,
conforme critérios já escritos em ADR-002 e CT-DOC-001.

---

## BLOCO 8 — VALIDAÇÃO LEGAL E COMERCIAL

**Objectivo:** itens fora de código, mas bloqueantes para abertura
real a utilizadores.

- [ ] Mercado Pago — implementado em código, nunca validado em
      produção real; testar transacção real de valor mínimo
- [ ] Termos de uso / política de privacidade — confirmar cobertura
      face ao estado actual do produto, incluindo o que o Bloco 11
      revelar
- [ ] Confirmar se a Constituição Tributária L2 precisa de versão
      pública/simplificada para utilizadores

**Critério de saída:** pagamento testado ponta a ponta; termos
legais revistos contra o estado actual do produto.

---

## SEQUÊNCIA RECOMENDADA (visão de topo, reforçada)

```
1.  Bloco 1  — Núcleo XML                      ← começar aqui, hoje
2.  Bloco 9  — Identidade/permissões            ← logo a seguir, fundação
3.  Bloco 2  — Relatório/Dashboard              ← depende de 1 estável
4.  Bloco 10 — Jornada utilizador/contador      ← depende de 2
5.  Bloco 11 — Segurança/LGPD                   ← antes de qualquer dado real
6.  Bloco 3  — Motor de anomalias               ← pode correr com 4/5
7.  Bloco 4  — Agentes sem IA externa           ← pode correr com 3
8.  Bloco 12 — Produção/monitorização/rollback  ← antes de piloto
9.  Bloco 6  — Infra/escala                     ← decisões, não bloqueante
10. Bloco 13 — Piloto controlado                ← antes de abertura ampla
11. Bloco 7  — Contador parceiro (formal)       ← antes de actos com CRC obrigatório
12. Bloco 8  — Legal/comercial                  ← antes de utilizadores pagantes

Bloco 5 — Ponte Documental ← paralelo a tudo, só quando amostra real chegar
```

---

## REGISTO DE DECISÕES TOMADAS NESTA SESSÃO (2026-06-20)

- DANFE/OCR/promotion documental: oficialmente em espera, sem prazo,
  condicionado a amostra real do contador
- Núcleo XML fiscal: prioridade imediata, caminho livre, sem bloqueio
- LLMRouter (DeepSeek/Kimi): directriz estratégica registada, não
  implementação actual — IA externa nunca decide, apenas propõe;
  motor fiscal valida; ledger regista; humano ratifica
- Reforço do GPT: roadmap técnico não é roadmap de abertura. Cinco
  blocos novos (9, 10, 11, 12, 13) adicionados e intercalados na
  sequência, não apenas anexados ao fim

---

*Este roadmap não substitui ADR-001, ADR-002 ou CT-DOC-001 — organiza
a sequência de execução do que já está institucionalmente decidido,
mais o que falta decidir em cada bloco.*

*O conhecimento não está na conversa. Está no repositório.*
