"""
Opcao B: para SQLite, descarta TODAS as CheckConstraints de tabela
em create_all -- nao so as que contem marcadores Postgres conhecidos.
Acaba o ciclo de "mais uma funcao Postgres apareceu" de uma vez.
Postgres real/Alembic continua a aplicar todas as CHECK normalmente
-- este override so dispara para o dialect sqlite.

Uso:
    python aplicar_patch_b02_v3.py
"""
from pathlib import Path

ALVO = Path("app/database.py")

MARCADOR_INICIO = '@compiles(CreateTable, "sqlite")\n'
MARCADOR_FIM = "return compiler.visit_create_table(create, **kw)\n"

NOVA_FUNCAO = '''@compiles(CreateTable, "sqlite")
def _skip_all_check_constraints_on_sqlite(create, compiler, **kw):
    """
    SQLite nao suporta varias funcoes/operadores Postgres-nativos
    usados nas CheckConstraints B02 (~ regex, jsonb_typeof, e
    potencialmente outras no futuro). Em vez de enumerar marcadores
    um a um (ja tentado duas vezes, sempre incompleto), descarta
    TODAS as CheckConstraints de tabela quando a criacao e para
    sqlite. Postgres real/Alembic continua a aplicar todas as CHECK
    normalmente -- este override so dispara para o dialect sqlite,
    usado nos testes locais. Validacao de formato (hash/txid/json)
    fica exclusivamente a cargo do Postgres real a partir daqui.
    """
    for constraint in list(create.element.constraints):
        if isinstance(constraint, CheckConstraint):
            create.element.constraints.discard(constraint)
    return compiler.visit_create_table(create, **kw)
'''


def aplicar() -> None:
    if not ALVO.exists():
        raise SystemExit(f"STOP: ficheiro nao encontrado: {ALVO.resolve()}")

    texto = ALVO.read_text(encoding="utf-8")

    n_inicio = texto.count(MARCADOR_INICIO)
    if n_inicio != 1:
        raise SystemExit(
            f"STOP: marcador de inicio encontrado {n_inicio}x (esperado 1). "
            "Nada foi escrito."
        )

    idx_inicio = texto.find(MARCADOR_INICIO)
    idx_fim = texto.find(MARCADOR_FIM, idx_inicio)
    if idx_fim == -1:
        raise SystemExit("STOP: marcador de fim nao encontrado apos o inicio. Nada foi escrito.")
    idx_fim += len(MARCADOR_FIM)

    texto_novo = texto[:idx_inicio] + NOVA_FUNCAO + texto[idx_fim:]

    with open(ALVO, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto_novo)

    print(f"OK: opcao B aplicada (todas as CHECK descartadas em sqlite) em {ALVO.resolve()}")


if __name__ == "__main__":
    aplicar()
