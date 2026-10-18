# SOLVERIS Enterprise — G1.1, correção na origem da consistência fiscal

Corte 16/10/2026; base remota esperada `work/fiscal-assumptions-c0`, SHA `70c49a5c545fc693ea7d6dd547db8f824e865bc3`.

## Defeito comprovado na inspeção do HEAD

- `TaxConsistencyEngine.verificar_consistencia({}, {})` devolvia `consistente=True` sem comparação.
- `app/xml_service.py:processar_e_persistir_xml` usa o motor acima no fluxo existente.
- `app/motor_fiscal.py:analisar_xml` copia `valor_st` e `base_st` do primeiro item XML em `icms_st`/`base_st` e não recalcula esses valores independentemente.
- MVA declarada por item não está capturada no parser central; confronto escalar não é prova.

## Contrato G1.1

A implementação **não substitui** os motores ST/MVA/PMPF, não altera rotas, esquemas de BD, migrations, cobrança ou o fluxo MEI. Corrige o contrato do motor de consistência já ligado ao processamento XML.

1. Sem `itens_calculados`, a resposta é `NAO_AVALIADO`, `consistente=None`.
2. Quando é fornecida uma lista externa de resultados *informativos* por item, exige igualdade de chave documental, cardinalidade, índices exclusivos, NCM e CFOP; só então compara `valor_st` e `base_st` observados com os valores calculados.
3. A coincidência numérica usa `Decimal`, tolerância de R$ 0,01, sem arredondamento de números inválidos. Pares inválidos ficam não avaliados.
4. **Nenhuma entrada fornecida pelo chamador tem autoridade fiscal intrínseca.** Mesmo com coincidência, `consistente=None`, `autoridade_fiscal=False`, `credito_confirmado=False`, `checkout_autorizado=False`.
5. O retorno permanece compatível nas chaves `consistente`, `divergencias`, adicionando estado causal e contagem dos pares comparados.
6. Nenhum XML real é necessário. Sintéticos são suficientes para testar a fronteira; prova fiscal futura requer norma específica, período, fonte oficial, cálculo independente, recolhimento quando necessário, titularidade e nível de confiança.

## Gates de execução

- Red: verifica o falso `consistente=True` na versão original, sem escrever no repositório.
- Green efémero: 22 testes sobre módulo preparado, antes de escrever no repositório.
- Instalação: substitui **apenas** `app/services/tax_consistency/tax_consistency_engine.py`, acrescenta um teste e documentação G1.
- Green no worktree: repete 22 testes diretamente sobre o módulo instalado.
- Regressões: testes reais selecionados de créditos ST, origem histórica, análise XML e ponte documental Enterprise.
- Ratificação Git: commit e push ficam fora do executor, aguardam revisão do resultado.
- **Nenhum** deploy, rede, DB produtiva, SEFAZ, LCR, MEI, pagamento ou alteração a outro worktree.

## Limites explícitos

O novo campo `itens_calculados` ainda não é produzido pelo `motor_fiscal.analisar_xml` existente. O estado real padrão será `NAO_AVALIADO` até ligar um fornecedor independente por item com autoridade normativa. É uma correção de falso positivo na origem, não a conclusão dos gates G1/G2/G3.
