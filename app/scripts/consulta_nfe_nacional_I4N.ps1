# I4N: operador nacional de consulta UNICA, explicitamente autorizada.
# NUNCA executado pelo instalador. Nao faz retry/DB/deploy/exporta cert.
param(
  [Parameter(Mandatory=$true)][string]$ChaveNfe,
  [Parameter(Mandatory=$true)][string]$CertificateThumbprint,
  [Parameter(Mandatory=$true)][switch]$AutorizacaoDocumentalConfirmada,
  [Parameter(Mandatory=$true)][switch]$ExecutarConsultaOficial,
  [string]$RepoRoot = 'C:\dev\saas-fiscal-demo-a1'
)
$ErrorActionPreference = 'Stop'; Set-StrictMode -Version Latest
function Stop-I4N([string]$code) { throw "STOP_I4N: $code" }
if (-not $AutorizacaoDocumentalConfirmada -or -not $ExecutarConsultaOficial) { Stop-I4N 'AUTORIZACAO_EXPLICITA_OBRIGATORIA' }
if ($ChaveNfe -cnotmatch '^[0-9]{44}$') { Stop-I4N 'CHAVE_INVALIDA' }
if ($CertificateThumbprint -notmatch '^[0-9a-fA-F]{40}$') { Stop-I4N 'CERT_THUMBPRINT_INVALID' }
$Repo = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
if (-not [string]::Equals($Repo,'C:\dev\saas-fiscal-demo-a1',[StringComparison]::OrdinalIgnoreCase)) { Stop-I4N 'REPO_INVALID' }
$py = Join-Path $Repo '.venv-release\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) { Stop-I4N 'PYTHON_NOT_FOUND' }
$certs = @(Get-ChildItem Cert:\CurrentUser\My | Where-Object {
  $_.Thumbprint -eq $CertificateThumbprint -and $_.HasPrivateKey -and
  $_.NotBefore -le (Get-Date) -and $_.NotAfter -gt (Get-Date)
})
if ($certs.Count -ne 1) { Stop-I4N 'CERT_NOT_ELIGIBLE' }
$cert = $certs[0]
# Estado do repositório e assinatura de versão são separados da autorização fiscal.
$oldPY=$env:PYTHONPATH; $oldDB=$env:DATABASE_URL; $oldAlembic=$env:ALEMBIC_RUNNING
try {
  $env:PYTHONPATH=$Repo
  $env:DATABASE_URL='sqlite://'
  $env:ALEMBIC_RUNNING='1'
  $planText = & $py -B -m app.services.enterprise_nfe_sefaz_operador_i4n plan --chave $ChaveNfe
  if ($LASTEXITCODE -ne 0) { Stop-I4N 'PLAN_FAILED' }
  $plan = $planText | ConvertFrom-Json
  if ($plan.schema_version -ne 'ENTERPRISE_NFE_OPERADOR_I4N_V1' -or
      $plan.ambiente -ne 'producao' -or $plan.consulta_real_executada -ne $false -or
      $plan.checkout_autorizado -ne $false) { Stop-I4N 'PLAN_INVALID' }
  $uri = [Uri]$plan.endpoint
  if ($uri.Scheme -ne 'https' -or $uri.Port -ne 443 -or
      -not [string]::IsNullOrEmpty($uri.UserInfo) -or -not [string]::IsNullOrEmpty($uri.Fragment) -or
      -not [string]::IsNullOrEmpty($uri.Query)) { Stop-I4N 'ENDPOINT_INVALID' }
  $expected = [Convert]::FromBase64String($plan.soap_base64)
  $digestObj=[System.Security.Cryptography.SHA256]::Create()
  try { $soapHash=[BitConverter]::ToString($digestObj.ComputeHash($expected)).Replace('-','').ToLowerInvariant() } finally { $digestObj.Dispose() }
  if ($soapHash -ne $plan.soap_sha256) { Stop-I4N 'PLAN_BYTES_INVALID' }
  $existing = [Net.ServicePointManager]::SecurityProtocol
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Write-Host "SOLVERIS_I4N_OFFICIAL_SINGLE_QUERY_BEGIN AUTHORIZER=$($plan.autorizador) UF=$($plan.uf_emissora)"
    # Schannel com validacao TLS padrao do Windows, sem ignorar erros, sem redirects.
    $resp = Invoke-WebRequest -Uri $plan.endpoint -Method POST -Certificate $cert `
      -Body $expected -ContentType "application/soap+xml; charset=utf-8; action=`"$($plan.action)`"" `
      -TimeoutSec 25 -MaximumRedirection 0 -UseBasicParsing -ErrorAction Stop
  } catch {
    Stop-I4N 'HTTPS_MTLS_OR_SEFAZ_REJECTED_NO_RETRY'
  } finally {
    [Net.ServicePointManager]::SecurityProtocol = $existing
  }
  if ($resp.StatusCode -ne 200 -or $null -eq $resp.RawContentStream) { Stop-I4N 'HTTP_OR_STREAM_INVALID' }
  $stream = $resp.RawContentStream
  $stream.Position = 0
  $mem = New-Object System.IO.MemoryStream
  try { $stream.CopyTo($mem); $responseBytes=$mem.ToArray() } finally { $mem.Dispose() }
  if ($responseBytes.Length -lt 1 -or $responseBytes.Length -gt 262144) { Stop-I4N 'RESPONSE_SIZE' }
  # Analise pelo interpretador I3N, com bytes enviados diretamente por pipe.
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $py
  $psi.Arguments = "-B -m app.services.enterprise_nfe_sefaz_operador_i4n parse --chave $ChaveNfe"
  $psi.WorkingDirectory = $Repo
  $psi.UseShellExecute = $false
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  try {
    if (-not $p.Start()) { Stop-I4N 'PARSER_START_FAILED' }
    $p.StandardInput.BaseStream.Write($responseBytes,0,$responseBytes.Length)
    $p.StandardInput.Close()
    $output=$p.StandardOutput.ReadToEnd()
    $null=$p.StandardError.ReadToEnd()
    $p.WaitForExit()
    if ($p.ExitCode -ne 0) { Stop-I4N 'OFFICIAL_RESPONSE_NOT_INTERPRETABLE' }
  } finally { $p.Dispose() }
  $observed = $output | ConvertFrom-Json
  if ($observed.chave_sha256 -ne $plan.chave_sha256 -or
      $observed.endpoint_catalogado -ne $plan.endpoint -or
      $observed.autorizador -ne $plan.autorizador -or
      $observed.checkout_autorizado -ne $false) { Stop-I4N 'EVIDENCE_BINDING_INVALID' }
  Write-Host "SOLVERIS_I4N_OFFICIAL_TLS_RESPONSE_OBSERVED"
  Write-Host "AUTORIZADOR=$($observed.autorizador) UF=$($observed.uf_emissora)"
  Write-Host "CSTAT=$($observed.cstat) SITUACAO=$($observed.situacao_declarada)"
  Write-Host "CHAVE_SHA256=$($observed.chave_sha256)"
  Write-Host "RESPONSE_SHA256=$($observed.resposta_sha256)"
  Write-Host 'NO_DB_NO_CREDIT_CLAIM_NO_PAYMENT_NO_DEPLOY_NO_RETRY'
} finally {
  $env:PYTHONPATH=$oldPY; $env:DATABASE_URL=$oldDB; $env:ALEMBIC_RUNNING=$oldAlembic
}
