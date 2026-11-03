# SOLVERIS B02: executar SOMENTE após revisão segregada, adoção e aprovação
# específica dos novos bytes por Miguel. Não executar com aprovação V1 antiga.
param(
  [Parameter(Mandatory=$true)][string]$ParecerJson,
  [Parameter(Mandatory=$true)][string]$AutoridadeAdotadaJson,
  [Parameter(Mandatory=$true)][string]$Sha256AutoridadeAdotada
)
& {
  $ErrorActionPreference = 'Stop'
  $repo = 'C:\dev\solveris-b02-g5-v5-publicacao'
  $root = "$HOME\Downloads\SOLVERIS_B02_ASSINATURA_AUTORIZADA_20261022"
  $original = "$root\BUNDLE_SUCESSOR_V2_CANONICO_CORRIGIDO"
  $bundle = "$root\BUNDLE_SUCESSOR_V2_24H_20261103_1800UTC"
  $signer = "$root\b02_documentary_signer_v2.py"
  $legacy = "$root\crypto_local.py"
  $adoption = "$repo\evidence\b02\B02_G4_CONTINUIDADE_DOCUMENTAL_V2_ADOCAO_EMITIDA_20261103.json"
  $public = "$env:LOCALAPPDATA\SOLVERIS\CustodiaB02\Chave_ceee5bb6f2a740a58cf4dbaa66565698\miguel-public.der"
  $private = "$env:LOCALAPPDATA\SOLVERIS\CustodiaB02\Chave_ceee5bb6f2a740a58cf4dbaa66565698\miguel-private-encrypted.pem"
  $commit = '7195b89385700291882f63b2f08c66e73d226c29'
  $codeblob = 'b8ff97373476bb3ef1b34362612eedd014f0ff21'
  $decision = 'd3602168c53debd10421aa83d1e980c632870b660be18a451d5b5a3d998c6520'
  $fingerprint = '6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c'

  if ([DateTimeOffset]::UtcNow -lt [DateTimeOffset]::Parse('2026-11-03T18:00:00+00:00') -or
      [DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse('2026-11-04T18:00:00+00:00')) {
    throw 'STOP_B02_SIGNER_V2_JANELA_NAO_ABERTA_OU_EXPIRADA'
  }
  foreach ($path in @($ParecerJson,$AutoridadeAdotadaJson,$legacy,$adoption,$public,$private)) {
    if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
      throw "STOP_B02_SIGNER_V2_FICHEIRO_AUSENTE:$path"
    }
  }
  if (-not (Test-Path -LiteralPath $original -PathType Container)) { throw 'STOP_B02_CANONICO_AUSENTE' }
  if ((Get-FileHash $public -Algorithm SHA256).Hash.ToLowerInvariant() -cne $fingerprint) {
    throw 'STOP_B02_PUBLICA_NAO_RECONHECIDA'
  }
  if ((Get-FileHash $AutoridadeAdotadaJson -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Sha256AutoridadeAdotada) {
    throw 'STOP_B02_AUTORIDADE_DIVERGENTE'
  }
  # Recuperar EXATAMENTE os bytes UTF-8 do ato próprio publicado pelo titular,
  # não aceitar ficheiro + hash escolhidos pelo operador. O próprio assinador
  # fará a mesma consulta, independente da gravação deste ficheiro local.
  $AutorizacaoExataTxt = Join-Path $root 'B02_PR28_AUTORIZACAO_ORIGINAL_GITHUB_6605195432.txt'
  @'
import json,sys,urllib.request,pathlib,hashlib
url='https://api.github.com/repos/nexialistamentor/saas-fiscal-demo/issues/comments/6605195432'
req=urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'SOLVERIS-B02-signer-V2-readonly'})
with urllib.request.urlopen(req,timeout=12) as resp:
 assert resp.status==200 and resp.geturl()==url,'STOP_GITHUB_SOURCE_REDIRECT'
 data=json.load(resp)
assert data.get('id')==6605195432,'STOP_GITHUB_COMMENT_ID'
assert data.get('user',{}).get('login')=='nexialistamentor' and data['user'].get('id')==192223328,'STOP_GITHUB_ISSUER'
assert data.get('author_association')=='OWNER' and data.get('issue_url')=='https://api.github.com/repos/nexialistamentor/saas-fiscal-demo/issues/28','STOP_GITHUB_ORIGIN'
assert data.get('created_at')==data.get('updated_at'),'STOP_GITHUB_ACT_EDITED'
body=data['body'].encode('utf-8')
assert b'd3602168c53debd10421aa83d1e980c632870b660be18a451d5b5a3d998c6520' in body,'STOP_GITHUB_DECISION_BINDING'
p=pathlib.Path(sys.argv[1]);p.parent.mkdir(exist_ok=True,parents=True)
if p.exists(): assert p.read_bytes()==body,'STOP_LOCAL_AUTHORIZATION_CHANGED'
else: p.write_bytes(body)
print('B02_GITHUB_ORIGINAL_AUTHORIZATION_SHA256='+hashlib.sha256(body).hexdigest())
'@ | python - $AutorizacaoExataTxt
  if ($LASTEXITCODE -ne 0) { throw 'STOP_B02_GITHUB_AUTHORIZATION_RETRIEVAL' }
  $Sha256AutorizacaoExata = (Get-FileHash -LiteralPath $AutorizacaoExataTxt -Algorithm SHA256).Hash.ToLowerInvariant()

  git -C $repo fetch --no-tags origin $commit
  if ($LASTEXITCODE -ne 0) { throw 'STOP_B02_FETCH_SIGNER' }

  # Materialização da fonte e do novo stage somente após validar os pins;
  # nenhuma escrita no checkout, na chave privada nem no bundle histórico.
  @'
import sys, pathlib, hashlib, subprocess, json
repo,commit,script,blob,old,new,dh = sys.argv[1:]
sha=lambda b:hashlib.sha256(b).hexdigest()
gblob=lambda b:hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
p=subprocess.run(['git','-C',repo,'show',commit+':tools/b02_documentary_signer_v2.py'],capture_output=True,check=True)
assert gblob(p.stdout)==blob,'STOP_CODE_BLOB'
s=pathlib.Path(script)
if s.exists(): assert s.read_bytes()==p.stdout,'STOP_SIGNER_LOCAL_DIVERGENTE'
else: s.write_bytes(p.stdout)
a=pathlib.Path(old); dest=pathlib.Path(new)
assert a.is_dir() and not a.is_symlink(),'STOP_CANONICAL_STAGE'
m=(a/'manifest.json').read_bytes()
assert sha(m)=='99d1a424015fc03a5ece71e84341eee748fd0b2fc1bebd238f9df2ede253a6c1','STOP_MANIFEST'
rows=json.loads(m)['entries']
assert len(rows)==7,'STOP_PROOF_COUNT'
items={}
for row in rows:
 name=row['path']; f=a/name
 assert f.is_file() and not f.is_symlink(),'STOP_MISSING_OR_SYMLINK:'+name
 b=f.read_bytes()
 assert sha(b)==row['sha256'] and len(b)==row['size'],'STOP_SEVEN_HASH:'+name
 items[name]=b
src=pathlib.Path.home()/'Downloads'/'SOLVERIS_B02_decision_CANDIDATO_NAO_ASSINADO_20261103_1500UTC.json'
old_dec=src.read_bytes()
assert sha(old_dec)=='d6a204a8b2635a7fd80aadc7fb59206836afddc8fda1cf3ed23eb0b9a2dfed94','STOP_SOURCE_DECISION'
d=json.loads(old_dec)
d.update(schema_version=2,profile='FOUNDER_SIGNED_REVIEW_BUNDLE_B02_V2',
 continuity_adoption_sha256='d0cd1765ea2ef4870a530f8e5367cdde8550b5a60a3a70cb294f9d80678f7fa8',
 signer_policy_id='SOLVERIS-B02-G4-DOCUMENTARY-LOCAL-SIGNER-V2',
 valid_from='2026-11-03T18:00:00+00:00',valid_until='2026-11-04T18:00:00+00:00')
db=json.dumps(d,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
assert sha(db)==dh,'STOP_NEW_DECISION_HASH'
if dest.exists():
 for name,b in {**items,'manifest.json':m,'decision.json':db}.items():
  assert (dest/name).read_bytes()==b,'STOP_STAGE_EXISTENTE_DIVERGENTE:'+name
else:
 dest.mkdir()
 for name,b in {**items,'manifest.json':m,'decision.json':db}.items():
  (dest/name).write_bytes(b)
print('B02_SIGNER_V2_SIGNING_STAGE_PINNED')
'@ | python - $repo $commit $signer $codeblob $original $bundle $decision
  if ($LASTEXITCODE -ne 0) { throw 'STOP_B02_PREPARE_STAGE' }

  $signerArgs = @('--repo', $repo, '--legacy', $legacy, '--bundle', $bundle,
    '--public', $public, '--fingerprint', $fingerprint,
    '--approved-decision-sha256', $decision,
    '--continuity-adoption', $adoption,
    '--signer-authority', $AutoridadeAdotadaJson,
    '--signer-review', $ParecerJson,
    '--approved-signer-authority-sha256', $Sha256AutoridadeAdotada,
    '--reviewed-signer-git-blob', $codeblob)
  python $signer preflight @signerArgs
  if ($LASTEXITCODE -ne 0) { throw 'STOP_B02_PREFLIGHT_NO_SIGN' }
  python $signer sign @signerArgs --private $private --authorization $AutorizacaoExataTxt --authorization-sha256 $Sha256AutorizacaoExata
  if ($LASTEXITCODE -ne 0) { throw 'STOP_B02_SIGNATURE_NO_VERIFIED' }
  python $signer verify @signerArgs
  if ($LASTEXITCODE -ne 0) { throw 'STOP_B02_VERIFY' }
  'B02_SIGNER_V2_SIGNATURE_VERIFIED_NO_ROOT_NO_G5'
}