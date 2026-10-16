# I3A consultoria real avulsa, operador EXTERNO, NAO invocado pelo instalador.
# SOMENTE PA, chave propria ou expressamente autorizada; uma chamada por execucao.
param(
  [Parameter(Mandatory=$true)][string]$ChaveNfe,
  [Parameter(Mandatory=$true)][string]$CertificateThumbprint,
  [Parameter(Mandatory=$true)][switch]$AutorizacaoDocumentalConfirmada,
  [Parameter(Mandatory=$true)][switch]$ExecutarConsultaOficial
)
$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest
if (-not $AutorizacaoDocumentalConfirmada -or -not $ExecutarConsultaOficial) { throw 'STOP: AUTORIZACAO_EXPLICITA_OBRIGATORIA' }
if ($ChaveNfe -cnotmatch '^15[0-9]{42}$' -or $ChaveNfe.Substring(20,2) -ne '55') { throw 'STOP: CHAVE_NFE_PA_INVALIDA' }
if ($CertificateThumbprint -notmatch '^[a-fA-F0-9]{40}$') { throw 'STOP: CERT_THUMBPRINT_INVALID' }
$matches=@(Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object { $_.Thumbprint -eq $CertificateThumbprint -and $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) -and $_.NotBefore -le (Get-Date) })
if ($matches.Count -ne 1) { throw 'STOP: CERTIFICADO_NAO_ELEGIVEL_NO_STORE' }
$cert=$matches[0]
# Esta chamada utiliza Schannel/WinHTTP do PowerShell; nao exporta o certificado.
# Nao comprova por si direito de consultar terceiros nem assinatura da NF-e.
$url='https://nfe.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx'
$ns='http://www.portalfiscal.inf.br/nfe'
$ws='http://www.portalfiscal.inf.br/nfe/wsdl/NFeConsultaProtocolo4'
$action="$ws/nfeConsultaNF"
$soap='http://www.w3.org/2003/05/soap-envelope'
$body="<?xml version=`"1.0`" encoding=`"utf-8`"?><s:Envelope xmlns:s=`"$soap`"><s:Body><nfeDadosMsg xmlns=`"$ws`"><consSitNFe xmlns=`"$ns`" versao=`"4.00`"><tpAmb>1</tpAmb><xServ>CONSULTAR</xServ><chNFe>$ChaveNfe</chNFe></consSitNFe></nfeDadosMsg></s:Body></s:Envelope>"
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
Write-Host 'SOLVERIS_I3A_OFFICIAL_SINGLE_QUERY_BEGIN'
try {
  $resp=Invoke-WebRequest -Uri $url -Method Post -Certificate $cert -Body ([Text.Encoding]::UTF8.GetBytes($body)) -ContentType "application/soap+xml; charset=utf-8; action=`"$action`"" -TimeoutSec 25 -MaximumRedirection 0 -UseBasicParsing -ErrorAction Stop
} catch {
  Write-Host 'SOLVERIS_I3A_EXTERNAL_TRANSPORT_UNAVAILABLE'
  throw 'STOP: HTTPS_MTLS_OR_SEFAZ_REJECTED_NO_RETRY'
}
if ($resp.StatusCode -ne 200 -or [Text.Encoding]::UTF8.GetByteCount([string]$resp.Content) -gt 262144) { throw 'STOP: HTTP_RESPONSE_INVALID' }
[xml]$xml=[string]$resp.Content
$mgr=New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
$mgr.AddNamespace('s',$soap);$mgr.AddNamespace('n',$ns)
$ret=$xml.SelectSingleNode('/s:Envelope/s:Body//n:retConsSitNFe',$mgr)
if ($null -eq $ret -or $ret.GetAttribute('versao') -ne '4.00') { throw 'STOP: SEFAZ_RESPONSE_INVALID' }
$respKey=$ret.SelectSingleNode('n:chNFe',$mgr)
$amb=$ret.SelectSingleNode('n:tpAmb',$mgr)
$cstat=$ret.SelectSingleNode('n:cStat',$mgr)
if ($null -eq $respKey -or $respKey.InnerText -cne $ChaveNfe -or $null -eq $amb -or $amb.InnerText -ne '1' -or $null -eq $cstat -or $cstat.InnerText -notmatch '^[0-9]{3}$') { throw 'STOP: SEFAZ_RESPONSE_IDENTITY_MISMATCH' }
# O resultado bruto NAO fica guardado, mas o cStat e apresentado para a proxima homologacao.
Write-Host "SEFAZ_CSTAT=$($cstat.InnerText)"
Write-Host 'OFFICIAL_RESPONSE_RECEIVED_TLS_CERTIFICATE_USED'
Write-Host 'NO_DB_NO_FISCAL_PROOF_NO_PAYMENT_NO_DEPLOY'
