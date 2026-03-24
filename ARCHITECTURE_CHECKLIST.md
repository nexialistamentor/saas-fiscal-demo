# Checklist de arquitetura

## CHECKLIST MESTRE — PRÉ-ALTERAÇÃO

Use este bloco sempre antes de pedir mudança ao Cursor, Gemini, Claude ou qualquer outro executor:

### CHECKLIST DE VALIDAÇÃO ARQUITETURAL

Antes de alterar qualquer código, confirme obrigatoriamente:

1. O que vou mexer já existe no projeto?
2. Estou reutilizando a função/serviço/rota existente?
3. Estou criando fluxo paralelo sem perceber?
4. Isso toca:
   - motor_fiscal
   - analysis_orchestrator
   - executar_e_registrar_analise_xml
   - processar_e_persistir_xml
   - InsightEngine
   - tabela_mva / buscar_mva / carregar_mva
5. A mudança mantém o pipeline oficial?
6. O resultado final continuará:
   - analisando
   - persistindo
   - enriquecendo
   - alimentando inteligência
7. Isso aumenta consumo de tokens?
8. Isso reprocessa algo que já está persistido?
9. Isso cria mais de uma fonte da verdade?
10. Isso escala para lote grande?

Se alguma resposta for incerta, parar e auditar antes de alterar.

---

## CHECKLIST MESTRE — PRÉ-COMMIT

### CHECKLIST DE SEGURANÇA PRÉ-COMMIT

Antes de commitar, confirmar:

1. Não criei duplicação de lógica
2. Não abri novo fluxo paralelo
3. Não quebrei o pipeline oficial
4. Não movi regra tributária para lugar errado
5. Não usei IA onde lógica determinística bastava
6. Não deixei fallback virar fonte principal
7. O código novo respeita .cursorrules
8. O impacto em produção é compreendido
9. O deploy dessa mudança pode ser validado isoladamente
10. Há clareza de rollback

---

## CHECKLIST MESTRE — PRÉ-PROMPT

Sempre que você for abrir um novo chat técnico, cole isso antes do pedido:

Antes de responder, respeite obrigatoriamente:

- não criar duplicação
- não criar fluxo paralelo
- não alterar o motor fiscal sem necessidade crítica
- não usar agents como processamento primário
- não usar LLM se dados persistidos já resolvem
- considerar tabela_mva como fonte normativa principal
- manter unitário e lote convergindo para o mesmo destino analítico
- responder com diagnóstico, risco, decisão, impacto e próximo passo único

---

## Como usar na prática

Você não precisa mandar tudo toda vez.

Use assim:

- **mudança pequena** → checklist pré-alteração
- **antes de subir código** → checklist pré-commit
- **novo chat confuso** → checklist pré-prompt

---

## Regras operacionais (persistência e análise)

uf_cobertura persistida em inteligencia_snapshots é a métrica oficial para decidir a futura migração de _analisar_margem_real de NCM para (NCM, UF).

### `_analisar_margem_real` (InsightEngine)

**Critério oficial para migrar de agregação por NCM para agregação por (NCM, UF)**

A migração só poderá ocorrer quando as **3 condições abaixo forem verdadeiras ao mesmo tempo**:

1. **Cobertura mínima de UF**  
   Pelo menos **85%** dos `DocumentoFiscal` do recorte analisado devem ter `uf_emit` **e/ou** `uf_dest` preenchidos.

2. **Massa mínima de dados**  
   Deve existir no mínimo **uma** das seguintes alternativas:
   - **100** documentos fiscais no recorte da empresa, **ou**
   - **30** dias de ingestão já com UF persistida.

3. **Simetria mínima entre entrada e saída**  
   Para a análise de margem real por (NCM, UF) fazer sentido, o conjunto precisa ter UF disponível em **documentos de entrada** e em **documentos de saída**. Se só um lado tiver UF consistente, a análise continua **por NCM**.

**Regra operacional**

- Enquanto **qualquer uma** dessas condições falhar: `_analisar_margem_real` permanece agregado **apenas por NCM**.
- Quando **todas** forem atendidas: `_analisar_margem_real` **pode** migrar para chave **(NCM, UF)**.

**Motivo da escolha**

Esse corte evita: migrar cedo demais com base incompleta; quebrar comparabilidade com histórico antigo; gerar insight “preciso no código, falso no dado”.

**Implementação**

Hoje vive em `app/services/insights_engine.py`; alterações futuras devem respeitar estes limites antes de mudar a chave analítica.
