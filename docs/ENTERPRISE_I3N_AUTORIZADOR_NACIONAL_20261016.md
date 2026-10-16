# SOLVERIS Enterprise — I3N: encaminhamento nacional por chave NF-e

**Baseline obrigatória:** `work/fiscal-assumptions-c0` HEAD `373edf4fc07649ddce3e1fca1425477667187b96`, com quatro ficheiros I3A ainda untracked e homologados. **Não ratificar a I3A PA como produto nacional isolado**.

Fonte primária: [Portal Nacional NF-e, relação de serviços Web](https://www.nfe.fazenda.gov.br/portal/WebServices.aspx), consultado em 16/10/2026. Catálogo de 27 UFs de emissão, 12 autorizadores normais (SVRS, SVAN e 10 próprios), ambientes de produção. Algumas URLs oficiais aparecem com `?wsdl`; a forma configurada usa endpoint SOAP sem a query de descrição.

## Âmbito e distinções

- O `cUF` da **chave NF-e**, e não o endereço do operador ou a UF de destino, seleciona o autorizador; modelo deve ser 55, DV válido por módulo 11, SOAP 1.2 4.00, chave e protocolo coerentes.
- PA, RJ e mais 14 UFs usam SVRS; MA usa SVAN; SP e RS usam autorizadores próprios, assim como AM, BA, GO, MG, MS, MT, PE e PR. **Isso não equivale à norma tributária da UF**.
- Não encaminhar para contingência SVC automaticamente: requer análise do tipo de emissão, autorização e protocolo vigente.
- A I3A PA permanece compatível e testada. A I3N acrescenta a porta de entrada nacional pura; nenhuma das duas executa rede, lê certificados ou grava dados.
- Resposta simulada não é prova do serviço remoto: `situacao_oficial_confirmada=False`. Apenas transporte TLS/mTLS verificado, proveniência autenticada e vínculo ao documento permitirão futuramente elevação de autoridade.
- Cada endpoint exige teste de homologação oficial e certificado autorizado antes de consultas reais. Rotas em catálogo não equivalem a conectividade certificada.

## Combustíveis e regimes fiscais

- Consultar situação de NF-e é um **problema de roteamento e autenticidade documental**. Apurar tributos é **problema normativo item-a-item**: competência, NCM, ANP, CFOP, CST/CSOSN, modalidade monofásica, UF origem/destino, cadeia, regime e fonte oficial vigente.
- O ICMS monofásico de combustíveis (Convênios ICMS 199/2022 e 15/2023) exige exceção explícita no motor; **não se pode inferir ICMS próprio, alíquota ou crédito com base apenas na UF ou nas tags `vICMS`**.
- Esta intervenção não calcula tributos nem certifica receita, EFD, pagamento ou restituição.

## Gates

RED causal (módulo nacional ausente), GREEN 18 testes nacionais, 18 testes I3A, 20 I2, 16 I1, 7 I0, todos read-only de DB e sem rede. Só os três novos ficheiros são copiados; os quatro I3A locais devem conservar exatamente os SHA homologados.

Após GREEN local: commit e push único dos sete ficheiros da capacidade I3A + I3N, sem deploy. Depois: transporte mTLS/certificado autorizado, verificação oficial, cruzamento item/norma temporal e cobertura EFD por competência.
