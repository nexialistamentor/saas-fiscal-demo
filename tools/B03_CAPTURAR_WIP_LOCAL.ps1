# SOLVERIS B03 — snapshot Git LOCAL de ficheiros ainda não commitados.
# Cria branch WIP em cada worktree SUJEITO a verificação sensível.
# Não altera o working tree, HEAD, index original nem faz push.
param([Parameter(Mandatory=$true)][string]$Repository)

$ErrorActionPreference = "Stop"
function Git([string]$where, [string[]]$args) {
    $r = & git -C $where -c core.quotepath=false @args
    if ($LASTEXITCODE -ne 0) { throw ("STOP_GIT_" + ($args -join "_")) }
    return $r
}
$root = (Git $Repository @("rev-parse","--show-toplevel") | Select-Object -First 1).Trim()
$remote = (Git $root @("remote","get-url","origin") | Select-Object -First 1).Trim()
if ($remote -notmatch 'nexialistamentor/saas-fiscal-demo(?:\.git)?$') {
    throw "STOP_WRONG_ORIGIN"
}
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$directory = Join-Path $env:LOCALAPPDATA "SOLVERIS\B03"
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$lines = @(Git $root @("worktree","list","--porcelain"))
$worktrees = @($lines | Where-Object { $_ -match '^worktree ' } |
    ForEach-Object { $_.Substring(9) })
$records = @()
$counter=0
foreach ($w in $worktrees) {
    $counter++
    $head = (Git $w @("rev-parse","HEAD") | Select-Object -First 1).Trim()
    $changes = @(
        @(Git $w @("diff","--name-only","HEAD"))
        @(Git $w @("ls-files","--others","--exclude-standard"))
    ) | ForEach-Object { $_ } | Where-Object { $_ } | Sort-Object -Unique
    $entries=@()
    $alerts=@()
    $total=0L
    foreach($relative in $changes) {
        $full=Join-Path $w $relative
        $present=Test-Path -LiteralPath $full -PathType Leaf
        $size=0L
        $sha=$null
        if($present) {
            $info=Get-Item -LiteralPath $full -Force
            if($info.LinkType) { $alerts += "SYMLINK:$relative" }
            $size=$info.Length
            $total += $size
            if($size -gt 12000000) { $alerts += "LARGE:$relative" }
            else { $sha=(Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant() }
        }
        $normalized=$relative.Replace('\','/')
        $privatePattern='(?i)(^|/)(\.env(\..*)?|\.ssh|\.aws|\.venv|node_modules|__pycache__)(/|$)|\.(pem|key|pfx|p12|p8|keystore|sqlite|sqlite3|db|zip|7z|tar|gz|pdf)$|(^|/)(credentials|secrets|tokens)\.(json|ya?ml|toml|txt)$'
        if($normalized -match $privatePattern) { $alerts += "SENSITIVE_PATH:$relative" }
        $textExtensions=@(".py",".md",".json",".js",".jsx",".ts",".tsx",".css",".sql",".ps1",".txt",".toml",".yaml",".yml",".html",".sh",".cfg",".ini")
        if($present -and $size -lt 2000000 -and [IO.Path]::GetExtension($full).ToLowerInvariant() -in $textExtensions) {
            $txt = [IO.File]::ReadAllText($full)
            if($txt -match '-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----' -or
               $txt -match '(?im)^\s*(?:DATABASE_URL|ACCESS_TOKEN|API_KEY|SECRET_KEY|PASSWORD|MP_ACCESS_TOKEN)\s*[:=]\s*["'']?[a-z0-9_\-\.]{12,}') {
                $alerts += "POSSIBLE_SECRET_CONTENT:$relative"
            }
        }
        $entries += [pscustomobject]@{path=$relative;exists=$present;size=$size;sha256=$sha}
    }
    $saved=$null; $commit=$null; $state="CLEAN"
    if($changes.Count -gt 0) {
        $state="NOT_SNAPSHOTTED"
        if($total -gt 80000000) { $alerts+="WORKTREE_TOTAL_TOO_LARGE" }
        if($alerts.Count -eq 0) {
            $tempIndex=Join-Path $directory ("index_"+[guid]::NewGuid().ToString("N"))
            $originalIndex=$env:GIT_INDEX_FILE
            try {
                $env:GIT_INDEX_FILE=$tempIndex
                Git $w @("read-tree","HEAD") | Out-Null
                Git $w @("add","-A","--",":/") | Out-Null
                $tree=(Git $w @("write-tree") | Select-Object -First 1).Trim()
                $commit=(Git $w @("commit-tree",$tree,"-p",$head,"-m","snapshot(b03): local uncommitted WIP, no remote push") | Select-Object -First 1).Trim()
                $saved="b03/wip-local-$stamp-$counter"
                Git $w @("update-ref","refs/heads/$saved",$commit) | Out-Null
                $state="SNAPSHOT_LOCAL_GIT_ONLY"
            } catch {
                $state="SNAPSHOT_FAILED"
                $alerts += $_.Exception.Message
            } finally {
                $env:GIT_INDEX_FILE=$originalIndex
                if(Test-Path -LiteralPath $tempIndex) { Remove-Item -LiteralPath $tempIndex -Force }
                if(Test-Path -LiteralPath ($tempIndex+".lock")) { Remove-Item -LiteralPath ($tempIndex+".lock") -Force }
            }
        } else {
            $state="STOP_SENSITIVE_OR_LARGE_REVIEW_REQUIRED"
        }
    }
    $records += [pscustomobject]@{
       worktree=$w;head=$head;state=$state;dirty_count=$changes.Count;
       snapshot_branch=$saved;snapshot_commit=$commit;warnings=$alerts;files=$entries
    }
    Write-Output ("B03_WIP="+$state+" COUNT="+$changes.Count+" WORKTREE="+$w)
    if($saved) { Write-Output ("B03_WIP_GIT_BRANCH="+$saved) }
    if($alerts.Count) { Write-Output ("B03_WIP_WARNING_COUNT="+$alerts.Count) }
}
$manifest=Join-Path $directory ("B03_LOCAL_WORKTREES_"+$stamp+".json")
[pscustomobject]@{
    schema="SOLVERIS_B03_LOCAL_WIP_INVENTORY_V1"
    produced_at_utc=$stamp; repository=$root; origin=$remote
    pushed_to_github=$false; contains_source_bytes=$false
    scope="TRACKED_MODIFICATIONS_AND_UNTRACKED_NONIGNORED_WORKTREE_FILES"
    note="WIP content (where safe) persisted in local Git snapshot branches; never auto-push."
    worktrees=$records
} | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $manifest -Encoding UTF8
Write-Output ("B03_INVENTARIO_LOCAL="+$manifest)
Write-Output "GIT_WORKTREE_AND_ORIGINAL_INDEX_PRESERVED; NO_REMOTE_PUSH"
