"""Contrato RED offline do ledger de consumo confirmado de grants one-time.

O primeiro ponto causal e a importacao direta da migration 0048 futura. O
contrato nao consome grants, nao faz seed e nao contacta rede ou gateway.
"""

import ast
from decimal import Decimal
from importlib import import_module
from inspect import getsource

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event, func, inspect as sa_inspect, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import sessionmaker


_MIGRATION_MODULE = (
    "migrations.versions.0048_checkout_offer_grant_consumption_ledger"
)
_TABLE_NAME = "checkout_offer_grant_consumptions"
_APPEND_ONLY_FUNCTION_NAME = (
    "reject_checkout_offer_grant_consumption_mutation"
)
_APPEND_ONLY_TRIGGER_NAME = (
    "trg_checkout_offer_grant_consumptions_append_only"
)
_COLUMNS = {
    "id",
    "grant_id",
    "user_id",
    "empresa_id",
    "capability",
    "idempotency_key",
    "request_fingerprint",
    "units",
    "usage_before",
    "usage_after",
    "created_at",
}


class _Operations:
    _allowed = {
        "create_table",
        "create_index",
        "drop_index",
        "drop_table",
        "execute",
    }

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name not in self._allowed:
            raise AssertionError(f"operacao Alembic fora do contrato: {name}")

        def _record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return _record


def _unique_columns(table):
    return {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }


def _check_texts(table):
    return {
        "".join(str(constraint.sqltext).lower().split())
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    }


def _index_columns(table):
    return {tuple(index.columns.keys()) for index in table.indexes}


def _assert_required_indexes(indexes):
    assert ("grant_id",) in indexes
    assert any(
        columns[-1:] == ("created_at",)
        and {"user_id", "empresa_id", "capability"}.issubset(columns[:-1])
        for columns in indexes
    )


def _normalized_ddl(statement):
    return " ".join(str(statement).strip().rstrip(";").lower().split())


def _recorded_ddl(call):
    name, args, kwargs = call
    assert name == "execute"
    assert len(args) == 1
    assert kwargs == {}
    return _normalized_ddl(args[0])


def _assert_postgresql_append_only_ddl(upgrade_calls, downgrade_calls):
    upgrade_ddl_calls = [
        call for call in upgrade_calls if call[0] == "execute"
    ]
    downgrade_ddl_calls = [
        call for call in downgrade_calls if call[0] == "execute"
    ]
    assert len(upgrade_ddl_calls) == len(downgrade_ddl_calls) == 2

    function_ddl, trigger_ddl = map(_recorded_ddl, upgrade_ddl_calls)
    function_prefix = (
        f"create function {_APPEND_ONLY_FUNCTION_NAME}() returns trigger "
        "language plpgsql as $$ begin raise exception "
    )
    assert function_ddl.startswith(function_prefix)
    assert function_ddl.endswith("; end; $$")
    function_body = function_ddl.removeprefix(function_prefix).removesuffix(
        "; end; $$"
    )
    assert function_body.startswith("'") and function_body.endswith("'")
    assert function_body.count("'") == 2
    assert "append-only" in function_body
    assert ";" not in function_body
    assert " return " not in f" {function_ddl} "

    assert trigger_ddl == (
        f"create trigger {_APPEND_ONLY_TRIGGER_NAME} before update or delete "
        f"on {_TABLE_NAME} for each row execute function "
        f"{_APPEND_ONLY_FUNCTION_NAME}()"
    )
    upgrade_positions = [
        index
        for index, call in enumerate(upgrade_calls)
        if call[0] in {"create_table", "execute"}
        and (
            call[0] == "execute"
            or call[1][0] == _TABLE_NAME
        )
    ]
    assert upgrade_positions == sorted(upgrade_positions)
    assert [upgrade_calls[index][0] for index in upgrade_positions] == [
        "create_table",
        "execute",
        "execute",
    ]

    drop_trigger_ddl, drop_function_ddl = map(
        _recorded_ddl, downgrade_ddl_calls
    )
    assert drop_trigger_ddl == (
        f"drop trigger {_APPEND_ONLY_TRIGGER_NAME} on {_TABLE_NAME}"
    )
    assert drop_function_ddl == (
        f"drop function {_APPEND_ONLY_FUNCTION_NAME}()"
    )
    drop_table_position = next(
        index
        for index, call in enumerate(downgrade_calls)
        if call[0] == "drop_table" and call[1] == (_TABLE_NAME,)
    )
    ddl_positions = [
        downgrade_calls.index(call) for call in downgrade_ddl_calls
    ]
    assert ddl_positions[0] < ddl_positions[1] < drop_table_position


def _assert_migration_contract(migration):
    assert migration.revision == "0048_checkout_offer_grant_consumption_ledger"
    assert migration.down_revision == "0047_one_time_offer_grants"
    assert migration.branch_labels is None
    assert migration.depends_on is None
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)

    source = getsource(migration)
    lowered = source.lower()
    for algorithm in (
        "blake2",
        "cryptography",
        "hashlib",
        "md5",
        "sha1",
        "sha256",
        "sha512",
    ):
        assert algorithm not in lowered

    forbidden_calls = {"bulk_insert", "delete", "insert", "update"}
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls

    operations = _Operations()
    original_op = migration.op
    try:
        migration.op = operations
        migration.upgrade()
        upgrade_calls = tuple(operations.calls)
        operations.calls.clear()
        migration.downgrade()
        downgrade_calls = tuple(operations.calls)
    finally:
        migration.op = original_op

    assert all(
        name in {"create_table", "create_index", "execute"}
        for name, _args, _kwargs in upgrade_calls
    )
    assert all(
        name in {"drop_index", "drop_table", "execute"}
        for name, _args, _kwargs in downgrade_calls
    )
    _assert_postgresql_append_only_ddl(upgrade_calls, downgrade_calls)
    create_tables = [call for call in upgrade_calls if call[0] == "create_table"]
    assert len(create_tables) == 1
    _, table_args, table_kwargs = create_tables[0]
    assert table_kwargs == {}
    assert table_args[0] == _TABLE_NAME

    elements = table_args[1:]
    columns = {
        element.name: element
        for element in elements
        if isinstance(element, sa.Column)
    }
    assert set(columns) == _COLUMNS
    assert all(not column.nullable for column in columns.values())
    assert isinstance(columns["id"].type, sa.Integer)
    assert all(
        isinstance(columns[name].type, sa.Integer)
        for name in ("grant_id", "user_id", "empresa_id", "units",
                     "usage_before", "usage_after")
    )
    assert all(
        isinstance(columns[name].type, sa.String)
        for name in ("capability", "idempotency_key", "request_fingerprint")
    )
    assert isinstance(columns["created_at"].type, sa.DateTime)
    assert columns["created_at"].server_default is not None

    temporary_metadata = sa.MetaData()
    migration_table = sa.Table(_TABLE_NAME, temporary_metadata, *elements)
    assert tuple(migration_table.primary_key.columns.keys()) == ("id",)
    assert _unique_columns(migration_table) == {("idempotency_key",)}
    checks = _check_texts(migration_table)
    assert "units>0" in checks
    assert "usage_before>=0" in checks
    assert "usage_after=usage_before+units" in checks
    assert all("request_fingerprint" not in check for check in checks)

    grant_foreign_keys = [
        constraint
        for constraint in migration_table.foreign_key_constraints
        if tuple(constraint.column_keys) == ("grant_id",)
    ]
    assert len(grant_foreign_keys) == 1
    grant_fk = grant_foreign_keys[0]
    assert tuple(element.target_fullname for element in grant_fk.elements) == (
        "checkout_offer_grants.id",
    )
    assert (grant_fk.ondelete or "NO ACTION").upper() not in {"CASCADE", "SET NULL"}

    created_indexes = {
        (args[0], args[1], tuple(args[2]))
        for name, args, _kwargs in upgrade_calls
        if name == "create_index"
    }
    assert created_indexes
    assert {table for _name, table, _columns in created_indexes} == {_TABLE_NAME}
    _assert_required_indexes({columns for _name, _table, columns in created_indexes})

    dropped_indexes = {
        (args[0], kwargs.get("table_name"))
        for name, args, kwargs in downgrade_calls
        if name == "drop_index"
    }
    assert dropped_indexes == {
        (name, _TABLE_NAME) for name, _table, _columns in created_indexes
    }
    assert [call[1][0] for call in downgrade_calls if call[0] == "drop_table"] == [
        _TABLE_NAME
    ]
    assert downgrade_calls[-1][0:2] == ("drop_table", (_TABLE_NAME,))


def _assert_model_contract(models):
    consumption = models.CheckoutOfferGrantConsumption
    table = consumption.__table__
    assert table.metadata is models.Base.metadata
    assert table.name == _TABLE_NAME
    assert set(table.columns.keys()) == _COLUMNS
    assert all(not column.nullable for column in table.columns)
    assert tuple(table.primary_key.columns.keys()) == ("id",)
    assert _unique_columns(table) == {("idempotency_key",)}
    assert _check_texts(table).issuperset(
        {"units>0", "usage_before>=0", "usage_after=usage_before+units"}
    )
    assert all(
        "request_fingerprint" not in check for check in _check_texts(table)
    )
    _assert_required_indexes(_index_columns(table))

    grant_foreign_keys = [
        constraint
        for constraint in table.foreign_key_constraints
        if tuple(constraint.column_keys) == ("grant_id",)
    ]
    assert len(grant_foreign_keys) == 1
    assert (grant_foreign_keys[0].ondelete or "NO ACTION").upper() not in {
        "CASCADE",
        "SET NULL",
    }

    child_relationships = [
        relationship
        for relationship in sa_inspect(consumption).relationships
        if relationship.mapper.class_ is models.CheckoutOfferGrant
    ]
    parent_relationships = [
        relationship
        for relationship in sa_inspect(models.CheckoutOfferGrant).relationships
        if relationship.mapper.class_ is consumption
    ]
    assert len(child_relationships) == len(parent_relationships) == 1
    child_relationship = child_relationships[0]
    parent_relationship = parent_relationships[0]
    assert child_relationship.key == "grant"
    assert child_relationship.back_populates == parent_relationship.key
    assert parent_relationship.back_populates == child_relationship.key
    assert "delete" not in parent_relationship.cascade
    assert "delete-orphan" not in parent_relationship.cascade

    assert set(models.CheckoutOfferGrant.__table__.columns.keys()) == {
        "id", "ordem_id", "usage_unit", "usage_limit", "usage_consumed",
        "estado", "created_at",
    }
    assert set(models.CheckoutOfferGrantCapability.__table__.columns.keys()) == {
        "id", "grant_id", "codigo",
    }
    model_source = getsource(consumption).lower()
    assert not any(
        algorithm in model_source
        for algorithm in ("blake2", "hashlib", "md5", "sha1", "sha256", "sha512")
    )


def _order(models, *, identifier, key):
    return models.OrdemCheckout(
        id=identifier,
        user_id=41,
        empresa_id=301,
        plano_id=None,
        offer_id=7,
        offer_code="document-one-time-company",
        contract_version=3,
        vertical="document",
        commercial_model="one_time",
        subject_type="company",
        subject_id=301,
        valor=Decimal("79.50"),
        moeda="BRL",
        estado="paid",
        idempotency_key=key,
        billing_period=None,
        usage_unit="document",
        usage_limit=10,
    )


def _assert_runtime_contract(models):
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session.begin() as db:
        db.add(models.User(
            id=41,
            email="consumption-ledger@example.invalid",
            hashed_password="hash-de-teste",
        ))
        db.add(models.Empresa(
            id=301,
            razao_social="Empresa ledger de consumo",
            user_id=41,
        ))
        db.add(models.CheckoutOffer(
            id=7,
            codigo="document-one-time-company",
            nome_publico="Documentos one time",
            vertical="document",
            commercial_model="one_time",
            subject_type="company",
            estado="published",
            moeda="BRL",
            preco=Decimal("79.50"),
            billing_period=None,
            usage_unit="document",
            usage_limit=10,
            contract_version=3,
        ))
        db.add_all([
            _order(models, identifier=701, key="consumption-order-701"),
            _order(models, identifier=702, key="consumption-order-702"),
        ])

    with Session.begin() as db:
        first_grant = models.CheckoutOfferGrant(
            ordem_id=701,
            usage_unit="document",
            usage_limit=10,
            usage_consumed=5,
            estado="active",
        )
        second_grant = models.CheckoutOfferGrant(
            ordem_id=702,
            usage_unit="document",
            usage_limit=10,
            usage_consumed=0,
            estado="active",
        )
        db.add_all([first_grant, second_grant])
        db.flush()
        first_grant_id = first_grant.id
        second_grant_id = second_grant.id

    with Session.begin() as db:
        db.add_all([
            models.CheckoutOfferGrantConsumption(
                grant_id=first_grant_id,
                user_id=41,
                empresa_id=301,
                capability="document.extract",
                idempotency_key="consume-confirmed-global-1",
                request_fingerprint="opaque:v1:alpha",
                units=3,
                usage_before=0,
                usage_after=3,
            ),
            models.CheckoutOfferGrantConsumption(
                grant_id=first_grant_id,
                user_id=41,
                empresa_id=301,
                capability="document.extract",
                idempotency_key="consume-confirmed-global-2",
                request_fingerprint="future-format/v2/beta",
                units=2,
                usage_before=3,
                usage_after=5,
            ),
        ])

    with Session() as db:
        rows = db.scalars(
            select(models.CheckoutOfferGrantConsumption).order_by(
                models.CheckoutOfferGrantConsumption.id
            )
        ).all()
        assert [(row.units, row.usage_before, row.usage_after) for row in rows] == [
            (3, 0, 3),
            (2, 3, 5),
        ]
        assert all(row.created_at is not None for row in rows)
        assert all(row.grant.id == first_grant_id for row in rows)
        parent = db.get(models.CheckoutOfferGrant, first_grant_id)
        relationship = sa_inspect(models.CheckoutOfferGrant).relationships
        parent_key = next(
            item.key
            for item in relationship
            if item.mapper.class_ is models.CheckoutOfferGrantConsumption
        )
        assert {row.id for row in getattr(parent, parent_key)} == {
            row.id for row in rows
        }
        first_id = rows[0].id

    def _count(db):
        return db.scalar(
            select(func.count()).select_from(models.CheckoutOfferGrantConsumption)
        )

    invalid_cases = (
        {"units": 0, "usage_before": 0, "usage_after": 0},
        {"units": -1, "usage_before": 0, "usage_after": -1},
        {"units": 1, "usage_before": -1, "usage_after": 0},
        {"units": 2, "usage_before": 4, "usage_after": 7},
    )
    for number, values in enumerate(invalid_cases, start=1):
        with Session() as db:
            before = _count(db)
            db.add(models.CheckoutOfferGrantConsumption(
                grant_id=second_grant_id,
                user_id=41,
                empresa_id=301,
                capability="document.extract",
                idempotency_key=f"consume-invalid-{number}",
                request_fingerprint=f"opaque-invalid:{number}",
                **values,
            ))
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()
            assert _count(db) == before

    with Session() as db:
        before = _count(db)
        db.add(models.CheckoutOfferGrantConsumption(
            grant_id=second_grant_id,
            user_id=41,
            empresa_id=301,
            capability="document.extract",
            idempotency_key="consume-confirmed-global-1",
            request_fingerprint="opaque:v9:collision",
            units=1,
            usage_before=0,
            usage_after=1,
        ))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        assert _count(db) == before

    with Session() as db:
        before = _count(db)
        db.add(models.CheckoutOfferGrantConsumption(
            grant_id=999999,
            user_id=41,
            empresa_id=301,
            capability="document.extract",
            idempotency_key="consume-missing-grant",
            request_fingerprint="opaque:v1:missing-grant",
            units=1,
            usage_before=0,
            usage_after=1,
        ))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        assert _count(db) == before

    # Esta prova SQLite exercita apenas a defesa ORM adicional. A garantia
    # PostgreSQL independente e auditada nas chamadas DDL da migration.
    with Session() as db:
        row = db.get(models.CheckoutOfferGrantConsumption, first_id)
        with pytest.raises(InvalidRequestError, match="append-only"):
            row.capability = "document.changed"
            db.flush()
        db.rollback()
    with Session() as db:
        row = db.get(models.CheckoutOfferGrantConsumption, first_id)
        assert row.capability == "document.extract"
        with pytest.raises(InvalidRequestError, match="append-only"):
            db.delete(row)
            db.flush()
        db.rollback()
    with Session() as db:
        assert db.get(models.CheckoutOfferGrantConsumption, first_id) is not None
        grant = db.get(models.CheckoutOfferGrant, first_grant_id)
        with pytest.raises(IntegrityError):
            db.delete(grant)
            db.flush()
        db.rollback()
        assert _count(db) == 2


def test_payments_checkout_offer_grant_consumption_ledger_contract_red():
    migration = import_module(_MIGRATION_MODULE)
    models = import_module("app.models")
    assert hasattr(models, "CheckoutOfferGrantConsumption")

    _assert_migration_contract(migration)
    _assert_model_contract(models)
    _assert_runtime_contract(models)
