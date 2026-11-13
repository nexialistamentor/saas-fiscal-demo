# Coordenacao B05 / Fase 4 -- 2026-11-13

Divisao de trabalho entre duas sessoes Claude, a partir de agora:

- **Esta sessao (coordenadora):** acompanha e ratifica a Fase 4 (GPT,
  branch `cobertura-nacional-jurisdicoes-fase4-cest-remetente`), mantem
  visao geral de B05 e desta coordenacao.
- **Outra sessao Claude (execucao):** recria a correcao da Issue #31 no
  branch certo, e continua o fecho de B05 nos dados reais de producao.

## Tarefa imediata: recriar a Issue #31 no branch certo

**Contexto do incidente** (ver `ALERTA_CATRACA_ANTIDUPLICACAO.md` na raiz
para o historico completo): o branch
`fix/issue-31-guarda-fonte-legal-prever-impacto-st` foi criado a partir
de `main`, numa altura em que `main` nao tinha a catraca anti-duplicacao
(`tools/check_duplicacao.py`/`docs/REGISTRO_CANONICO.json`). O commit
`190efdeb2465db3208e720dcb38352d8fc39681a` (correcao real da Issue #31,
ja testada: `prever_impacto_st` passa a usar `resolver_aliquota_e_mva`
em vez de `buscar_mva` direto) foi feito **sem nenhuma verificacao de
duplicacao**, porque o hook falhava aberto nessa altura.

`main` ja foi corrigido (commits `cd579473`..`1067b5f1`): a catraca
agora existe em `main`, e o hook agora falha FECHADO se os ficheiros
faltarem.

## Passos exatos para recriar a correcao

1. Criar o branch novo a partir de `main` ja atualizado (que agora tem
   a catraca):
   ```powershell
   git fetch origin main
   git checkout -b fix/issue-31-v2-guarda-fonte-legal origin/main
   Test-Path tools\check_duplicacao.py
   Test-Path docs\REGISTRO_CANONICO.json
   ```
   Ambos devem devolver `True`. Se algum devolver `False`, PARAR --
   nao prosseguir, reportar e investigar antes de continuar.

2. Trazer a correcao ja testada via cherry-pick (nao recriar o diff a
   mao -- o commit original ja foi validado antes, so a base e que
   estava errada):
   ```powershell
   git cherry-pick 190efdeb2465db3208e720dcb38352d8fc39681a
   ```
   Se houver conflito (improvavel, mas possivel dado o tempo decorrido
   desde a criacao do branch antigo), resolver olhando o ficheiro real
   atual de `app/services/motor_predicao_tributaria.py` antes de aceitar
   qualquer lado do conflito -- nunca aceitar automaticamente.

3. Rodar a suite relevante (incluindo os dois testes que falharam no
   branch antigo, para confirmar se eram causados pela correcao ou pela
   base desatualizada):
   ```powershell
   python -m pytest tests\test_pipeline_xml_canonico.py tests\test_mei_normative_census.py -v
   ```
   Investigar qualquer falha antes de prosseguir -- nao assumir que sao
   "falhas de ambiente conhecidas" sem confirmar.

4. Suite ampla relacionada com `motor_predicao_tributaria`/`InsightEngine`
   e catraca, como de costume, antes do commit final (o cherry-pick ja
   cria o commit, mas confirmar que a catraca rodou de verdade desta
   vez -- deve aparecer "OK: nenhuma duplicacao..." no output do
   commit, nao mais o aviso antigo).

5. Push do branch novo:
   ```powershell
   git push -u origin fix/issue-31-v2-guarda-fonte-legal
   ```

6. **Nao apagar nem tocar no branch antigo**
   (`fix/issue-31-guarda-fonte-legal-prever-impacto-st`) sem
   confirmacao -- so deixa de ser o branch ativo, fica como historico
   do incidente.

## Depois disso -- continuar B05

Ver `docs/HANDOFF_B05_PROXIMA_SESSAO_20261113.md` (ja publicado) para o
estado completo de B05: acesso Postgres, achados reais de producao
(0/80 empresas com UF, 5 NCMs/2 UFs reais confirmados), e os proximos
passos sugeridos por prioridade. Prioridade 1 dessa lista (Issue #31) e
exatamente esta tarefa -- depois de fechada, seguir para a prioridade 2
(trocar credencial exposta) e so depois tentar fechar B05 com o caso
real `empresa_id=4`/NCM 22021000/PA.

Esta sessao coordenadora acompanha a Fase 4 do GPT em paralelo -- nao
mexer no branch `cobertura-nacional-jurisdicoes-fase4-cest-remetente`
sem avisar, para nao haver mistura de trabalho entre as duas frentes.
