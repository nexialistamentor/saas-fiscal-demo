# SOLVERIS.MEI-ANISTIA-001 — Gate investigativo normativo e técnico

**Corte:** 2026-11-13. **Modalidade:** investigação/read-only (nenhum endpoint, dado, motor fiscal, contrato SERPRO ou interface alterado nesta etapa).  
**Base técnica fixada:** release Vercel `51a2f652bd9bf405fb977349a7e4a83cf8cfd09f` (`work/mei-meta-measurement-20261018`). Branch distinta da PR #32 de copy/UX.  
**Gate:** `INVESTIGACAO_CONCLUIDA / L3_LIMITE_2027_RED / CONSULTA_DIVIDA_NAO_AUTORIZADA / PIXMEI_SEM_INSCRICAO / RELEASE_HOLD`.

## 1. Fonte e interpretação vinculante (21/10–13/11/2026)

Lei Complementar nº 238, de 21/10/2026, texto legislativo primário:
https://www2.camara.leg.br/legin/fed/leicom/2026/leicomplementar-238-21-outubro-2026-800071-publicacaooriginal-181678-pl.html

PGFN — FAQ atualizado em 06/11/2026:
https://www.gov.br/pgfn/pt-br/servicos/perguntas-frequentes/perguntas-frequentes-perdao-do-mei

Ministério da Fazenda — Portaria Conjunta RFB/PGFN nº 740/2026 e implementação automática:
https://www.gov.br/fazenda/pt-br/assuntos/noticias/2026/novembro/pgfn-esclarece-regras-sobre-perdao-de-dividas-tributarias-para-microempreendedor-individual/

**Precisões obrigatórias ao texto da missão:**
- Nome jurídico preciso: **remissão**, não mero perdão inespecífico nem certificação de regularidade.
- Créditos federais de contribuição previdenciária do MEI **com vencimento até 13/10/2026**, incluindo principal, juros, multas e encargos — e não todo DAS devido até o fim de outubro.
- **ICMS e ISS não abrangidos**, mesmo se constarem no mesmo DAS.
- Incluídos créditos não inscritos e inscritos na Dívida Ativa (PGFN), parcelamentos/negociações nos termos da portaria; discriminar acordos mistos.
- Regra geral: baixa **de ofício a partir de 01/01/2027** sem requerimento do contribuinte; **exceção** para dívidas com ação judicial em andamento, que exigem desistência e renúncia específicas, conforme orientação PGFN.
- Para o contribuinte **ainda formalmente MEI**, manter em dia as contribuições vencidas nos seis meses seguintes; a PGFN informa que essa condição não se aplica a quem já encerrou o CNPJ ou migrou de porte. Não generalizar indiscriminadamente.
- Não há restituição de pagamento anterior; a cobrança continua nos sistemas oficiais até início dos efeitos.
- Para prazo/condições definitivos usar LC 238 e Portaria nº 740, não FAQs de projeto anteriores à sanção (alguns são desatualizados/contraditórios).

## 2. Teto anual: vigência por ano e limitações do motor

| Ano | Limite anual | Base |
| --- | ---: | --- |
| 2026 | R$ 81.000 | LC 123/2006; binding internalizado `data/mei/mei_das_2026_normative_binding_v1.json` |
| 2027 | R$ 110.000 | LC 238/2026 art. 2º; efeitos 01/01/2027 |
| 2028+ | R$ 140.000 | LC 238/2026 arts. 1º e 10, I; efeitos 01/01/2028 |

Art. 3º condiciona a ampliação à consideração da renúncia de receita nas leis orçamentárias de 2027–2029. A comprovação do cumprimento dessa condição deve ser versionada antes de decisão normativa definitiva. Para início em 2027, teto proporcional é **R$ 9.166,67 × meses**; em 2028, **R$ 11.666,67 × meses**, conforme os textos legais; não substituir isso por mera divisão do limite anual em comparações legais.

**Código auditado (somente leitura):**
- `app/services/assistente_service.py::_resposta_limite_mei`: toma limite de `MEI_LIMITE_ANUAL_FATURAMENTO=81_000`; binding estrito de 2026, pedido 2027 retorna `AUTORIDADE_NORMATIVA_MEI_INDISPONIVEL`.
- `app/services/tax_engines/mei_constants.py`: constante 81.000 e limiar de alerta 75.000.
- `app/services/tax_engines/mei_tax_engine.py::_exigir_autoridade_normativa_mei`: bloqueio explícito fora de 2026; **não remover** para atualizar uma pergunta informativa de teto. DAS 2027 exige fonte salarial/tributária própria.
- `app/services/source_authority_guard.py` e `data/fontes_tributarias_manifest.json`: autorização precisa de origem/versionamento/hash, alvo normativo, escopo, vigência e risco. O binding 2026 não pode ser clonado e apresentado como normativo 2027.
- `tests/test_assistente_limite_mensal_mei_temporal_contract.py`: gate existente exige bloqueio em 2027. A transição exige atualização controlada de prova sem permitir bypass.

**Próxima implementação autorizável:** internalizar LC 238 com arquivo de evidência SHA-256, cadastrar fonte normativa restrita no manifest, realizar binding temporal sem sobreposição e resolver **apenas resposta informativa do teto por ano**, preservando o motor DAS de 2027 fail-closed até outra missão. Novos testes RED precedem GREEN.

## 3. Dívida ativa: possível conector, porém sem direito de inferir valor perdoado

SERPRO — documentação `DIVIDAATIVA24`, `idSistema=PGMEI`:
https://apicenter.estaleiro.serpro.gov.br/documentacao/api-integra-contador/pt/solucoes/integra-mei/pgmei/servicos/consultar_divida_ativa/

Entrada: `anoCalendario`. Saída: registros com `periodoApuracao`, `tributo`, `valor`, `enteFederado`, `situacaoDebito`. Serviço **consulta somente dívida ativa**, e não necessariamente todos os débitos em cobrança administrativa na RFB.

Implementação atual:
- `app/services/serpro_pgmei_client.py` permite exclusivamente `GERARDASPDF21` e `GERARDASCODBARRA22`. **DIVIDAATIVA24 não está na allowlist**.
- `app/services/serpro_pgmei_composition.py` monta transporte autenticado por OAuth/mTLS, mas não oferece leitura de débitos.
- `app/routes/imposto_router.py` expõe emissão DAS protegida por autorização econômica `mei.das`, não um endpoint de histórico de débitos.
- Não foi provada habilitação contratual de `DIVIDAATIVA24`, autorização do cliente para consultar dados fiscais desse tipo, resposta real, custo de chamada, retenção, interpretação ou reconciliação com RFB/PGFN.
- O aplicativo oficial MEI `Consulta Pendências` exige conta gov.br, e não prova por si só acesso via API SERPRO (https://www8.receita.fazenda.gov.br/simplesnacional/noticias/NoticiaCompleta.aspx?id=a7f63841-a727-4159-b3a5-156649959882).
- Alternativa potencial `SITFIS` existe no catálogo Integra Contador, mas não há integração SOLVERIS nem contrato/elegibilidade verificados.

**Decisão do gate:** não construir verificador numérico, nem retornar mensagem afirmando `sem dívidas` a partir de lista parcial, nem adicionar `DIVIDAATIVA24` à allowlist nesta etapa. Preferir card **informativo**, com links oficiais para:
- PGFN Regularize: https://www.regularize.pgfn.gov.br/
- Portal de Serviços da RFB: https://servicos.receitafederal.gov.br/
- PGMEI/Simples Nacional: https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATBHE/pgmei.app/Identificacao

Cópia segura para ratificação:
> **Perdão das contribuições antigas do MEI: veja o que a lei prevê.** A remissão da LC 238/2026 alcança contribuições previdenciárias federais vencidas até 13/10/2026; não abrange ICMS nem ISS. O processamento oficial está previsto a partir de 01/01/2027, observadas as condições legais. Consulte sua situação diretamente nos canais da Receita Federal e da PGFN. **A SOLVERIS ainda não consulta nem certifica individualmente seus débitos elegíveis.**

## 4. PixMEI: informação, não inscrição

Fonte ministerial (modificada em 11/11/2026):
https://www.gov.br/memp/pt-br/prospera-mei/pixmei

Alerta federal de fraudes em 29/10/2026:
https://www.gov.br/secom/pt-br/fatos/brasil-contra-fake/noticias/2026/10/governo-federal-alerta-para-golpes-envolvendo-o-pix-mei

- Apoio de **até R$ 5.000**, ainda proposta em estruturação; nenhum valor individual aprovado, edital/canal de inscrição sem publicação oficial comprovada neste corte, nenhum pagamento liberado.
- Referência de **R$ 40.500/ano** e priorização de mulheres empreendedoras são critérios de estudo/preliminares, não pré-aprovação.
- É permitido somente material de **preparação documental**, sem pedir dados bancários e sem parecer formulário oficial.
- `app/services/notification_service.py` é apenas adaptador de WhatsApp. Não há evidência de subscription+consent+storage+revogação+disparador de edital. **Não exibir botão ativo "Avisar quando sair" até existir fluxo real e verificável de aviso**.
- Antes de uso comercial, rever edital/inscrições no MEMP e publicar fonte/data de verificação.

Cópia segura para ratificação:
> **PixMEI: organize-se, mas ainda não há inscrições.** O governo estuda apoio produtivo de até R$ 5 mil, com seleção e regras definitivas a publicar. A SOLVERIS não inscreve participantes, não solicita dados bancários e não garante recebimento. Use os canais oficiais do MEMP e desconfie de taxas ou promessas de pagamento imediato.

## 5. Gates e próxima fase (separados)

1. **B1 informativo:** UI estática, links oficiais, sem consultas fictícias — teste DOM e revisão visual, deploy só por ratificação.
2. **B2 normativo:** internalização de LC 238, fonte/versão/hash/vigência, prova RED/GREEN e controle do requisito orçamentário antes de liberar 2027/2028. Manter DAS 2027 bloqueado se não houver autoridade própria.
3. **B1 dados reais FUTURO:** conferir habilitação `DIVIDAATIVA24`, procuração/acesso, proteção de dados, limites da API, resolução temporal, payloads reais sem vazamento, segregação INSS/ICMS/ISS e reconciliação com débitos não inscritos.
4. **B3 preparação:** só textos e checklist sem coleta sensível. Opt-in somente após mecanismo efetivo de notificação, autorização, persistência e cancelamento.
5. **Proibição de release:** não mexer em Railway/produção, SERPRO real, Mercado Pago ou banco de dados nesta etapa; NÃO associar esta branch ao merge da PR #32 sem nova comparação.

## 6. Falhas que um RED deve capturar

- 2027 devolvendo 81.000, ou novo valor sem fonte normativamente autorizada.
- 2028 devolvendo 110.000, ou sem diferenciação temporal.
- 2027 aceito pelo motor de DAS sem salário mínimo ou binding oficial.
- Anistia descrevendo corte em 31/10, incluindo ICMS/ISS, promessa de perdão já executado ou simulação sem dados oficiais.
- `DIVIDAATIVA24` consumido como prova de dívida TOTAL ou ausência de pendências.
- PixMEI descrito como inscrição aberta, promessa de concessão, opt-in de aviso sem persistência/disparo, ou pedido de chave Pix.

**Estado final:** investigação encerrada com decisões fail-closed; alterações operacionais **não iniciadas** e requerem contratos RED verdes, evidência normativa, autorização e ratificação visual antes de qualquer deploy.


## 7. Gate orçamentário verificado — LOA 2027 ainda pendente (13/11/2026)

Fonte oficial: Congresso Nacional, Orçamento 2027 — https://www.congressonacional.leg.br/web/orcamento/acompanhe/orcamento-anual/-/loa/2027

Constatação em 13/11/2026: projeto **PLN 24/2026**, último estado **06/11/2026 — AGUARDANDO RECEBIMENTO DE EMENDAS**; as etapas de votação em plenário e sanção estão **não iniciadas**. A Lei Complementar 238/2026, art. 3º, condiciona a ampliação dos limites de receita bruta à consideração da renúncia de receita nas LOAs 2027–2029.

**Consequência L3 vinculante:** não se demonstrou ainda o cumprimento da condição orçamentária para 2027. **Não trocar o valor constante do motor para R$ 110.000 em 2027 nem R$ 140.000 em 2028 por simples hardcode.** O texto do usuário pode explicar que a lei *prevê* os tetos, sujeitos à condição; no assistente fiscal, preservar bloqueio para ano sem autoridade completamente resolvida. A transição só se torna elegível para GREEN depois de localizar LOA sancionada, demonstrar a dotação/renúncia exigida, internalizar prova e vincular fonte+vigência+jurisdição+hash, com testes temporais; examinar também a LOA posterior para 2028.
