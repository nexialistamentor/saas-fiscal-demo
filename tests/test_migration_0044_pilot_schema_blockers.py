"""Contract and fail-closed tests for reconciliation revision 0044."""

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0044_pilot_schema_blockers.py"


def _load():
    spec = importlib.util.spec_from_file_location("migration_0044", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_static_contract_and_exact_scope():
    source = MIGRATION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    module = _load()
    assert module.revision == "0044_pilot_schema_blockers"
    assert module.down_revision == "0043_reconcile_tabela_mva_schema"
    assert module.branch_labels is module.depends_on is None
    assert "op.get_bind()" in source
    assert ".begin(" not in source
    forbidden = ("UPDATE ", "DELETE ", "INSERT ", "server_default", "create_index", "drop_constraint", "drop_column")
    assert not any(token in source for token in forbidden)
    downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
    downgrade_source = ast.get_source_segment(source, downgrade)
    assert "DROP" not in downgrade_source.upper()
    assert "nullable=True" not in downgrade_source


class _Result:
    def __init__(self, *, row=None, scalar=None, rows=None):
        self.row, self.scalar, self.rows = row, scalar, rows
    def one_or_none(self): return self.row
    def scalar_one(self): return self.scalar
    def all(self): return self.rows


class _Bind:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, columns=None, nulls=None, invalid_roles=0, constraints=None):
        self.columns = columns or {
            ("usuarios", "consulta_paga"): (False, "bool"),
            ("planos", "limite_analises"): (False, "int4"),
            ("usuarios", "role"): (True, "varchar"),
        }
        self.nulls = nulls or {}
        self.invalid_roles = invalid_roles
        self.constraints = [] if constraints is None else constraints

    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM pg_catalog.pg_class AS c" in sql:
            return _Result(row=self.columns.get((params["table_name"], params["column_name"])))
        if "WHERE consulta_paga IS NULL" in sql:
            return _Result(scalar=self.nulls.get("consulta_paga", 0))
        if "WHERE limite_analises IS NULL" in sql:
            return _Result(scalar=self.nulls.get("limite_analises", 0))
        if "role NOT IN" in sql:
            return _Result(scalar=self.invalid_roles)
        if "FROM pg_catalog.pg_constraint" in sql:
            return _Result(rows=self.constraints)
        raise AssertionError(sql)


class _Op:
    def __init__(self, bind): self.bind, self.ddl = bind, []
    def get_bind(self): return self.bind
    def alter_column(self, table, column, **kwargs): self.ddl.append(("alter", table, column, kwargs))
    def create_check_constraint(self, name, table, expression): self.ddl.append(("check", name, table, expression))


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda b: b.columns.__setitem__(("usuarios", "consulta_paga"), (False, "int4")), "noncanonical type"),
        (lambda b: b.columns.pop(("usuarios", "consulta_paga")), "missing"),
        (lambda b: b.columns.pop(("planos", "limite_analises")), "missing"),
        (lambda b: b.nulls.__setitem__("consulta_paga", 1), "NULL values"),
        (lambda b: b.nulls.__setitem__("limite_analises", 1), "NULL values"),
        (lambda b: setattr(b, "invalid_roles", 1), "invalid non-NULL"),
        (lambda b: setattr(b, "constraints", [("ck_usuarios_role_valido", "usuarios", "c", True, "role <> 'x'")]), "ambiguous or noncanonical"),
        (lambda b: setattr(b, "constraints", [("other_role_check", "usuarios", "c", True, "role <> 'x'"), ("ck_usuarios_role_valido", "usuarios", "c", True, "x")]), "ambiguous or noncanonical"),
        (lambda b: setattr(b, "constraints", [("ck_usuarios_role_valido", "outra_tabela", "c", True, "x")]), "ambiguous or noncanonical"),
    ],
)
def test_every_bad_state_fails_before_any_ddl(mutate, match):
    migration = _load()
    bind = _Bind()
    mutate(bind)
    operation = _Op(bind)
    migration.op = operation
    with pytest.raises(RuntimeError, match=match):
        migration.upgrade()
    assert operation.ddl == []


def test_repairs_run_only_after_all_gates_and_in_fixed_order():
    migration = _load()
    operation = _Op(_Bind())
    migration.op = operation
    migration.upgrade()
    assert [(item[0], item[1], item[2]) for item in operation.ddl] == [
        ("alter", "usuarios", "consulta_paga"),
        ("alter", "planos", "limite_analises"),
        ("check", "ck_usuarios_role_valido", "usuarios"),
    ]


def test_canonical_state_is_complete_no_op():
    migration = _load()
    bind = _Bind(
        columns={
            ("usuarios", "consulta_paga"): (True, "bool"),
            ("planos", "limite_analises"): (True, "int4"),
            ("usuarios", "role"): (True, "varchar"),
        },
        constraints=[("ck_usuarios_role_valido", "usuarios", "c", True, migration._CANONICAL_ROLE_CHECK)],
    )
    operation = _Op(bind)
    migration.op = operation
    migration.upgrade()
    assert operation.ddl == []
