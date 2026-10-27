"""Verifica que o compilador SQLite nunca modifica a metadata SQLAlchemy."""
import os
os.environ.setdefault("ALEMBIC_RUNNING", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import CheckConstraint, Column, Integer, MetaData, Table, create_engine
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
import app.database  # noqa: F401  # regista o compilador específico SQLite


def test_sqlite_ignores_only_pg_checks_and_preserves_postgresql_metadata():
    t = Table(
        "b02_check_nonmutation_probe", MetaData(), Column("x", Integer),
        CheckConstraint("x > 0", name="ck_sqlite_effective"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_pg_native"),
        CheckConstraint("x ~ '^[1-9]+$'", name="ck_pg_regex"),
    )
    names_before = {c.name for c in t.constraints}
    ddl_sqlite = str(CreateTable(t).compile(dialect=sqlite.dialect()))
    assert 'ck_sqlite_effective' in ddl_sqlite
    assert 'ck_pg_native' not in ddl_sqlite
    assert 'ck_pg_regex' not in ddl_sqlite
    assert {c.name for c in t.constraints} == names_before
    ddl_pg = str(CreateTable(t).compile(dialect=postgresql.dialect()))
    assert all(name in ddl_pg for name in ('ck_sqlite_effective', 'ck_pg_native', 'ck_pg_regex'))
    assert {c.name for c in t.constraints} == names_before
    engine = create_engine('sqlite:///:memory:')
    t.create(bind=engine)
    with engine.begin() as conn:
        try:
            conn.execute(t.insert().values(x=-1))
        except IntegrityError:
            pass
        else:
            raise AssertionError('CHECK SQLite simples deixou de ser aplicado')
