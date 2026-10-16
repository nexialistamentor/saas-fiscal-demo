# SOLVERIS Enterprise — I6: recibo de custódia assinada, não atestado SEFAZ

**Base obrigatória:** branch `work/fiscal-assumptions-c0`; HEAD `a017648a032c77cc2e431a4f3717542ddd0eed2b` (I5 remoto ratificado).

## Hipótese operacional e objetivo
A I5 liga XML exato, ItemFiscal, DocumentoFiscal e RelatorioAnalise à observação SOAP sintética/fornecida, com hashes, mas **não** prova que a resposta foi recebida da SEFAZ ou por um canal TLS autenticado. A I4N opt-in observa Schannel/PowerShell, mas hoje não conserva SOAP nem recibo independentemente assinado. I6 cria **apenas a fronteira de verificação do recibo de custódia externa**; não acrescenta um assinador nem modifica o operador I4N.

`vincular_custodia_nfe_i6`: valida assinatura Ed25519 da estrutura estrita do atestado (âncora de confiança = bytes de chave pública de origem EXTERNA e independente; **nunca** obtidos do próprio documento), UUIDv4, timestamp UTC recente (até cinco minutos), escopo Enterprise, identidade de protocolo declarada e SHA-256 dos bytes XML e SOAP, chave, autorizador, URL catalogado. Reexecuta I5 sobre os dados reais do chamador e exige correspondência com o relato assinado.

O atestado contém campos `tls_validation_declaration`, `client_certificate_declared`, `certificate_der_sha256`; **todos são ALEGAÇÕES assinadas do custodiante**, não fatos autenticados pela I6. Mesmo com assinatura válida, `origem_sefaz_criptograficamente_comprovada=False` e `tls_mtls_comprovado_independentemente=False`. Não interpretar `assinatura_custodiante_verificada=True` como autenticidade NF-e, validade de crédito ou apuração fiscal.

## Limitações e riscos bloqueantes
- I6 não gera chaves Ed25519 de produção, não assina, não consulta serviços externos e não grava em disco/BD; recebe somente chave pública explícita e bytes já sob custódia autorizada.
- Ainda não existe agente de custódia independente provisionado, segregação efetiva do assinador, cadeia de confiança formal, ledger imutável, armazenamento criptográfico de bytes SOAP, revisão do certificado cliente, assinatura XML NF-e validada nem mecanismo durável de anti-replay. Um evento `event_id` assinado **pode ser reproduzido** dentro da janela de cinco minutos enquanto não existir ledger externo de unicidade.
- Proibido usar a assinatura do mesmo processo que coletou dados como prova independente sem a separação operacional comprovada. **Nunca** inventar credenciais, atestados, assinatura de produção ou prova oficial para satisfazer testes.
- Nenhuma autorização de consulta para terceiros é presumida; a presença da NF-e de empresa terceira em repositório público não concede permissão. Não carregar esses XML reais como testes I6 nem incluir dados pessoais no Git.
- A resposta I6 inclui somente ids internos, hashes/indicadores; nenhuma chave NF-e em claro, certificado, assinatura, CNPJ, SOAP ou valores. `checkout_autorizado=False`, `direito_creditorio_comprovado=False` e `apuracao_mensal_completa=False` SEMPRE.

## Teste causal e isolamento
RED causal: módulo I6 ainda não existe. GREEN: 28 testes exclusivamente sintéticos com assinador Ed25519 **de teste**, imutabilidade, assinaturas incorretas, âncoras erradas, incompatibilidade de hashes, documentos/usuários diferentes, proteção temporal, não elevação fiscal. Regressões I5 (22), I4N (16), I3N (18), I3A (18), I2 (20), I1 (16), I0 (7) e regressão partilhada (12). Em Windows usar `DATABASE_URL=sqlite://` e `ALEMBIC_RUNNING=1`. Nenhum disparo de rede, nenhuma escrita em DB, MEI, deploy, payments ou PDF.

## Gate real seguinte (não resolvido pela I6)
Provisionar e auditar custodiante independente e âncora de confiança; implantar fluxo de resposta oficial permitido preservando bytes exatos e comprovativo de transporte, ledger de idempotência/replay e event-time. Só depois verificar integridade da NF-e e eventual evento SEFAZ, seguir para EFD-Contribuições/competência e normas NCM/ANP/UF antes de qualquer crédito estimado/real. Uma homologação com empresa e certificado legítimos permanece pendente.
