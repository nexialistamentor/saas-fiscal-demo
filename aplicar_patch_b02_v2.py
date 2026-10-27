"""
Corrige o patch v1 (lista de nomes incompleta, por causa de saida
truncada no terminal) para deteccao por CONTEUDO: qualquer
CheckConstraint cujo sqltext contenha ' ~ ' e descartada em SQLite,
independentemente do nome/tabela. So atua no dialect sqlite -- Postgres
real/Alembic fica sempre intacto.

Uso:
    python aplicar_patch_b02_v2.py

Corre como ficheiro, a partir da raiz do repo. Falha com SystemExit
explicito se as ancoras nao forem encontradas -- nao escreve nada
nesse caso.
"""
from pathlib import Path

ALVO = Path("app/database.py")

MARCADOR_INICIO = '@compiles(CreateTable, "sqlite")\n'
MARCADOR_FIM = "return compiler.visit_create_table(create, **kw)\n"

NOVA_FUNCAO = '''@compiles(CreateTable, "sqlite")
def _skip_b02_regex_checks_on_sqlite(create, compiler, **kw):
    """
    SQLite nao suporta o operador '~' (regex match) usado em varias
    CheckConstraints B02 (validacao de hash/txid), espalhadas por
    multiplas tabelas com convencoes de nome diferentes
    (ck_b02_*, ck_b02p_*, etc). Em vez de enumerar nomes -- que ja
    falhou uma vez por lista incompleta -- deteta por CONTEUDO: toda
    CheckConstraint cujo sqltext contenha o literal ' ~ ' e descartada
    neste dialect. So atua para sqlite; Postgres real/Alembic fica
    sempre intacto.
    """
    for constraint in list(create.element.constraints):
        if (
            isinstance(constraint, CheckConstraint)
            and constraint.sqltext is not None
            and " ~ " in str(constraint.sqltext)
        ):
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

    bloco_antigo = texto[idx_inicio:idx_fim]
    if "nomes_regex" not in bloco_antigo:
        raise SystemExit(
            "STOP: o bloco encontrado nao parece a funcao v1 esperada "
            "(nao contem 'nomes_regex'). Nada foi escrito -- verifica manualmente."
        )

    texto_novo = texto[:idx_inicio] + NOVA_FUNCAO + texto[idx_fim:]

    with open(ALVO, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto_novo)

    print(f"OK: funcao substituida por deteccao de conteudo em {ALVO.resolve()}")


if __name__ == "__main__":
    aplicar()
