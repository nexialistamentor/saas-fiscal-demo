# SOLVERIS Enterprise — I11: manifesto de custódia LCR e comparação anti-rollback

**Corte:** 16/10/2026. **Base exigida:** `work/fiscal-assumptions-c0` em `98c1b40bc6c6cadb7f8d18c0d85af1cabc00ae34` (I10 ratificada). Apenas o diagnóstico Enterprise integral, sem SKU reduzido.

## Papel exato

`conferir_proveniencia_lcr_i11` recebe os argumentos completos da I10 e **reexecuta** `verificar_lcr_nfe_i10`, que já cruza NF-e 55 → XMLDSig I7 → emitente I8 → cadeia X.509 I9 → LCRs I10. Depois verifica um **manifesto Ed25519** de aquisição de evidências assinado por custodiante externo. A chave pública fiável vem do chamador, fora do manifesto e do repositório; não pode ser extraída do documento analisado.

O manifesto é estrito, determinístico e inclui: SHA-256 do XML, chave de acesso em hash, digest do recibo I10, digest da raiz aprovada, digests DER e CRLNumber e thisUpdate/nextUpdate para todas as LCRs, UUIDv4, sequência, hash do manifesto anterior, marca temporal UTC e declaração explícita de **procedência não oficialmente comprovada**. Recusa alteração de qualquer byte, assinaturas falsas, omissões, CRLNumber incompatível e manifesto com mais de 5 minutos em relação ao relógio UTC fornecido.

A **comparação anti-rollback** exige, para sequências posteriores ao bootstrap, um estado anterior fornecido e aprovado fora do manifesto. Rejeita sequência repetida/saltada, predecessor divergente, troca de raiz, CRLNumber menor e *mesmo CRLNumber com bytes diferentes*. A função devolve o estado **proposto** que um host independente poderá persistir/ratificar. O módulo não persiste esse estado nem consegue autenticar o estado anterior: um chamador pode fornecer estado falso. Assim, `antirollback_duravel_verificado=False` SEMPRE.

## Autoridade não adquirida

- **I11 não valida a origem oficial ITI/ICP-Brasil, a legalidade da aquisição ou a cadeia de confiança completa**. Assinatura do custodiante e hashes não demonstram que a fonte seja oficial. `origem_oficial_iti_verificada=False`, `cadeia_icp_brasil_verificada=False`, `revogacao_oficial_global_verificada=False`.
- `temporalidade_externa_autenticada=False`: data UTC foi fornecida pelo chamador, sem autoridade de tempo independente. É vedado confundir janela declarada com atualidade oficial.
- `situacao_sefaz_confirmada=False`, `efd_competencia_reconciliada=False`, `apuracao_mensal_completa=False`, `direito_creditorio_comprovado=False`, `checkout_autorizado=False`.
- **NENHUM** certificado, LCR, XML real, chave privada, CNPJ, chave NF-e em claro, credencial ou assinatura assinadora de produção é incluído no pacote. A chave privada fixa presente no teste pertence apenas a uma fixture sintética e não pode ser usada fora dos testes.
- Nenhuma rede, BD, ficheiro local, secret store, Windows Certificate Store, MEI, pagamentos ou deploy. Não é permitido simular aprovação oficial por meio de `True` autodeclarado.

## Testes e gates

RED causal: módulo ausente, um teste falha por `I11_RED_CAUSAL_MISSING_MODULE`. GREEN: 32 testes sintéticos I11 cobrindo assinatura, chave errada, validade temporal, vínculo a I10, listagem LCR, digest, sequência, substituição de origem, retrocesso de número e estado anterior. Regressões de I10 (28), I9 (24), I8 (22), I7 (26 + 3 C14N), I6 (28), I5 (22), I4N (16), I3N (18), I3A (18), I2 (20), I1 (16), I0 (7) e suites partilhadas (12). Python local com `DATABASE_URL=sqlite://`, `ALEMBIC_RUNNING=1`, sem rede ou consultas externas.

## Continuação do circuito integral

1. Realizar **aprovisionamento independente das âncoras oficiais do ITI**, com validação da política aplicável, avaliação PKIX/RFC5280 e aquisição de LCRs/OCSP por canal legitimado; ativar ledger externo durável e proteção de rollback real.
2. Encaixar I4N→I6 com bytes SOAP originais e custódia autêntica sob autorização documental válida; nunca presumir que certificado Windows permite consulta universal às NF-e de terceiros.
3. Avançar para EFD/SPED por competência e reconciliação de normas fiscais por UF, NCM, ANP, regime e item; só então crédito, PDF de prova e oferta do diagnóstico integral sob gates comerciais existentes.
4. Tratar a exposição de XMLs empresariais no repositório público em intervenção independente autorizada, sem apagar evidências ou presumir que eliminar o ficheiro no HEAD apaga o histórico.
