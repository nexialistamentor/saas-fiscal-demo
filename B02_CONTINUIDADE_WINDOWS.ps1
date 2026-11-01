# SOLVERIS B02 — comandos locais limitados aos antecedentes ainda abertos.
# Nao instala 0064/0065, nao cria autoridade, nao repete G4/R4/C3/testes.
# Executar no Windows PowerShell com a .venv-release ativa.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('objetos-revisao','receber-pareceres','elegibilidade-chave','bundle-assinado','compilar-nativo','item-r6')]
    [string]$Etapa,
    [string]$Repositorio = 'C:\dev\solveris-b02-g5-v5-publicacao',
    [string]$ChavePublicaDer,
    [string]$ParecerA2,
    [string]$ParecerG5,
    [string]$PastaBundle,
    [string]$PoliticaV3Final,
    [string]$HeaderNativo,
    [string]$ElfSaida,
    [string]$XmlNFe,
    [int]$IndiceItem = 1
)
$ErrorActionPreference='Stop'
$branch='candidate/g5-v5-publicacao-local'
$repoOrigin='github.com[:/]nexialistamentor/saas-fiscal-demo(\.git)?$'
$headBase='0605bdc518c0bc70a249619875c5f5d3551124e7'
function Parar([string]$reason) { throw "STOP_B02_$reason" }
function Pinned([string]$path,[string]$expected) {
    if(-not (Test-Path -LiteralPath $path -PathType Leaf)){Parar "FICHEIRO_AUSENTE:$path"}
    $actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if($actual -cne $expected){Parar "HASH_DIVERGENTE:$path`:$actual"}
    return $actual
}
if(-not (Test-Path -LiteralPath $Repositorio -PathType Container)){Parar 'CHECKOUT_INEXISTENTE'}
Push-Location -LiteralPath $Repositorio
try {
    $b=(& git branch --show-current).Trim();if($LASTEXITCODE -ne 0 -or $b -cne $branch){Parar 'CHECKOUT_BRANCH'}
    $origin=(& git remote get-url origin).Trim();if($LASTEXITCODE -ne 0 -or $origin -notmatch $repoOrigin){Parar 'CHECKOUT_ORIGIN'}
    & git merge-base --is-ancestor $headBase HEAD
    if($LASTEXITCODE -ne 0){Parar 'CHECKOUT_SEM_ANCESTRAL_PINADO'}
    if((@(& git status --porcelain --untracked-files=no)).Count -gt 0){Parar 'ARVORE_RASTREADA_MODIFICADA'}
    switch($Etapa) {
        'objetos-revisao' {
            [void](Pinned 'evidence/b02/rcv31/a2/B02_RCV31_R3_DELTA4_V3_A2_SNAPSHOT_V4.patch' 'bfd8b397bb245923a7cff10b0b1c06480bef29aa8e2c707691bcc992c5f8ce7e')
            [void](Pinned 'POLICY_G5_CANDIDATO_SUCESSOR_V3_PARA_REVISAO.json' '32068cadf7297fb5958af25650899abffc667c17f3508f9261a165b8dfbd5fc7')
            Write-Output 'B02_OBJECTOS_REVISOR_A2_V4_E_G5_V3_EXATOS_PASS; apenas material para atos proprios'
        }
        'receber-pareceres' {
            if(-not $ParecerA2 -or -not $ParecerG5){Parar 'DOIS_PARECERES_PROPRIOS_EXIGIDOS'}
            if(-not (Test-Path -LiteralPath $ParecerA2 -PathType Leaf) -or -not (Test-Path -LiteralPath $ParecerG5 -PathType Leaf)){Parar 'PARECER_AUSENTE'}
            $h1=(Get-FileHash -LiteralPath $ParecerA2 -Algorithm SHA256).Hash.ToLowerInvariant()
            $h2=(Get-FileHash -LiteralPath $ParecerG5 -Algorithm SHA256).Hash.ToLowerInvariant()
            if($h1 -ceq $h2){Parar 'PARECERES_NAO_SEGREGADOS'}
            Write-Output "A2_V4_DOCUMENTO_RECEBIDO_NAO_AUTENTICADO_SHA256=$h1"
            Write-Output "G5_V3_DOCUMENTO_RECEBIDO_NAO_AUTENTICADO_SHA256=$h2"
            Write-Output 'CONFERIR_IDENTIDADES_ACEITACAO_CONFLITOS_E_ASSINATURAS_NO_CANAL_EMISSOR_ANTES_DE_QUALQUER_DECISAO_SQL'
        }
        'elegibilidade-chave' {
            # Localizacao restrita as custodias B02 conhecidas. Ficheiro DER publico
            # OU ROOT.json historico fixado: nao se procuram chaves privadas.
            $pastaAssinatura=Join-Path $env:USERPROFILE 'Downloads\SOLVERIS_B02_ASSINATURA_AUTORIZADA_20261022'
            $pastaIsolada=Join-Path $env:USERPROFILE 'Downloads\B02Trust_ISOLADO_TESTE'
            $pastaInstalada=Join-Path $env:LOCALAPPDATA 'SOLVERIS\B02Trust'
            $fontes=@()
            if($ChavePublicaDer) {
                if(-not (Test-Path -LiteralPath $ChavePublicaDer -PathType Leaf)) {Parar "CHAVE_PUBLICA_INDICADA_NAO_EXISTE:$ChavePublicaDer"}
                $fontes=@($ChavePublicaDer)
            } else {
                foreach($pasta in @($pastaInstalada,$pastaIsolada,$pastaAssinatura)) {
                    if(Test-Path -LiteralPath $pasta -PathType Container) {
                        $fontes+=@(Get-ChildItem -LiteralPath $pasta -Recurse -File -ErrorAction SilentlyContinue |
                            Where-Object { $_.Name -ceq 'ROOT.json' -or $_.Extension -ieq '.der' } |
                            ForEach-Object { $_.FullName })
                    }
                }
                $fontes=@($fontes | Select-Object -Unique)
            }
            if($fontes.Count -eq 0){Parar 'CHAVE_PUBLICA_AUSENTE_NAS_TRES_CUSTODIAS; USAR_-ChavePublicaDer_COM_DER_OU_ROOT_JSON_REAL'}
            $code=@'
import sys, json, hashlib
from pathlib import Path
from cryptography.hazmat.primitives.serialization import load_der_public_key, Encoding, PublicFormat
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
fingerprint='6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c'
root_pin='398e3938b11af5694c65fad4412303681651cb906aa5acfff2ef9c1de6caa4ff'
decision_pin='fc7fe0f239e468b46c3597688f095e758e573fb8deb78dcbc2b6279707df4274'
signature_pin='88d9e61a2a900e5ff82ffbee139cd1906f4106b889ca00dad3400f8cdf17cb3e'
try:
    p=Path(sys.argv[1])
    if p.name=='ROOT.json':
        stored=p.read_bytes()
        if hashlib.sha256(stored).hexdigest()!=root_pin: raise ValueError('ROOT_HISTORICA_NAO_PINADA')
        root=json.loads(stored)
        if root.get('key_fingerprint')!=fingerprint: raise ValueError('ROOT_FINGERPRINT')
        raw=bytes.fromhex(root['public_key_der_hex'])
        # Confirmar assinatura historica quando os dois ficheiros estao juntos.
        decision=p.parent/'BUNDLE_ASSINADO'/'decision.json'
        signature=p.parent/'BUNDLE_ASSINADO'/'signature.bin'
        if decision.is_file() or signature.is_file():
            if not (decision.is_file() and signature.is_file()): raise ValueError('BUNDLE_HISTORICO_INCOMPLETO')
            d=decision.read_bytes();s=signature.read_bytes()
            if hashlib.sha256(d).hexdigest()!=decision_pin or hashlib.sha256(s).hexdigest()!=signature_pin:
                raise ValueError('BUNDLE_HISTORICO_NAO_PINADO')
        else: d=s=None
        origin='ROOT_JSON_HISTORICO_PINADO'
    elif p.suffix.lower()=='.der':
        raw=p.read_bytes(); d=s=None; origin='DER_PUBLICO'
    else: raise ValueError('APENAS_DER_OU_ROOT_JSON')
    if hashlib.sha256(raw).hexdigest()!=fingerprint: raise ValueError('PUBLIC_DER_FINGERPRINT_DIVERGENTE')
    key=load_der_public_key(raw)
    if not isinstance(key,Ed25519PublicKey) or key.public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)!=raw:
        raise ValueError('PUBLIC_DER_NAO_ED25519_CANONICO')
    if d is not None: key.verify(s,d)
    print('B02_CHAVE_PUBLICA_HISTORICA_IDENTIFICADA='+str(p))
    print('B02_PUBLIC_KEY_ED25519_FINGERPRINT_MATCH_'+fingerprint)
    print('FONTE='+origin+'; ASSINATURA_HISTORICA_VERIFICADA='+str(d is not None))
    print('NAO_COMPROVA_CONTROLE_DA_PRIVADA_REVOGACAO_MANDATO_NEM_VIGENCIA_ATUAL')
except Exception:
    sys.exit(3)
'@
            $encontrada=$false
            foreach($fonte in $fontes) {
                $saida=@($code | & python - $fonte)
                if($LASTEXITCODE -eq 0) {
                    $saida | Write-Output
                    $encontrada=$true
                    break
                }
            }
            if(-not $encontrada) {
                Parar 'CHAVE_PUBLICA_PINADA_NAO_LOCALIZADA; USAR_-ChavePublicaDer_COM_FICHEIRO_DER_OU_ROOT_JSON_ORIGINAL'
            }
        }
        'bundle-assinado' {
            if(-not $PastaBundle){Parar 'PASTA_BUNDLE_ASSINADO_EXIGIDA'}
            # Novo bundle != bundle historico. PINS antigos e _base() so aceitam
            # os bytes ja expirados; nao ativar nem alterar esse mecanismo.
            # Este comando so valida o pacote e a assinatura Ed25519 offline.
            if(-not $ChavePublicaDer) {
                $ChavePublicaDer=Join-Path $env:LOCALAPPDATA 'SOLVERIS\B02Trust\fc7fe0f239e468b46c3597688f095e758e573fb8deb78dcbc2b6279707df4274\ROOT.json'
            }
            if(-not (Test-Path -LiteralPath $ChavePublicaDer -PathType Leaf)){
                Parar 'ROOT_PUBLICO_HISTORICO_AUSENTE'
            }
            & python B02_PREPARAR_BUNDLE_SUCESSOR.py --verificar-assinado $PastaBundle --der-publico $ChavePublicaDer
            if($LASTEXITCODE -ne 0){Parar 'BUNDLE_SUCESSOR_ASSINATURA_OU_HASH_DIVERGENTE'}
            Write-Output 'B02_SUCESSOR_OFFLINE_VERIFICADO; SEM_PROVA_DE_MANDATO_REVOGACAO_DEPLOYMENT_OU_ATIVACAO'
        }
        'compilar-nativo' {
            if(-not $PoliticaV3Final -or -not $HeaderNativo -or -not $ElfSaida){Parar 'POLITICA_FINAL_HEADER_SAIDA_EXIGIDOS'}
            # Hash derivado dos bytes CANONICOS do corpo final, nao da candidata antiga.
            $code=@'
import sys, json, hashlib
from pathlib import Path
from app.services.enterprise_b02_founder_review_profile import canonical
b=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))['policy_candidate_body']
r=b['rules']['b02_noncredential']['security']['g5_release']
if (b['policy_id'],b['policy_version'],b['policy_type'])!=('SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE',3,'activation_authority'):raise RuntimeError('STOP_NOT_V3')
if b['exact_references']['adoption_act_sha256'] is None or b['roles']['functional_reviewer'] is None or not b['origin_evidence']['institutional_evidence_bindings'] or not r['capability_root_id'] or not r['actor']:raise RuntimeError('STOP_UNISSUED_V3')
for d in r['documents']:
 if not d['g4']['origin_report_binding'] or d['g4']['outcome'].startswith('AWAITING_') or d['sanitization']['outcome'].startswith('AWAITING_'):raise RuntimeError('STOP_UNVERIFIED_V3_DOCUMENT')
print(hashlib.sha256(canonical(b)).hexdigest())
'@
            $policyHash=@($code | & python - $PoliticaV3Final)
            if($LASTEXITCODE -ne 0 -or $policyHash.Count -ne 1 -or $policyHash[0] -notmatch '^[a-f0-9]{64}$'){Parar 'G5_V3_CORPO_NAO_FINAL'}
            $headerHash=(Get-FileHash -LiteralPath $HeaderNativo -Algorithm SHA256).Hash.ToLowerInvariant()
            & python tools/b02_g5_native_pg1710_isolated_build.py --header $HeaderNativo --header-sha256 $headerHash --policy-hash $policyHash[0] --out $ElfSaida
            if($LASTEXITCODE -ne 0){Parar 'BUILD_NATIVO_NAO_REALIZADO'}
            Write-Output 'B02_NATIVO_APENAS_COMPILADO_ISOLADO; NAO_INSTALADO_NEM_APROVADO'
        }
        'item-r6' {
            if(-not $XmlNFe -or $IndiceItem -lt 1){Parar 'XML_REAL_E_INDICE_EXIGIDOS'}
            $code=@'
import sys,json,hashlib
from pathlib import Path
from app.services.enterprise_g113_c4_fiscal_item_bridge import _xml_item
raw=Path(sys.argv[1]).read_bytes();i=int(sys.argv[2]);o=_xml_item(raw,i)
if (o['ncm'],o['cest'],o['uf'],o['cst'])!=('12119090','2000100','PR','10'):
 raise RuntimeError('STOP_R6_ITEM_NAO_CORRESPONDE_HENNA_C3')
print(json.dumps({'status':'R6_XML_FORNECIDO_ITEM_CANDIDATO_SEM_AUTENTICACAO_OU_AUTORIDADE_FISCAL','indice_item':i,'xml_sha256':hashlib.sha256(raw).hexdigest(),**{k:str(v) for k,v in o.items()}},ensure_ascii=False,sort_keys=True))
'@
            $code | & python - $XmlNFe $IndiceItem
            if($LASTEXITCODE -ne 0){Parar 'XML_NFE_REAL_INCOMPATIVEL'}
        }
    }
} finally { Pop-Location }
