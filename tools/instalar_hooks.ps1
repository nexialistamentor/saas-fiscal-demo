# instalar_hooks.ps1
# Copia githooks/pre-commit (versionado) para o hooks/ do git-common-dir
# (nao versionado -- cada clone/worktree precisa de rodar isto uma vez).
# Hooks sao PARTILHADOS entre worktrees -- vivem no git-common-dir, nao no
# git-dir privado de cada worktree (confirmado: este repo e um worktree de
# C:\dev\saas-fiscal-demo, git-common-dir real e C:\dev\saas-fiscal-demo\.git).
# Rodar a partir da raiz do repo (ou de qualquer worktree dele):
#   .\tools\instalar_hooks.ps1

$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) {
    Write-Error "Nao foi possivel encontrar a raiz do repositorio git."
    exit 1
}

$commonDir = (git rev-parse --git-common-dir)
if (-not [System.IO.Path]::IsPathRooted($commonDir)) {
    # git-common-dir pode vir relativo ao cwd -- resolver para absoluto
    $commonDir = (Resolve-Path (Join-Path $repoRoot $commonDir)).Path
}

$origem = Join-Path $repoRoot "githooks\pre-commit"
$hooksDir = Join-Path $commonDir "hooks"
$destino = Join-Path $hooksDir "pre-commit"

if (-not (Test-Path $origem)) {
    Write-Error "Nao encontrado: $origem -- rode este script a partir da raiz do repo."
    exit 1
}

New-Item -ItemType Directory -Force -Path $hooksDir | Out-Null
Copy-Item $origem $destino -Force

# Git for Windows usa sh.exe (MSYS) para correr hooks sem extensao; nao
# precisa de bit de execucao no NTFS, mas definir nao faz mal nalguns
# ambientes WSL/Linux que montem o mesmo repo.
try {
    git update-index --chmod=+x "githooks/pre-commit" 2>$null
} catch {
    # nao critico -- Windows nao usa bits de execucao POSIX
}

Write-Host "Hook instalado em: $destino"
Write-Host "Teste com um commit normal -- o hook roda check_duplicacao.py automaticamente."
