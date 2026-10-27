"""
Aplica o diff minimo de compatibilidade SQLite para as constraints
B02 que usam '~' (regex match, so Postgres) em app/database.py.

Uso:
    python aplicar_patch_b02.py

Nao cola nada na consola. Corre como ficheiro, a partir da raiz do
repo (C:\\dev\\saas-fiscal-demo-a1). Falha com SystemExit explicito
se qualquer ancora nao for encontrada EXACTAMENTE uma vez -- nao
escreve nada no ficheiro nesse caso.
"""
from pathlib import Path

ALVO = Path("app/database.py")

ANCORA_IMPORT = (
    "from sqlalchemy import create_engine, event, inspect, text\n"
    "from sqlalchemy.orm import declarative_base, sessionmaker\n"
)

NOVO_IMPORT = (
    "from sqlalchemy import create_engine, event, inspect, text\n"
    "from sqlalchemy import CheckConstraint\n"
    "from sqlalchemy.schema import CreateTable\n"
    "from sqlalchemy.ext.compiler import compiles\n"
    "from sqlalchemy.orm import declarative_base, sessionmaker\n"
)

ANCORA_FUNC = "def ensure_sqlite_schema_compat() -> None:\n"

NOMES_CONSTRAINTS_REGEX = {
    "ck_b02_02", "ck_b02_03", "ck_b02_04", "ck_b02_05", "ck_b02_06",
    "ck_b02_12", "ck_b02_13", "ck_b02_14", "ck_b02_15", "ck_b02_16",
    "ck_b02_17", "ck_b02_18",
    "ck_b02_22", "ck_b02_23", "ck_b02_24", "ck_b02_25", "ck_b02_26",
}

NOVA_FUNCAO = '''@compiles(CreateTable, "sqlite")
def _skip_b02_regex_checks_on_sqlite(create, compiler, **kw):
    """
    SQLite nao suporta o operador '~' (regex match) usado nas
    CheckConstraints B02 (validacao de hash/txid). Em Postgres real
    (producao/Alembic) estas constraints continuam intactas -- este
    override so dispara para o dialect sqlite, usado nos testes
    locais. Scope restrito por nome, nao por qualquer '~' futuro.
    """
    nomes_regex = ''' + repr(NOMES_CONSTRAINTS_REGEX) + '''
    for constraint in list(create.element.constraints):
        if isinstance(constraint, CheckConstraint) and constraint.name in nomes_regex:
            create.element.constraints.discard(constraint)
    return compiler.visit_create_table(create, **kw)


'''


def aplicar() -> None:
    if not ALVO.exists():
        raise SystemExit(f"STOP: ficheiro nao encontrado: {ALVO.resolve()}")

    texto = ALVO.read_text(encoding="utf-8")

    n_import = texto.count(ANCORA_IMPORT)
    if n_import != 1:
        raise SystemExit(
            f"STOP: ancora de import encontrada {n_import}x (esperado 1). "
            "Nada foi escrito."
        )

    n_func = texto.count(ANCORA_FUNC)
    if n_func != 1:
        raise SystemExit(
            f"STOP: ancora da funcao encontrada {n_func}x (esperado 1). "
            "Nada foi escrito."
        )

    if "_skip_b02_regex_checks_on_sqlite" in texto:
        raise SystemExit(
            "STOP: patch ja parece aplicado (funcao ja existe no ficheiro). "
            "Nada foi escrito."
        )

    texto_novo = texto.replace(ANCORA_IMPORT, NOVO_IMPORT, 1)
    texto_novo = texto_novo.replace(ANCORA_FUNC, NOVA_FUNCAO + ANCORA_FUNC, 1)

    # LF explicito, UTF-8 sem BOM, consistente com a convencao do repo
    with open(ALVO, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto_novo)

    print(f"OK: patch aplicado em {ALVO.resolve()}")
    print(f"OK: {len(NOMES_CONSTRAINTS_REGEX)} constraints marcadas para skip em SQLite")


if __name__ == "__main__":
    aplicar()
