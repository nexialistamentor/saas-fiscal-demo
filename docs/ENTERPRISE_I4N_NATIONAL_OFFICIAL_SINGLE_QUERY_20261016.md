# SOLVERIS Enterprise — I4N operador nacional de consulta única

Base: branch `work/fiscal-assumptions-c0`, commit `7d124229464f88ccba293907ad9657f73636297d`.

O serviço nacional é selecionado por `cUF` e DV da chave modelo 55, sem inferência de alíquota/UF do contribuinte. A operação real é **manual e opt-in** com chave de NF-e legitimamente acessível, autorização documental e thumbprint do certificado privado elegível no Windows, controlados pelo operador. Não é iniciada por testes ou instalador. O certificado não é exportado. Resposta via Windows TLS, com certificado cliente, sem desativar validação ou redirecionar, sem retry automático.

Composição: `enterprise_nfe_sefaz_nacional_i3n` (plano e parser SOAP puro) -> `enterprise_nfe_sefaz_operador_i4n` (CLI puro, liga plano/hash/interpretador) -> `consulta_nfe_nacional_I4N.ps1` (único executor real opcional).

Resultados: observação TLS de retorno SOAP de serviço catalogado (chave SHA, SOAP SHA, cStat e situação), **sem gravação de SOAP bruto e sem atestado independente da assinatura XML**. Uma resposta `100` observada não demonstra que os bytes XML entregues pelo cliente sejam autênticos, nem escrituração, NF-e cancelada posteriormente, EFD, tributo ou direito a crédito. A prova durável ainda requer custódia auditável do retorno e vinculação à I2 com carimbo temporal/conferência de eventos. Sem lote ou cobertura de todos os documentos do mês.

Fonte de endpoints: https://dfe-portal.svrs.rs.gov.br/Nfe/Servicos e https://www.nfe.fazenda.gov.br/portal/WebServices.aspx. Endpoints normais 4.00, produção, sem fallback automático para contingência.

**Gates de instalação:** I4N RED e GREEN; regressões I3N, I3A, I2, I1, I0; estado e hashes; nenhuma consulta na instalação; alterações só nos 4 ficheiros novos. Não fazer deploy, DB/migrations, MEI ou pagamentos. O script de consulta separada não é executado pelo instalador.
