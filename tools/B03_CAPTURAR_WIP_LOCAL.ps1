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
        modified_count=0; ignored_count=0; ignored_source_count=0; snapshot_refs=@(); snapshot_inspection=@();
        modified=@(); ignored=@(); ignored_source_candidates=@(); warnings=@()
    }
    try {
        $current.head = GitOne -RepoPath $wt -GitArgs @('rev-parse','HEAD')
        $current.branch = GitOne -RepoPath $wt -GitArgs @('branch','--show-current')
        $porcelain = @(Invoke-B03Git -RepoPath $wt -GitArgs @('status','--porcelain=v1','--untracked-files=all'))
        $ignored = @(Invoke-B03Git -RepoPath $wt -GitArgs @('ls-files','--others','--ignored','--exclude-standard','--directory'))
        # Auditar fontes potencialmente ignoradas, excluindo dependencias/cache.
        # Somente NOMES: nao inclui nem publica o conteudo destes ficheiros.
        $ignoredCode = @(Invoke-B03Git -RepoPath $wt -GitArgs @(
            'ls-files','--others','--ignored','--exclude-standard','--',
            'app','tools','tests','docs','migrations','scripts',
            'frontend-dashboard/src','native') | Where-Object {
                $_ -match '(?i)\.(?:py|js|jsx|ts|tsx|sql|md|json|toml|ps1|yaml|yml)$' -and
                $_ -notmatch '(?i)(^|/)(?:__pycache__|\.pytest_cache|\.venv[^/]*|venv\d*|node_modules|dist|build)(/|$)'
            } | Sort-Object -Unique)
        # Git for-each-ref trata prefixo parcial do último componente como NÃO match.
        # Ler refs/heads/b03 e filtrar pelo nome completo do snapshot.
        $snapshots = @(Invoke-B03Git -RepoPath $wt -GitArgs @(
            'for-each-ref','--format=%(refname:short)','refs/heads/b03') |
            Where-Object { [string]$_ -like 'b03/wip-local-*' })
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
        $current.ignored_source_candidates = @($ignoredCode)
        $current.ignored_source_count = $ignoredCode.Count
        $current.snapshot_refs = @($snapshots | ForEach-Object { [string]$_ })
        $proofs = [System.Collections.Generic.List[object]]::new()
        foreach($localRef in $snapshots) {
            $name=[string]$localRef
            try {
                $changed = @(Invoke-B03Git -RepoPath $wt -GitArgs @(
                    'diff-tree','--name-only','-r',($name+'^'),$name))
                $envFiles = @($changed | Where-Object {
                    $_ -match '(?i)(^|/)(venv\d*|\.venv[^/]*|node_modules|__pycache__|\.pytest_cache)(/|$)'
                })
                $sensitiveFiles = @($changed | Where-Object {
                    $_ -match '(?i)(\.env(?:\..*)?$|\.(pem|pfx|p12|key|sqlite|db)$|(^|/)(credentials|secrets|tokens)[^/]*$)'
                })
                $proofs.Add([pscustomobject]@{
                    ref=$name; changed_count=$changed.Count;
                    environment_files=$envFiles.Count; sensitive_named_files=$sensitiveFiles.Count;
                    needs_manual_content_review=$true
                })
            } catch {
                $proofs.Add([pscustomobject]@{
                    ref=$name;status='INSPECTION_FAILED';needs_manual_content_review=$true
                })
            }
        }
        $current.snapshot_inspection = @($proofs.ToArray())
        $current.status = if ($entries.Count -eq 0 -and $ignored.Count -eq 0) {'CLEAN_OBSERVED'} else {'INVENTORIED_NOT_FULLY_BACKED_UP'}
    } catch {
        $current.status = 'INCOMPLETE_ERROR'
        $current.warnings = @($_.Exception.Message)
    }
    $records.Add([pscustomobject]$current)
    Write-Output ('B03_INVENTORY=' + $current.status +
        ' WIP=' + $current.modified_count +
        ' IGNORED=' + $current.ignored_count +
        ' IGNORED_SOURCE_CANDIDATES=' + $current.ignored_source_count +
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
$all = @($records.ToArray())
$totalWip = 0
$totalIgnored = 0
$totalIgnoredCode = 0
foreach($entry in $all) {
    $totalWip += [int]$entry.modified_count
    $totalIgnored += [int]$entry.ignored_count
    $totalIgnoredCode += [int]$entry.ignored_source_count
}
# Snapshot refs podem repetir entre worktrees que partilham o mesmo git-dir.
$uniqueRefs = @($all | ForEach-Object { $_.snapshot_refs } |
    Where-Object { $_ } | Sort-Object -Unique)
Write-Output ('B03_RESUMO_WORKTREES=' + $all.Count +
    ' WIP=' + $totalWip + ' IGNORED=' + $totalIgnored +
    ' IGNORED_SOURCE_CANDIDATES=' + $totalIgnoredCode +
    ' SNAPSHOT_REF_NAMES_UNIQUE=' + $uniqueRefs.Count)
Write-Output ('B03_INVENTARIO_LOCAL=' + $manifest)
Write-Output ('B03_DISCOVERY_WARNINGS=' + $discoveryIssues.Count)
Write-Output 'B03_READ_ONLY_DONE_NO_GIT_ADD_NO_COMMIT_NO_PUSH'
