# HANDOFF — SOLVERIS Enterprise, B04 em andamento

Escrito pela sessão Claude de 2026-11-11, para a próxima sessão (Claude ou
GPT) continuar exatamente de onde parou. Leia isto por inteiro antes de
tocar em qualquer ficheiro.

## Onde estamos agora

- **Repo:** `C:\dev\saas-fiscal-demo-a1` (worktree de `C:\dev\saas-fiscal-demo`;
  git-common-dir real é `C:\dev\saas-fiscal-demo\.git` — hooks vivem lá, não
  em `.git\hooks` deste worktree, que não existe como pasta própria).
- **Branch atual:** `b04/integracao-g13-icms-st-20261111`, criado a partir
  de `b03/inventario-antidup-20261110` (que está fechado e publicado em
  `origin`, até ao commit `5cd49824`).
- **Último passo confirmado:** `app/services/enterprise_b04_icms_st_integral_bridge.py`
  + `tests/test_enterprise_b04_icms_st_integral_bridge.py` escritos, sintaxe
  OK, 3 testes `pytest` passam, `check_duplicacao.py` OK, `git add` feito.
  **O `git commit` e `git push` deste branch foram pedidos na mesma mensagem
  que gerou este handoff — confirme com `git log --oneline -3` e
  `git status` se já aconteceram antes de repetir.**

## B00-B03: fechados, não reabrir

- B00, B01, B02: fechados antes desta sessão.
- **B03** (comparação monetária ICMS-ST): fechado nesta sessão, depois
  **reclassificado** — ver próxima secção. Ler `docs/B03_FECHAMENTO.md`
  inteiro (inclui o adendo) antes de mexer em qualquer coisa relacionada a
  ICMS-ST.

## A lição mais importante desta sessão (não repetir o erro)

B03 construiu `enterprise_b03_item_reconciliation.py` do zero para a
capacidade ICMS-ST **sem saber que `enterprise_g12_st_item_reconciliation.py`
(G12) + `enterprise_g13_subject_st_bridge.py` (G13) já faziam a mesma coisa,
com mais rigor, e já estavam ligados em produção** via
`registro_analise_service.py`. Isso só foi descoberto na Fase de B04, ao ler
`enterprise_integral_projection.py::_CAPACIDADES` (o catálogo de 52
capacidades) e seguir a cadeia G12→G13.

**Regra absoluta a partir de agora:** antes de escrever qualquer função nova
que calcule, valide ou confira algo fiscal, ler primeiro:
1. `docs/REGISTRO_CANONICO.json` (registo de módulos já confirmados).
2. `app/services/enterprise_integral_projection.py::_CAPACIDADES` (as 52
   capacidades, cada uma com `origem` e `produtor_ou_chave` declarados).
3. Fazer `git grep` pelo nome da capacidade/conceito antes de assumir que
   não existe. Nomes de gate (`G12`, `G13`, `I0`-`I12`) não seguem a
   numeração dos blocos (`B00`-`B11`) — são sistemas de numeração
   diferentes e PARALELOS. Não confundir um com o outro.

Se este passo for pulado outra vez, o risco é exatamente o que aconteceu
com B03: trabalho testado e funcional, mas descartável, porque duplicava
algo já maduro.

## Estado atual da cadeia I (contexto necessário)

- `I0` (`enterprise_integral_projection.py::projetar_diagnostico_integral_i0`):
  base determinística, sem efeitos colaterais, em cima de
  `compor_resultado_empresarial`/`InsightEngine.executar_engines`. Devolve
  `cobertura`: lista de dicts (`id`, `grupo`, `origem`, `produtor_ou_chave`,
  `estado`, `causa`, `autoridade_fiscal`, `resultado_bruto_nao_validado`).
  Estados possíveis: `informativo_sem_prova`, `nao_apurado`, `falha_motor`,
  `nao_integrado_ao_snapshot` (quando `origem == "pendente"`).
- `I1` (`enterprise_pis_cofins_authority_i1.py`): wrapper de I0, quarentena
  PIS/Cofins. **Capacidades PIS/COFINS têm prazo de validade: extintas em
  01/01/2027** (ver `docs/REFORMA_TRIBUTARIA_2027_ALINHAMENTO.md`). Não
  investir pesado aqui sem avaliar o retorno.
- `I2` (`enterprise_i2_documentary_bridge.py`): wrapper de I1, liga a um
  XML específico via `relatorio_id`/`DocumentoFiscal` já persistidos
  (exige posse, hash, binding — nunca aceita dados soltos).
- `G12` (`enterprise_g12_st_item_reconciliation.py::confrontar_st_por_item_g12`):
  motor real de confronto ICMS-ST por item, método `iva_st` apenas (não
  PMPF). Já maduro: valida frete/seguro/desconto/redução zerados, coerência
  aritmética do ICMS próprio, cruza `buscar_mva` com `resolver_base_calculo_st`.
- `G13` (`enterprise_g13_subject_st_bridge.py::projetar_confronto_st_sujeito_g13`):
  chama I2 (custódia) + G12 (cálculo) sobre os *mesmos* bytes/db, confirma
  consistência entre os dois, nunca promove a autoridade.
- **Novo nesta sessão:** `enterprise_b04_icms_st_integral_bridge.py::
  projetar_diagnostico_integral_icms_st` — chama I2 + G13, funde o
  resultado de G13 nas entradas `icms_st`/`mva`/`consistencia_fiscal` da
  `cobertura` (de `nao_integrado_ao_snapshot` para `informativo_sem_prova`,
  nunca `autoridade_fiscal=True`). `pmpf`/`restituicao_st`/`creditos_st`/
  `distorcoes_st_mva` continuam `pendente` — G12/G13 não cobrem isso, não
  fingir que cobrem.

## Reclassificação de B03 (não confundir com o módulo novo de B04)

`enterprise_b03_item_reconciliation.py` (de B03) **não é usado em
produção**. É scaffold de aprendizagem — os 7 testes continuam válidos
como especificação do contrato `resolver_aliquota_e_mva→MotorFiscal→
TaxConsistencyEngine`, mas nenhuma função dele é chamada por nada real.
Não o apague (seria destruir histórico/contexto), mas também não construa
em cima dele pensando que é produção.

## O que falta fazer para fechar B04 de facto

1. Confirmar commit+push do branch atual (ver "Último passo confirmado").
2. Atualizar `_CAPACIDADES` em `enterprise_integral_projection.py`: mudar
   `origem` de `"pendente"` para `"snapshot"` (ou `"engine"`, a decidir
   olhando o padrão exato usado por outras entradas já `"snapshot"`) nas
   linhas de `icms_st`, `mva`, `consistencia_fiscal`, e `produtor_ou_chave`
   de `"st_service"`/`"fiscal_utils"`/`"tax_consistency_engine"` para
   `"enterprise_b04_icms_st_integral_bridge"` — **só depois de confirmar
   que isso não quebra nenhum teste existente de I0/I1/I2** (rodar a
   suite inteira de testes `enterprise_integral*`/`enterprise_i*`/
   `enterprise_g1*` antes e depois da mudança).
3. Verificar se existe algum consumidor real (router/endpoint) que deve
   chamar `projetar_diagnostico_integral_icms_st` — hoje é só uma função
   testada, sem ninguém a invocá-la em produção. Procurar por onde
   `registro_analise_service.py` ou outro ponto de entrada deveria ligar
   isto (provavelmente onde já chama G13 diretamente hoje).
4. Investigar as outras 7+ capacidades do grupo `inteligencia` marcadas
   `"pendente"` (`score_tributario`, `ranking_restituicao`, `ranking_estrategico`,
   `projecao_recuperacao`, `impacto_financeiro`, `anomalias`, `eficiencia`,
   `complexidade`, `maturidade`, `benchmark`...) — mesma disciplina: ler
   antes de construir, `git grep` pelo nome do serviço declarado em
   `produtor_ou_chave` antes de presumir que não existe.
5. Só depois disso, mover para B05 (validação com casos reais) — e mesmo
   aí, `B03_FECHAMENTO.md` já regista que só há 1 regra real na BD (PA/
   NCM=22021000) — B05 vai precisar de mais dados reais ou de construir
   casos sintéticos claramente rotulados como tal.

## O que pode e o que NÃO pode fazer

**Pode:**
- Ler qualquer ficheiro do repo livremente (`view`, `mostrar_corpo_funcao.py`,
  `confirmar_assinaturas_b03.py`).
- Escrever código novo **depois** de confirmar por leitura real que não
  existe já (Fase 0 obrigatória, sempre).
- Criar um branch novo por bloco (`b04/...`, `b05/...`), nunca misturar
  blocos no mesmo branch.
- Rodar testes, `check_duplicacao.py`, scripts de diagnóstico.
- Corrigir bugs reais encontrados por teste contra dado real (como os 2
  bugs corrigidos em B03), documentando a correção.

**NÃO pode, em circunstância nenhuma:**
- Commitar ou fazer push sem o pre-commit hook rodar (nunca usar
  `git commit --no-verify` sem motivo documentado e explícito).
- Construir uma capacidade nova sem primeiro confirmar, por `git grep` +
  leitura real do corpo (não só da assinatura), que não existe já um
  produtor para ela no catálogo de 52 capacidades.
- Misturar ficheiros de blocos diferentes no mesmo commit.
- Decidir sozinho(a) para merge em `main`/`candidate` ou para apagar
  qualquer módulo (mesmo os reclassificados como scaffold) sem
  ratificação explícita de Miguel.
- Assumir que um nome de ficheiro corresponde ao seu conteúdo real —
  provou-se várias vezes nesta sessão que não bate (ex: `st_service.py`
  parecia o produtor certo e era legado morto de abril/2026).
- Inventar valores calculados quando falta autoridade normativa — sempre
  fail-closed (`nao_apurado`/`falha_motor`/`CoberturaNaoComprovada`),
  nunca aproximar ou adivinhar.
- Reconstruir a cadeia política→decisão→ativação→assinatura pesada do B02
  para blocos novos sem necessidade legal concreta identificada (decisão
  já registada em `docs/B03_GOVERNANCE_LEVEL.md`).

## Em caso de dúvida, comandos para consultar primeiro

```
# Ver o que já existe mapeado
Get-Content docs\REGISTRO_CANONICO.json
python tools\confirmar_assinaturas_b03.py --repo C:\dev\saas-fiscal-demo-a1 --registro docs\REGISTRO_CANONICO.json

# Ler o corpo real de uma função (nunca confiar só no nome/docstring)
python tools\mostrar_corpo_funcao.py --ficheiro <caminho> --funcao <nome>

# Ver as 52 capacidades e seus estados declarados
python -c "
import re
texto = open(r'C:\dev\saas-fiscal-demo-a1\app\services\enterprise_integral_projection.py', encoding='utf-8-sig').read()
m = re.search(r'_CAPACIDADES\s*=\s*\((.*?)\n\)', texto, re.S)
print(m.group(0))
"

# Confirmar se algo já é chamado por outro módulo antes de presumir que está isolado
git grep -n "<nome_da_funcao>" -- "app/*.py"

# Rodar a catraca anti-duplicacao antes de qualquer commit (o pre-commit hook ja faz isto sozinho, mas para rodar manualmente)
python tools\check_duplicacao.py --repo C:\dev\saas-fiscal-demo-a1 --registro docs\REGISTRO_CANONICO.json

# Rodar os testes do que já existe antes e depois de qualquer mudança
python -m pytest tests\test_enterprise_b03_item_reconciliation.py tests\test_enterprise_b04_icms_st_integral_bridge.py -v

# Confirmar estado git antes de qualquer commit
git rev-parse --show-toplevel
git status
git log --oneline -5
```

## Ficheiros-chave para ler antes de continuar, por ordem

1. Este ficheiro (`HANDOFF_PROXIMA_SESSAO.md`).
2. `docs/B03_GOVERNANCE_LEVEL.md` — nível de governança decidido.
3. `docs/B03_FECHAMENTO.md` — inteiro, incluindo o adendo de reclassificação.
4. `docs/REFORMA_TRIBUTARIA_2027_ALINHAMENTO.md` — prazo de validade de
   capacidades PIS/COFINS.
5. `docs/REGISTRO_CANONICO.json` — módulos já confirmados.
6. `app/services/enterprise_integral_projection.py` — o catálogo inteiro,
   ler `_CAPACIDADES` por completo antes de tocar em qualquer capacidade.
7. `app/services/enterprise_b04_icms_st_integral_bridge.py` — o último
   trabalho real feito, para continuar a partir daqui.
