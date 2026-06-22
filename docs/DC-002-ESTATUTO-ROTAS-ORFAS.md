# DC-002 — Estatuto de Rotas Órfãs do Eixo XML

**Data:** 2026-06-20

**Natureza:** Decisão formal de estatuto. Fecha DT-FLUXO-01 e
  DT-FLUXO-02 do Bloco 1.2 (ROADMAP_ABERTURA_UTILIZADORES.md).

**Base:** evidência de uso real (frontend, scripts, testes) recolhida
  nesta sessão, cruzada com comportamento de persistência confirmado
  por leitura directa de código.

**Pré-condição cumprida:** DT-FLUXO-03 corrigido e **confirmado em
  produção** (commit `4a5ddab`, deploy `19709822`) antes desta
  decisão — eixo canónico protegido antes de decidir sobre caminhos
  laterais.

---

## DT-FLUXO-03 — FECHADO, COM PROVA EM PRODUÇÃO

A sequência completa, registada por transparência institucional:

```
8477097  Caracterização (xfail strict) — bug documentado, não corrigido
bc6ce6a  Primeira correção (UNIQUE constraint, sem dedup)
         → deploy FAILED — revelou 2 grupos de duplicados REAIS em
           produção (22 registos), confirmando que o TOCTOU já tinha
           causado dano concreto antes de ser caracterizado
4a5ddab  Correção completa (dedup + verificação + constraint)
         → deploy SUCCESS, confirmado via SSH directo ao container:
           alembic current = 0011_unique_relatorio_xml_chave (head)
           /health = {"status": "ok"}
```

Esta sequência fica registada porque é evidência de que a disciplina
de caracterização-antes-de-correção, aplicada nesta sessão, não foi
apenas processo — preveniu um deploy que teria silenciosamente
falhado a proteger produção, e revelou uma dívida real que já
afectava utilizadores antes de qualquer um de nós saber dela.

---

## EVIDÊNCIA DE USO REAL (confirmada nesta sessão)

| Rota | Frontend | Scripts | Testes pytest |
|------|----------|---------|----------------|
| `POST /fiscal/analisar-xml` | ✅ único caminho usado (`App.jsx`) | ✅ `testes_operacionais.py` | — |
| `POST /upload-xml` | ❌ zero ocorrências | ✅ smoke/dedup manual | ❌ |
| `POST /lote/analisar-lote` | ❌ zero ocorrências | ❌ zero ocorrências | ❌ (só contrato documental) |

---

## PRINCÍPIO DE CLASSIFICAÇÃO

> Rota órfã que não persiste é simulação.
> Rota órfã que persiste é risco.

As duas rotas órfãs não são equivalentes. `/lote/analisar-lote` não
persiste nada — não pode criar estado fiscal incompleto, porque não
cria estado nenhum. `/upload-xml` persiste `DocumentoFiscal` sem
nunca gerar `RelatorioAnalise`, sem chamar `InsightEngine`, sem
calcular score, sem verificar limite de análises — cria um documento
que existe no sistema mas nunca se torna uma análise auditável.

---

## DECISÃO 1 — `/fiscal/analisar-xml`

**Estatuto: único caminho canónico para abertura ao utilizador.**

Nenhuma alteração necessária. Já é o caminho usado pelo frontend,
já passa pelo pipeline completo (`executar_e_registrar_analise_xml`
→ `InsightEngine` → score → `RelatorioAnalise`), já está protegido
contra TOCTOU desde `bc6ce6a`.

---

## DECISÃO 2 — `/upload-xml`

**Estatuto: BLOQUEANTE PARA ABERTURA PÚBLICA enquanto permanecer
exposto sem correcção.**

Não é suficiente documentar como legado. A rota cria verdade fiscal
parcial — um `DocumentoFiscal` persistido sem o ciclo de análise que
a Constituição (Art. V — Auditabilidade) exige para qualquer acto
que afecte o contribuinte.

**Acções aprovadas, nesta ordem:**

1. **Imediato (esta decisão):** `/upload-xml` é formalmente declarada
   **não-canónica** e **não autorizada para uso por utilizador final**.
   Não entra em nenhuma jornada de produto (Bloco 10 do roadmap).
2. **Imediato (esta decisão):** a rota permanece tecnicamente activa
   apenas para compatibilidade dos scripts de smoke/dedup já
   existentes (`testar_api_swagger.py`, `_test_duplicata_upload.py`).
   Não é removida nesta decisão.
3. **Antes da abertura ao utilizador (Bloco 13, piloto controlado):**
   uma de duas correcções obrigatórias, a decidir em ADR próprio
   quando o trabalho for retomado:
   - **(a)** Transformar `/upload-xml` em wrapper de
     `executar_e_registrar_analise_xml`, eliminando a divergência; ou
   - **(b)** Desactivar o endpoint publicamente (remover de
     `main.py` ou protegê-lo atrás de flag de administrador/ambiente
     de desenvolvimento), mantendo só uso interno controlado
4. **Até a correcção (a) ou (b) ser implementada:** `/upload-xml`
   **bloqueia** a conclusão do Bloco 13 (Piloto Controlado) do
   roadmap. Não é possível declarar "abertura pública pronta" com
   esta rota exposta sem correcção.

---

## DECISÃO 3 — `/lote/analisar-lote`

**Estatuto: ferramenta interna / simulação efémera. Não bloqueante.**

A rota não persiste, não cria `RelatorioAnalise`, não compete com
dados reais. Resultado vive apenas em memória (`jobs` dict, TTL
implícito por processo).

**Acções aprovadas:**

1. Declarada formalmente como **não-auditável** e **não substituta
   de análise fiscal definitiva**.
2. Pode permanecer como está, sem alteração de código.
3. Se um dia for exposta a utilizador final, deve apresentar aviso
   explícito: *"resultado não guardado, não auditável, não substitui
   análise fiscal canónica"* (já antecipado no roadmap, Bloco 10).
4. Não bloqueia nenhum bloco do roadmap.

---

## ACTUALIZAÇÃO DO ROADMAP

`ROADMAP_ABERTURA_UTILIZADORES.md`, Bloco 1.2, passa a reflectir:

```
DT-FLUXO-01 (/upload-xml)        ✔ decidido — BLOQUEANTE para Bloco 13
                                     até (a) wrapper canónico ou
                                     (b) desactivação implementada
DT-FLUXO-02 (/lote/analisar-lote) ✔ decidido — não-bloqueante,
                                     ferramenta interna declarada
DT-FLUXO-03 (dedup TOCTOU)        ✔ corrigido e confirmado em
                                     produção (4a5ddab, deploy 19709822)
```

Bloco 1 do roadmap fica concluído com esta decisão — as três dívidas
de fluxo nomeadas na auditoria original (Mapa de Realidade) têm,
agora, decisão registada e rastreável, nenhuma em limbo silencioso.

---

*Esta decisão não implementa código para `/upload-xml` — declara
estatuto e cria bloqueio explícito para abertura, a resolver quando
o trabalho do Bloco 13 for retomado. `/lote/analisar-lote` não exige
acção adicional.*

*O conhecimento não está na conversa. Está no repositório.*
