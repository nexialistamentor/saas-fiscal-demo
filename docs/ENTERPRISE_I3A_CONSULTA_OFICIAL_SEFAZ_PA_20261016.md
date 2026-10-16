# SOLVERIS — I3A, consulta oficial de situação NF-e (SVRS-PA)

Baseline: `work/fiscal-assumptions-c0` / `373edf4fc07649ddce3e1fca1425477667187b96`.

## Fonte oficial
Portal Nacional NF-e, Relação de Serviços Web: Pará usa SVRS para serviços NF-e; `NfeConsultaProtocolo` versão 4.00, endpoint produção:
`https://nfe.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx`.

## Conclusão desta intervenção
- Biblioteca PURA constrói `consSitNFe` 4.00 em SOAP 1.2, validando chave NF-e modelo 55 de PA, e interpreta respostas sob namespace e formato rigoroso.
- Classifica autorização, cancelamento, denegação, ausência, consumo indevido, erro não conclusivo. Protocolo/identidade/ambiente precisam ser coerentes.
- Nenhum XML auto-declarado vira atestado de consulta ao serviço: parser sempre marca `situacao_oficial_confirmada=False` até existir transportador externo auditado.
- Instalação não envia solicitações externas. O script Windows manual é um operador de **consulta única** por chave real, usando certificado do Windows sem exportar a chave privada. Exige declaração explícita de titularidade/mandato e confirmação de envio.
- `xmlsec` não instalado; autenticação TLS cliente por certificado não substitui a validação de assinatura dos documentos NF-e recebidos. Consulta de situação não representa exame da EFD ou prova creditória.
- Sem alteração do MEI, InsightEngine, database, checkout, PDF, routes, deploy, migrations ou pagamentos.

## Continuidade
I3B: operador mTLS auditado, consulta real autorizada sobre documento persistido, ligação de protocolo atual/eventos ao relatório, clock/limite de consumo e auditoria de titularidade. I3C: cobertura por competência com EFD-Contribuições/NFS-e + regra temporal e habilitação explícita de evidência de crédito quando comprovada; nunca inferir crédito por simples ICMS excluído.
