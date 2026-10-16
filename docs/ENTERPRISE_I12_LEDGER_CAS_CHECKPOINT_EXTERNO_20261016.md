# SOLVERIS Enterprise — I12: ledger local CAS com checkpoint externo assinado

Corte de 16/10/2026. Baseline obrigatória: branch `work/fiscal-assumptions-c0`, HEAD `93df5d8dc19a5d59b71d6f20be0f06de318dfa5b` (I11 ratificada). Continuação de **uma só SOLVERIS Enterprise integral**, não de um mini-modelo.

## Problema causal

A I11 valida a assinatura de um manifesto de LCR e compara progressão de números/manifestos com um `estado_previo_aprovado` que é recebido como argumento. Isso não demonstra unicidade nem persistência entre execuções; o operador poderia reapresentar um estado antigo. A I12 cria **um registo transacional local verificável** e exige um **checkpoint externo assinado** para aprovar exatamente o estado do ledger antes de cada transição.

## Fronteiras

- `enterprise_nfe_i12_custody_ledger.py` recebe uma `sqlite3.Connection` *explicitamente fornecida*, `ledger_id` UUIDv4, os argumentos completos I10, o manifesto I11, a chave pública confiada do custodiante I11, um checkpoint Ed25519 externo **independente** e respetiva chave pública confiada. Não abre ficheiros nem cria bases ou tabelas automaticamente. `provisionar_schema_ledger_i12` exige `autorizar_criacao_esquema=True` explícito pelo host; **o instalador não invoca o provisionamento em nenhuma base do projeto**.
- O checkpoint externo tem schema fechado, identifica ledger, sequência anterior, SHA-256 do estado e SHA-256 do manifesto anterior. É verificado matematicamente contra chave pública explicitamente recebida, distinta da chave de custódia da I11. A origem real do checkpoint e a independência operacional das chaves **ainda precisam de provisão externa**.
- `registrar_custodia_lcr_i12` abre `BEGIN IMMEDIATE`, lê o estado SQLite com integridade SHA, compara *exatamente* ao checkpoint assinado, reexecuta I11→I10→I9→I8→I7, grava um novo estado com verificação CAS e COMMIT atómico. Qualquer recusa efetua rollback. A resposta contém somente hashes, ID aleatório, sequência e limites de autoridade; o estado persistido guarda exclusivamente hashes de raízes/LCRs e CRLNumber, sem CNPJ, XML, SOAP, certificados ou assinatura privada.
- O recibo marca `checkpoint_externo_de_saida_ainda_nao_assinado=True`: o sistema **não tem** assinador independente de produção. Para a sequência seguinte, um actor externo terá de aprovar e assinar o novo checkpoint. Não é permitido autogerar chaves ou usar as chaves sintéticas dos testes.
- `consultar_ponta_ledger_i12` só lê e confere SHA do estado, sem modificar o ledger.

## Autoridade não adquirida

`comparacao_cas_sqlite_local_confirmada=True` significa apenas transação e sequenciação **dentro daquela ligação/ficheiro SQLite**. Não comprova resistência a restauração de backup, perda de dados, administração maliciosa ou substituição simultânea do ficheiro e do checkpoint aprovado. A origem ITI, a confiança ICP-Brasil, a validade temporal oficial, OCSP, situação SEFAZ, EFD por competência e direitos creditórios continuam não comprovados e as respetivas flags, incluindo `checkout_autorizado`, mantêm-se **False**. Não afirmar antirollback durável externo enquanto não existir um host/serviço independente autenticado e auditado.

## Disciplina da intervenção

O pacote acrescenta **apenas** módulo I12, 34 testes sintéticos e este registo. RED causal com módulo ausente; GREEN 34; regressões I11=32, I10=28, I9=24, I8=22, I7=26, I7 C14N=3, I6=28, I5=22, I4N=16, I3N=18, I3A=18, I2=20, I1=16, I0=7 e testes partilhados. Testes I12 usam SQLite `:memory:` e um ficheiro sob `TemporaryDirectory` eliminado automaticamente. Nenhuma execução é conectada à base do projecto, não são criadas migrações nem alterados motores e rotas.

## Próximas ligações do produto integral

1. Aprovisionamento independente das raízes oficiais ITI, validação completa de política de certificado e dos caminhos PKIX; aquisição auditável de LCR/OCSP e checkpoint assinado operado fora do repositório e fora do mesmo host. Não carregar certificado privado para o Git.
2. Proveniência real e custódia autenticada de respostas SEFAZ sob autorização documental, incluindo retenção protegida dos bytes SOAP, atestado de canal e estado anti-replay.
3. EFD/SPED por competência, identificação de item/UF/NCM/ANP/regime, aplicação de fonte normativa com versão/vigência, cálculo reproduzível, créditos, histórico, ranking, relatórios e todos os gates comerciais do diagnóstico integral.
4. Tratar a exposição de XMLs reais num repositório público mediante intervenção de privacidade separada e autorizada; retirar ficheiros de um commit futuro por si só não elimina o histórico.

**Não toca no MEI, pagamentos, produção, certificados Windows, SEFAZ, migrações, deploy nem base de dados real.**
