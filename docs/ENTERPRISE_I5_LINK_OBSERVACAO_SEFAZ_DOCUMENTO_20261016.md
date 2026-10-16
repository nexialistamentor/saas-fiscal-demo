# SOLVERIS Enterprise — I5: observação SOAP vinculada ao documento fiscal

Base: `work/fiscal-assumptions-c0` / `5896746c695efb4611aff666036d23e0ca7e71d1`.

## Autoridade e âmbito

- Projeta somente observação **offline, interna e read-only**: reutiliza `projetar_diagnostico_integral_i2` para garantir que XML, relatório, empresa, titular, fingerprint e itens persistidos reconciliam; reutiliza `interpretar_observacao_unica` (I4N) e I3N para interpretar uma resposta SOAP e encaminhar a chave modelo 55 ao autorizador correto.
- Os **bytes da resposta SOAP** e os bytes **exatos do XML** são necessários nesta entrada; a saída inclui hashes SHA-256 de ambos, chave em hash, IDs internos e um recibo determinístico. NENHUM SOAP bruto, CNPJ, chave NF-e em claro, valores financeiros ou certificado aparece no recibo. Nenhuma persistência ou exportação ocorre.
- `cStat=100` nunca prova que a resposta veio da SEFAZ, que o XML está assinado corretamente, que não houve evento posterior, ou que existe tributo/crédito reconhecido. A origem TLS/mTLS, custódia independente e temporalidade do evento continuam **não atestadas**; todos os booleanos de autoridade e checkout são `False`, inclusive para `101` e `656`.
- I5 **não modifica** I0/I1/I2/I3A/I3N/I4N, rotas, motores fiscais, banco, certificado, MEI, PDF, pagamentos ou produção. Não consulta serviços externos.
- O I4N de execução manual **não preserva o SOAP**; logo, o primeiro teste real I4N ainda não preenche a entrada da I5. Essa lacuna será fechada por uma custódia local apropriada e por um atestado de transporte verificável; o recibo I5 é uma preparação auditável, **não** uma evidência oficial com proveniência demonstrada.
- O repositório contém XML potencialmente real de terceiros em pasta pública. Conter essa exposição, regularizar a custódia e substituir fixtures requer intervenção independente e autorizada; não acrescentar novos dados sensíveis ao Git nem executar consulta sem autorização documental.

## RED/GREEN

Suites: 22 testes I5 com XML/SOAP exclusivamente sintéticos, 16 I4N, 18 I3N, 18 I3A, 20 I2, 16 I1 e 7 I0; regressão partilhada selecionada. Env local `DATABASE_URL=sqlite://`, `ALEMBIC_RUNNING=1`. Import de `app.database` primeiro. Nenhuma operação real ou crédito autorizado.

## Objetivos seguintes

1. Custódia da resposta SOAP de uma consulta legitimamente autorizada, com testemunho de canal/certificado e timestamp auditável, **sem gravar dados pessoais no Git**.
2. Verificação criptográfica da assinatura XML NF-e e dos eventos/protocolo com autoridade apropriada.
3. Reconciliação EFD-Contribuições por competência, aplicação da norma vigente à operação/item/regime, e só então avaliação de créditos. Cobertura fiscal não equivale a valor recuperável.
