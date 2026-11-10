#!/usr/bin/env python3
"""B03: auditoria estática antidualidade, sem rede/SQL/import do app/escrita."""
from __future__ import annotations
import argparse, ast, re, subprocess, sys
from pathlib import Path
from collections import defaultdict

OWNERS = {
    "calculo_st": ("app/motor_fiscal.py", "MotorFiscal"),
    "comparacao_numerica": ("app/services/tax_consistency/tax_consistency_engine.py", "TaxConsistencyEngine"),
    "resolucao_mva": ("app/services/tabela_normativa_service.py", "buscar_mva"),
    "resolucao_aliquota": ("app/services/fiscal_utils.py", "resolver_aliquota_e_mva"),
    "confronto_g12": ("app/services/enterprise_g12_st_item_reconciliation.py", "confrontar_st_por_item_g12"),
    "escopo_g14": ("app/services/enterprise_g14_operational_normative_scope.py", "cotejar_enquadramento_normativo_operacao_g14"),
    "proveniencia_c5": ("tools/enterprise_g113_c5_parameter_trace.py", "cotejar_rastro_parametros_g113_c5"),
    "proveniencia_c6": ("tools/enterprise_g113_c6_l2_record_provenance.py", "cotejar_registo_l2_g113_c6"),
    "orquestrador_b01": ("app/services/registro_analise_service.py", "executar_circuito_enterprise_01"),
}
KEYWORDS = re.compile(r"mva|icms|compar|divergen|jurisd|st_|reconcil|normativ|tax_consistency|fiscal|g1[2345678]|c[34567]_|xml", re.I)
SUFFIX = re.compile(r"(?:_v\d+|_v\d+_\w+|_novo|_alternativo|_backup|_copy)$", re.I)

def git(root: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=false", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
    if p.returncode:
        raise RuntimeError("STOP_GIT_" + args[0] + ": " + p.stderr.strip()[:160])
    return p.stdout

def public_names(src: str) -> set[str]:
    tree = ast.parse(src)
    result = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                result.add(node.name)
    return result

def run(root: Path) -> int:
    root = root.resolve(strict=True)
    actual = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve(strict=True)
    if root != actual:
        raise RuntimeError("STOP_NOT_GIT_ROOT")
    head = git(root, "rev-parse", "HEAD").strip()
    branch = git(root, "branch", "--show-current").strip() or "(detached)"
    dirty = git(root, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
    wt = [s.split(" ",1)[1] for s in git(root,"worktree","list","--porcelain").splitlines() if s.startswith("worktree ")]
    raw = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "app", "tools", "tests")
    names = sorted(set(n for n in raw.split("\x00") if n.endswith(".py")))
    occurrences = defaultdict(list); families = defaultdict(list)
    parsed_sources = {}; warnings = []; relevant = 0
    for rel in names:
        path = root / rel
        if not KEYWORDS.search(rel) or path.is_symlink() or not path.is_file():
            continue
        relevant += 1
        try:
            if path.stat().st_size > 2_000_000:
                warnings.append(rel + ":TOO_LARGE"); continue
            src = path.read_text(encoding="utf-8-sig")
            parsed_sources[rel] = src
            for name in public_names(src):
                occurrences[name].append(rel)
            families[SUFFIX.sub("",path.stem)].append(rel)
        except (OSError, UnicodeError, SyntaxError) as ex:
            warnings.append(rel + ":" + type(ex).__name__)
    duplicates = [(n,v) for n,v in sorted(occurrences.items()) if len(v)>1]
    repeats = [(n,v) for n,v in sorted(families.items()) if len(v)>1]
    print("B03_ANTIDUP_READONLY_COMPLETE")
    print("GIT_TOP=" + str(root))
    print("HEAD=" + head)
    print("BRANCH=" + branch)
    print("DIRTY_ENTRIES=" + str(len(dirty)))
    print("WORKTREES=" + str(len(wt)))
    for x in wt[:20]:
        print("WORKTREE=" + x)
    print("RELEVANT_PY_FILES=" + str(relevant))
    for label,(rel,name) in OWNERS.items():
        try:
            src=parsed_sources.get(rel) or (root/rel).read_text(encoding="utf-8-sig")
            present=name in public_names(src)
        except (OSError,UnicodeError,SyntaxError):
            present=False
        print("OWNER_" + label + "=" + ("FOUND" if present else "MISSING") + ":" + rel)
    print("PUBLIC_NAME_COLLISIONS=" + str(len(duplicates)))
    for n,files in duplicates[:20]:
        print("  " + n + " => " + ", ".join(files[:5]))
    print("SIMILAR_FILENAME_FAMILIES=" + str(len(repeats)))
    for n,files in repeats[:15]:
        print("  " + n + " => " + ", ".join(files[:5]))
    print("PARSE_WARNINGS=" + str(len(warnings)))
    for x in warnings[:10]:
        print("  " + x)
    print("AUDIT_MEANING=STATIC_CANDIDATES_NOT_PROOF_OF_DUPLICATION_OR_B03_READINESS")
    print("NO_FILES_WRITTEN_NO_SQL_NO_NETWORK_NO_TEST_EXECUTION")
    return 0

def main():
    p=argparse.ArgumentParser()
    p.add_argument("repo",type=Path)
    args=p.parse_args()
    return run(args.repo)

if __name__=="__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as ex:
        print("STOP_B03_AUDIT=" + str(ex),file=sys.stderr)
        sys.exit(2)
