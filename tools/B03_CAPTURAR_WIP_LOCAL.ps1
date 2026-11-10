# SOLVERIS B03 — inventario integral READ-ONLY de Git, WIP e refs locais.
# Substitui o comportamento inseguro anterior (git add -A); NAO cria commits,
# NAO altera index, ficheiros, branches ou worktrees. O JSON vai para LOCALAPPDATA.
# O script NAO afirma capturar fontes fora dos Git repos encontrados.
param(
    [Parameter(Mandatory=$true)][string]$Repository,
    [string[]]$AdditionalRoots = @()
)

$ErrorActionPreference = 'Stop'
function Invoke-B03Git {
    param([string]$RepoPath, [string[]]$GitArgs)
    $result = @(& git.exe -C $RepoPath -c core.quotepath=false @GitArgs)
    if ($LASTEXITCODE -ne 0) {
        throw ('STOP_GIT_' + ($GitArgs -join '_'))
    }
    return $result
}
function GitOne {
    param([string]$RepoPath, [string[]]$GitArgs)
    $values = @(Invoke-B03Git -RepoPath $RepoPath -GitArgs $GitArgs)
    if ($values.Count -eq 0) { return '' }
    return ([string]$values[0]).Trim()
}

$root = GitOne -RepoPath $Repository -GitArgs @('rev-parse','--show-toplevel')
$origin = GitOne -RepoPath $root -GitArgs @('remote','get-url','origin')
if ($origin -notmatch 'nexialistamentor/saas-fiscal-demo(?:\.git)?$') {
    throw 'STOP_WRONG_ORIGIN'
}
$base = Split-Path -Parent $root
$searchRoots = @($base) + @($AdditionalRoots)
$repoCandidates = @($root)
$discoveryIssues = [System.Collections.Generic.List[string]]::new()
foreach($folder in ($searchRoots | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $folder -PathType Container)) {
        $discoveryIssues.Add("ROOT_NOT_FOUND:$folder")
        continue
    }
    # Detectar clones independentes no topo de cada pasta, sem entrar em venvs.
    $dirs = @(Get-ChildItem -LiteralPath $folder -Directory -Force -ErrorAction SilentlyContinue)
    foreach($d in $dirs) {
        if (Test-Path -LiteralPath (Join-Path $d.FullName '.git')) {
            $repoCandidates += $d.FullName
        }
    }
}
$worktrees = [System.Collections.Generic.List[string]]::new()
$seenRepos = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach($candidate in ($repoCandidates | Select-Object -Unique)) {
    try {
        $foundOrigin = GitOne -RepoPath $candidate -GitArgs @('remote','get-url','origin')
        if ($foundOrigin -notmatch 'nexialistamentor/saas-fiscal-demo(?:\.git)?$') { continue }
        $top = GitOne -RepoPath $candidate -GitArgs @('rev-parse','--show-toplevel')
        if (-not $seenRepos.Add($top)) { continue }
        $rows = @(Invoke-B03Git -RepoPath $top -GitArgs @('worktree','list','--porcelain'))
        foreach($line in $rows) {
            $line = [string]$line
            if ($line.StartsWith('worktree ')) { $worktrees.Add($line.Substring(9)) }
        }
    } catch {
        $discoveryIssues.Add('DISCOVERY_FAILED:' + $candidate)
    }
}
$destination = Join-Path $env:LOCALAPPDATA 'SOLVERIS\B03'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$records = [System.Collections.Generic.List[object]]::new()
$uniqueWorktrees = @($worktrees | Sort-Object -Unique)
foreach($wt in $uniqueWorktrees) {
    $current = [ordered]@{
        worktree=$wt; head=$null; branch=$null; status='UNREAD';
        modified_count=0; ignored_count=0; snapshot_refs=@();
        modified=@(); ignored=@(); warnings=@()
    }
    try {
        $current.head = GitOne -RepoPath $wt -GitArgs @('rev-parse','HEAD')
        $current.branch = GitOne -RepoPath $wt -GitArgs @('branch','--show-current')
        $porcelain = @(Invoke-B03Git -RepoPath $wt -GitArgs @('status','--porcelain=v1','--untracked-files=all'))
        $ignored = @(Invoke-B03Git -RepoPath $wt -GitArgs @('ls-files','--others','--ignored','--exclude-standard','--directory'))
        $snapshots = @(Invoke-B03Git -RepoPath $wt -GitArgs @(
            'for-each-ref','--format=%(refname:short)','refs/heads/b03/wip-local-'))
        $entries = [System.Collections.Generic.List[object]]::new()
        foreach($entry in $porcelain) {
            $line = [string]$entry
            if ($line.Length -lt 4) { continue }
            $statusCode = $line.Substring(0,2)
            $relative = $line.Substring(3)
            $resolved = Join-Path $wt $relative
            $category = 'SOURCE_OR_ARTIFACT'
            if ($relative -match '(?i)(^|/|\\)(venv\d*|\.venv[^/\\]*|node_modules|\.pytest_cache|__pycache__|dist|build)(/|\\|$)') {
                $category = 'ENVIRONMENT_OR_BUILD'
            } elseif ($relative -match '(?i)(\.env(?:\.[^/\\]*)?$|\.(pem|p12|pfx|key|db|sqlite|sqlite3|zip|7z|tar|gz)$|(^|[/\\])(?:secrets|credentials|tokens)[^/\\]*$)') {
                $category = 'SENSITIVE_OR_BINARY_REVIEW'
            }
            $size=$null
            $sha=$null
            if (Test-Path -LiteralPath $resolved -PathType Leaf) {
                $size=(Get-Item -LiteralPath $resolved -Force).Length
                if ($category -eq 'SOURCE_OR_ARTIFACT' -and $size -le 10000000) {
                    try { $sha=(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant() }
                    catch { $category='HASH_UNREADABLE' }
                }
            }
            $entries.Add([pscustomobject]@{git_status=$statusCode;path=$relative;category=$category;bytes=$size;sha256=$sha})
        }
        $current.modified = @($entries.ToArray())
        $current.modified_count = $entries.Count
        $current.ignored = @($ignored | ForEach-Object { [string]$_ })
        $current.ignored_count = $ignored.Count
        $current.snapshot_refs = @($snapshots | ForEach-Object { [string]$_ })
        $current.status = if ($entries.Count -eq 0 -and $ignored.Count -eq 0) {'CLEAN_OBSERVED'} else {'INVENTORIED_NOT_FULLY_BACKED_UP'}
    } catch {
        $current.status = 'INCOMPLETE_ERROR'
        $current.warnings = @($_.Exception.Message)
    }
    $records.Add([pscustomobject]$current)
    Write-Output ('B03_INVENTORY=' + $current.status +
        ' WIP=' + $current.modified_count +
        ' IGNORED=' + $current.ignored_count +
        ' SNAPSHOT_REFS=' + @($current.snapshot_refs).Count +
        ' WORKTREE=' + $wt)
}
$manifest = Join-Path $destination ('B03_INVENTARIO_COMPLETO_' + $stamp + '.json')
[ordered]@{
    schema='SOLVERIS_B03_WIP_READONLY_INVENTORY_V2'
    produced_at_utc=$stamp
    git_origin=$origin
    roots_scanned=@($searchRoots | Select-Object -Unique)
    discovery_warnings=@($discoveryIssues.ToArray())
    outside_search_roots_not_scanned=$true
    ignored_paths_listed_not_hashed=$true
    local_snapshots_untouched=$true
    no_git_objects_created=$true
    no_remote_push=$true
    worktrees=@($records.ToArray())
} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $manifest -Encoding UTF8
Write-Output ('B03_INVENTARIO_LOCAL=' + $manifest)
Write-Output ('B03_DISCOVERY_WARNINGS=' + $discoveryIssues.Count)
Write-Output 'B03_READ_ONLY_DONE_NO_GIT_ADD_NO_COMMIT_NO_PUSH'
