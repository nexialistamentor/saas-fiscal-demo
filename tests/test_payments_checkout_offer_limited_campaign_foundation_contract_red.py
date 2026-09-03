"""Contrato RED da fundacao persistente de campanhas comerciais limitadas."""

from datetime import datetime, timedelta
from decimal import Decimal
from importlib import util
from pathlib import Path
import re

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event, inspect as sa_inspect
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateIndex


_MIGRATION_NAME = "0049_checkout_offer_limited_campaign_foundation"
_CAMPAIGN_COLUMNS = {
    "id",
    "codigo",
    "offer_id",
    "estado",
    "purchase_limit",
    "reservation_ttl_seconds",
    "contract_version",
    "criado_em",
    "atualizado_em",
}
_RESERVATION_COLUMNS = {
    "id",
    "campaign_id",
    "ordem_id",
    "estado",
    "reserved_at",
    "expires_at",
    "confirmed_at",
    "released_at",
    "expired_at",
}
_ORDER_CAMPAIGN_COLUMNS = {
    "campaign_id",
    "campaign_code",
    "campaign_contract_version",
    "campaign_purchase_limit",
    "campaign_reservation_expires_at",
}


class _MigrationRecorder:
    def __init__(self):
        self.tables = {}
        self.added_columns = []
        self.foreign_keys = []
        self.checks = []
        self.indexes = []
        self.executions = []

    @staticmethod
    def f(name):
        return name

    def create_table(self, name, *elements, **kwargs):
        assert name not in self.tables
        self.tables[name] = {"elements": elements, "kwargs": kwargs}

    def add_column(self, table_name, column):
        self.added_columns.append((table_name, column))

    def create_foreign_key(
        self, name, source, referent, local_columns, remote_columns, **kwargs
    ):
        self.foreign_keys.append(
            {
                "name": name,
                "source": source,
                "referent": referent,
                "local_columns": tuple(local_columns),
                "remote_columns": tuple(remote_columns),
                "kwargs": kwargs,
            }
        )

    def create_check_constraint(self, name, table_name, condition, **kwargs):
        self.checks.append(
            {
                "name": name,
                "table_name": table_name,
                "condition": condition,
                "kwargs": kwargs,
            }
        )

    def create_index(self, name, table_name, columns, unique=False, **kwargs):
        self.indexes.append(
            {
                "name": name,
                "table_name": table_name,
                "columns": tuple(columns),
                "unique": unique,
                "kwargs": kwargs,
            }
        )

    def execute(self, statement):
        self.executions.append(statement)


def _normalizar_sql(value):
    return " ".join(str(value).lower().split())


def _assert_postgresql_identifier_limit(test_source):
    frozen_schema_names = set(
        re.findall(r'''["']((?:ck|uq|ix|fk)_[a-z0-9_]+)["']''', test_source)
    )
    overlength = sorted(
        name for name in frozen_schema_names if len(name) > 63
    )
    assert not overlength, (
        "identificadores PostgreSQL excedem 63 caracteres: "
        + ", ".join(overlength)
    )


def _carregar_migration(path):
    spec = util.spec_from_file_location(_MIGRATION_NAME, path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _elementos_tabela(recorder, table_name, kind):
    table = recorder.tables.get(table_name)
    if table is None:
        return ()
    return tuple(
        element
        for element in table["elements"]
        if isinstance(element, kind)
    )


def _colunas_tabela(recorder, table_name):
    return {
        column.name: column
        for column in _elementos_tabela(recorder, table_name, sa.Column)
    }


def _constraint_column_names(constraint):
    bound_names = tuple(column.name for column in constraint.columns)
    if bound_names:
        return bound_names
    return tuple(
        value if isinstance(value, str) else value.name
        for value in constraint._pending_colargs
    )


def _assert_column_type(column, expected_type, *, length=None):
    assert isinstance(column.type, expected_type)
    if length is not None:
        assert column.type.length == length


def _checks_tabela(table):
    return {
        constraint.name: _normalizar_sql(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    }


def _checks_migration(recorder, table_name):
    inline = {
        constraint.name: _normalizar_sql(constraint.sqltext)
        for constraint in _elementos_tabela(
            recorder, table_name, sa.CheckConstraint
        )
    }
    adicionais = {
        check["name"]: _normalizar_sql(check["condition"])
        for check in recorder.checks
        if check["table_name"] == table_name
    }
    return inline | adicionais


def _assert_fk_model(table, local_column, target):
    matches = [
        foreign_key
        for foreign_key in table.foreign_keys
        if foreign_key.parent.name == local_column
        and foreign_key.target_fullname == target
    ]
    assert len(matches) == 1
    assert (matches[0].ondelete or "").upper() != "CASCADE"


def _assert_fk_migration(recorder, table_name, local_column, target):
    target_table, target_column = target.split(".")
    inline_matches = []
    for constraint in _elementos_tabela(
        recorder, table_name, sa.ForeignKeyConstraint
    ):
        if _constraint_column_names(constraint) != (local_column,):
            continue
        if tuple(element.target_fullname for element in constraint.elements) == (
            target,
        ):
            inline_matches.append(constraint)
    external_matches = [
        foreign_key
        for foreign_key in recorder.foreign_keys
        if foreign_key["source"] == table_name
        and foreign_key["referent"] == target_table
        and foreign_key["local_columns"] == (local_column,)
        and foreign_key["remote_columns"] == (target_column,)
    ]
    assert len(inline_matches) + len(external_matches) == 1
    for constraint in inline_matches:
        assert (constraint.ondelete or "").upper() != "CASCADE"
    for constraint in external_matches:
        assert (constraint["kwargs"].get("ondelete") or "").upper() != "CASCADE"


def _assert_unique(table, expected_columns, expected_name):
    matches = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == expected_columns
    ]
    assert len(matches) == 1
    assert matches[0].name == expected_name


def _assert_unique_migration(
    recorder, table_name, expected_columns, expected_name
):
    matches = [
        constraint
        for constraint in _elementos_tabela(
            recorder, table_name, sa.UniqueConstraint
        )
        if _constraint_column_names(constraint) == expected_columns
    ]
    assert len(matches) == 1
    assert matches[0].name == expected_name


def _assert_primary_key_migration(recorder, table_name):
    matches = _elementos_tabela(recorder, table_name, sa.PrimaryKeyConstraint)
    assert len(matches) == 1
    assert _constraint_column_names(matches[0]) == ("id",)


def _sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _oferta(models, identificador, codigo):
    return models.CheckoutOffer(
        id=identificador,
        codigo=codigo,
        nome_publico=f"Oferta {identificador}",
        vertical="tax",
        commercial_model="monthly",
        subject_type="company",
        estado="published",
        moeda="BRL",
        preco=Decimal("49.90"),
        billing_period="month",
        usage_unit=None,
        usage_limit=None,
        contract_version=1,
    )


def _campanha(
    models,
    *,
    identificador,
    offer_id,
    codigo,
    estado="draft",
    purchase_limit=3,
    reservation_ttl_seconds=17,
    contract_version=1,
):
    now = datetime(2026, 9, 3, 12, 0, 0)
    return models.CheckoutOfferCampaign(
        id=identificador,
        codigo=codigo,
        offer_id=offer_id,
        estado=estado,
        purchase_limit=purchase_limit,
        reservation_ttl_seconds=reservation_ttl_seconds,
        contract_version=contract_version,
        criado_em=now,
        atualizado_em=now,
    )


def _ordem(models, *, identificador, offer_id, offer_code, campaign=None, **changes):
    values = {
        "id": identificador,
        "user_id": 41,
        "empresa_id": 301,
        "plano_id": None,
        "offer_id": offer_id,
        "offer_code": offer_code,
        "contract_version": 1,
        "vertical": "tax",
        "commercial_model": "monthly",
        "subject_type": "company",
        "subject_id": 301,
        "valor": Decimal("49.90"),
        "moeda": "BRL",
        "billing_period": "month",
        "usage_unit": None,
        "usage_limit": None,
        "idempotency_key": f"campaign-foundation-order-{identificador}",
        "estado": "pending",
        "campaign_id": None,
        "campaign_code": None,
        "campaign_contract_version": None,
        "campaign_purchase_limit": None,
        "campaign_reservation_expires_at": None,
    }
    if campaign is not None:
        values.update(
            campaign_id=campaign.id,
            campaign_code=campaign.codigo,
            campaign_contract_version=campaign.contract_version,
            campaign_purchase_limit=campaign.purchase_limit,
            campaign_reservation_expires_at=datetime(2026, 9, 3, 12, 5, 0),
        )
    values.update(changes)
    return models.OrdemCheckout(**values)


def _reserva(models, *, identificador, campaign_id, ordem_id, estado, **changes):
    reserved_at = datetime(2026, 9, 3, 12, 0, 0)
    values = {
        "id": identificador,
        "campaign_id": campaign_id,
        "ordem_id": ordem_id,
        "estado": estado,
        "reserved_at": reserved_at,
        "expires_at": reserved_at + timedelta(seconds=17),
        "confirmed_at": None,
        "released_at": None,
        "expired_at": None,
    }
    if estado == "confirmed":
        values["confirmed_at"] = reserved_at + timedelta(seconds=2)
    elif estado == "released":
        values["released_at"] = reserved_at + timedelta(seconds=3)
    elif estado == "expired":
        values["expired_at"] = reserved_at + timedelta(seconds=17)
    values.update(changes)
    return models.CheckoutOfferCampaignReservation(**values)


def _assert_integrity_error(Session, entity):
    with Session() as db:
        db.add(entity)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_payments_checkout_offer_limited_campaign_foundation_contract_red():
    repo_root = Path(__file__).resolve().parents[1]
    _assert_postgresql_identifier_limit(Path(__file__).read_text(encoding="utf-8"))
    migration_path = (
        repo_root / "migrations" / "versions" / f"{_MIGRATION_NAME}.py"
    )
    models = __import__("app.models", fromlist=["Base"])

    missing_foundation = []
    if not migration_path.is_file():
        missing_foundation.append(str(migration_path.relative_to(repo_root)))
    for model_name in (
        "CheckoutOfferCampaign",
        "CheckoutOfferCampaignReservation",
    ):
        if not hasattr(models, model_name):
            missing_foundation.append(f"app.models.{model_name}")
    assert not missing_foundation, (
        "foundation 0049/modelos ainda ausente: " + ", ".join(missing_foundation)
    )

    migration_source = migration_path.read_text(encoding="utf-8")
    migration = _carregar_migration(migration_path)
    assert migration.revision == _MIGRATION_NAME
    assert migration.down_revision == "0048_checkout_offer_grant_consumption_ledger"
    assert re.search(r"\b(?:bulk_insert|insert\s+into)\b", migration_source, re.I) is None
    assert re.search(r"(?<!\w)1_?000(?!\w)", migration_source) is None
    assert re.search(
        r"\b(?:hashlib|sha[_-]?256|signature)\b", migration_source, re.I
    ) is None

    recorder = _MigrationRecorder()
    real_op = migration.op
    migration.op = recorder
    try:
        migration.upgrade()
    finally:
        migration.op = real_op

    assert set(recorder.tables) == {
        "checkout_offer_campaigns",
        "checkout_offer_campaign_reservations",
    }
    assert recorder.executions == []

    campaign_migration_columns = _colunas_tabela(
        recorder, "checkout_offer_campaigns"
    )
    reservation_migration_columns = _colunas_tabela(
        recorder, "checkout_offer_campaign_reservations"
    )
    assert set(campaign_migration_columns) == _CAMPAIGN_COLUMNS
    assert set(reservation_migration_columns) == _RESERVATION_COLUMNS
    assert all(
        not campaign_migration_columns[name].nullable
        for name in _CAMPAIGN_COLUMNS
    )
    assert all(
        not reservation_migration_columns[name].nullable
        for name in _RESERVATION_COLUMNS
        - {"confirmed_at", "released_at", "expired_at"}
    )
    assert all(
        reservation_migration_columns[name].nullable
        for name in {"confirmed_at", "released_at", "expired_at"}
    )
    _assert_primary_key_migration(recorder, "checkout_offer_campaigns")
    _assert_primary_key_migration(
        recorder, "checkout_offer_campaign_reservations"
    )
    for name in ("id", "offer_id", "purchase_limit", "reservation_ttl_seconds", "contract_version"):
        _assert_column_type(campaign_migration_columns[name], sa.Integer)
    _assert_column_type(campaign_migration_columns["codigo"], sa.String, length=120)
    _assert_column_type(campaign_migration_columns["estado"], sa.String, length=20)
    for name in ("criado_em", "atualizado_em"):
        _assert_column_type(campaign_migration_columns[name], sa.DateTime)
    for name in ("id", "campaign_id", "ordem_id"):
        _assert_column_type(reservation_migration_columns[name], sa.Integer)
    _assert_column_type(reservation_migration_columns["estado"], sa.String, length=20)
    for name in (
        "reserved_at",
        "expires_at",
        "confirmed_at",
        "released_at",
        "expired_at",
    ):
        _assert_column_type(reservation_migration_columns[name], sa.DateTime)
    _assert_unique_migration(
        recorder,
        "checkout_offer_campaigns",
        ("codigo",),
        "uq_checkout_offer_campaigns_codigo",
    )
    _assert_unique_migration(
        recorder,
        "checkout_offer_campaign_reservations",
        ("ordem_id",),
        "uq_checkout_offer_campaign_reservations_ordem_id",
    )
    _assert_fk_migration(
        recorder, "checkout_offer_campaigns", "offer_id", "checkout_offers.id"
    )
    _assert_fk_migration(
        recorder,
        "checkout_offer_campaign_reservations",
        "campaign_id",
        "checkout_offer_campaigns.id",
    )
    _assert_fk_migration(
        recorder,
        "checkout_offer_campaign_reservations",
        "ordem_id",
        "ordens_checkout.id",
    )

    campaign_migration_checks = _checks_migration(
        recorder, "checkout_offer_campaigns"
    )
    reservation_migration_checks = _checks_migration(
        recorder, "checkout_offer_campaign_reservations"
    )
    assert set(campaign_migration_checks) == {
        "ck_checkout_offer_campaigns_codigo_canonico",
        "ck_checkout_offer_campaigns_estado_valido",
        "ck_checkout_offer_campaigns_purchase_limit_positivo",
        "ck_checkout_offer_campaigns_reservation_ttl_seconds_positivo",
        "ck_checkout_offer_campaigns_contract_version_positivo",
    }
    assert "codigo = lower(codigo)" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_codigo_canonico"
    ]
    assert "codigo = trim(codigo)" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_codigo_canonico"
    ]
    assert "length(codigo) > 0" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_codigo_canonico"
    ]
    assert "codigo not like '%--%'" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_codigo_canonico"
    ]
    assert "draft" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_estado_valido"
    ]
    assert "active" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_estado_valido"
    ]
    assert "retired" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_estado_valido"
    ]
    assert "purchase_limit > 0" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_purchase_limit_positivo"
    ]
    assert "reservation_ttl_seconds > 0" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_reservation_ttl_seconds_positivo"
    ]
    assert "contract_version > 0" in campaign_migration_checks[
        "ck_checkout_offer_campaigns_contract_version_positivo"
    ]
    assert set(reservation_migration_checks) == {
        "ck_checkout_offer_campaign_reservations_estado_valido",
        "ck_checkout_offer_campaign_reservations_intervalo_valido",
        "ck_checkout_offer_campaign_reservations_timestamps_coerentes",
    }
    reservation_coherence = reservation_migration_checks[
        "ck_checkout_offer_campaign_reservations_timestamps_coerentes"
    ]
    for state, timestamp in (
        ("reserved", None),
        ("confirmed", "confirmed_at"),
        ("released", "released_at"),
        ("expired", "expired_at"),
    ):
        assert state in reservation_coherence
        if timestamp is not None:
            assert f"{timestamp} is not null" in reservation_coherence
    for timestamp in ("confirmed_at", "released_at", "expired_at"):
        assert f"{timestamp} is null" in reservation_coherence
    assert "expires_at > reserved_at" in reservation_migration_checks[
        "ck_checkout_offer_campaign_reservations_intervalo_valido"
    ]

    campaign_active_index = [
        index
        for index in recorder.indexes
        if index["name"] == "uq_checkout_offer_campaigns_offer_active"
    ]
    assert len(campaign_active_index) == 1
    campaign_active_index = campaign_active_index[0]
    assert campaign_active_index["table_name"] == "checkout_offer_campaigns"
    assert campaign_active_index["columns"] == ("offer_id",)
    assert campaign_active_index["unique"] is True
    assert "estado = 'active'" in _normalizar_sql(
        campaign_active_index["kwargs"].get("postgresql_where")
    )
    assert "estado = 'active'" in _normalizar_sql(
        campaign_active_index["kwargs"].get("sqlite_where")
    )
    reservation_quota_index = [
        index
        for index in recorder.indexes
        if index["name"]
        == "ix_checkout_offer_campaign_reservations_camp_estado_expires_at"
    ]
    assert len(reservation_quota_index) == 1
    assert reservation_quota_index[0]["table_name"] == (
        "checkout_offer_campaign_reservations"
    )
    assert reservation_quota_index[0]["columns"] == (
        "campaign_id",
        "estado",
        "expires_at",
    )
    assert reservation_quota_index[0]["unique"] is False

    order_additions = {
        column.name: column
        for table_name, column in recorder.added_columns
        if table_name == "ordens_checkout"
    }
    assert set(order_additions) == _ORDER_CAMPAIGN_COLUMNS
    assert all(column.nullable for column in order_additions.values())
    for name in (
        "campaign_id",
        "campaign_contract_version",
        "campaign_purchase_limit",
    ):
        _assert_column_type(order_additions[name], sa.Integer)
    _assert_column_type(order_additions["campaign_code"], sa.String, length=120)
    _assert_column_type(
        order_additions["campaign_reservation_expires_at"], sa.DateTime
    )
    _assert_fk_migration(
        recorder, "ordens_checkout", "campaign_id", "checkout_offer_campaigns.id"
    )
    order_migration_checks = _checks_migration(recorder, "ordens_checkout")
    assert set(order_migration_checks) == {
        "ck_ordens_checkout_campaign_snapshot_coerente"
    }
    order_coherence = order_migration_checks[
        "ck_ordens_checkout_campaign_snapshot_coerente"
    ]
    for column in _ORDER_CAMPAIGN_COLUMNS:
        assert f"{column} is null" in order_coherence
        assert f"{column} is not null" in order_coherence
    assert "campaign_contract_version > 0" in order_coherence
    assert "campaign_purchase_limit > 0" in order_coherence

    campaign_model = models.CheckoutOfferCampaign
    reservation_model = models.CheckoutOfferCampaignReservation
    assert campaign_model.__tablename__ == "checkout_offer_campaigns"
    assert reservation_model.__tablename__ == "checkout_offer_campaign_reservations"
    assert campaign_model.__table__.metadata is models.Base.metadata
    assert reservation_model.__table__.metadata is models.Base.metadata
    campaign_table = campaign_model.__table__
    reservation_table = reservation_model.__table__
    order_table = models.OrdemCheckout.__table__
    assert set(campaign_table.columns.keys()) == _CAMPAIGN_COLUMNS
    assert set(reservation_table.columns.keys()) == _RESERVATION_COLUMNS
    assert _ORDER_CAMPAIGN_COLUMNS <= set(order_table.columns.keys())
    assert all(not campaign_table.c[name].nullable for name in _CAMPAIGN_COLUMNS)
    assert all(
        not reservation_table.c[name].nullable
        for name in _RESERVATION_COLUMNS
        - {"confirmed_at", "released_at", "expired_at"}
    )
    assert all(
        reservation_table.c[name].nullable
        for name in {"confirmed_at", "released_at", "expired_at"}
    )
    assert all(order_table.c[name].nullable for name in _ORDER_CAMPAIGN_COLUMNS)
    assert tuple(campaign_table.primary_key.columns.keys()) == ("id",)
    assert tuple(reservation_table.primary_key.columns.keys()) == ("id",)
    for name in ("id", "offer_id", "purchase_limit", "reservation_ttl_seconds", "contract_version"):
        _assert_column_type(campaign_table.c[name], sa.Integer)
    _assert_column_type(campaign_table.c.codigo, sa.String, length=120)
    _assert_column_type(campaign_table.c.estado, sa.String, length=20)
    for name in ("criado_em", "atualizado_em"):
        _assert_column_type(campaign_table.c[name], sa.DateTime)
    for name in ("id", "campaign_id", "ordem_id"):
        _assert_column_type(reservation_table.c[name], sa.Integer)
    _assert_column_type(reservation_table.c.estado, sa.String, length=20)
    for name in (
        "reserved_at",
        "expires_at",
        "confirmed_at",
        "released_at",
        "expired_at",
    ):
        _assert_column_type(reservation_table.c[name], sa.DateTime)

    forbidden_campaign_columns = {
        "preco",
        "price",
        "valor",
        "moeda",
        "currency",
        "usage_unit",
        "usage_limit",
        "capability",
        "capabilities",
        "commercial_model",
        "vertical",
        "subject_type",
        "access_token",
        "credential",
        "credencial",
        "gateway_payload",
        "payload",
        "secret",
        "segredo",
        "token",
    }
    assert not set(campaign_table.columns.keys()).intersection(
        forbidden_campaign_columns
    )
    _assert_unique(
        campaign_table,
        ("codigo",),
        "uq_checkout_offer_campaigns_codigo",
    )
    _assert_unique(
        reservation_table,
        ("ordem_id",),
        "uq_checkout_offer_campaign_reservations_ordem_id",
    )
    _assert_fk_model(campaign_table, "offer_id", "checkout_offers.id")
    _assert_fk_model(
        reservation_table, "campaign_id", "checkout_offer_campaigns.id"
    )
    _assert_fk_model(reservation_table, "ordem_id", "ordens_checkout.id")
    _assert_fk_model(order_table, "campaign_id", "checkout_offer_campaigns.id")

    campaign_checks = _checks_tabela(campaign_table)
    reservation_checks = _checks_tabela(reservation_table)
    order_checks = _checks_tabela(order_table)
    assert campaign_checks == campaign_migration_checks
    assert reservation_checks == reservation_migration_checks
    assert order_checks["ck_ordens_checkout_campaign_snapshot_coerente"] == (
        order_coherence
    )

    model_active_indexes = [
        index
        for index in campaign_table.indexes
        if index.name == "uq_checkout_offer_campaigns_offer_active"
    ]
    assert len(model_active_indexes) == 1
    model_active_index = model_active_indexes[0]
    assert model_active_index.unique is True
    assert tuple(column.name for column in model_active_index.columns) == ("offer_id",)
    postgresql_index_ddl = _normalizar_sql(
        CreateIndex(model_active_index).compile(dialect=postgresql.dialect())
    )
    sqlite_index_ddl = _normalizar_sql(
        CreateIndex(model_active_index).compile(dialect=sqlite.dialect())
    )
    assert "create unique index" in postgresql_index_ddl
    assert "where estado = 'active'" in postgresql_index_ddl
    assert "create unique index" in sqlite_index_ddl
    assert "where estado = 'active'" in sqlite_index_ddl
    model_quota_indexes = [
        index
        for index in reservation_table.indexes
        if index.name
        == "ix_checkout_offer_campaign_reservations_camp_estado_expires_at"
    ]
    assert len(model_quota_indexes) == 1
    assert tuple(column.name for column in model_quota_indexes[0].columns) == (
        "campaign_id",
        "estado",
        "expires_at",
    )
    assert model_quota_indexes[0].unique is False

    for relationship in sa_inspect(models.CheckoutOffer).relationships:
        if relationship.mapper.class_ is campaign_model:
            assert "delete" not in relationship.cascade
            assert "delete-orphan" not in relationship.cascade

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _sqlite_foreign_keys)
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    first_campaign = _campanha(
        models,
        identificador=11,
        offer_id=1,
        codigo="launch-small-active",
        estado="active",
        purchase_limit=3,
        reservation_ttl_seconds=17,
        contract_version=2,
    )
    second_campaign = _campanha(
        models,
        identificador=12,
        offer_id=2,
        codigo="launch-other-retired",
        estado="retired",
        purchase_limit=29,
        reservation_ttl_seconds=43,
        contract_version=7,
    )
    draft_same_offer = _campanha(
        models,
        identificador=13,
        offer_id=1,
        codigo="launch-small-draft",
        estado="draft",
    )
    retired_same_offer = _campanha(
        models,
        identificador=14,
        offer_id=1,
        codigo="launch-small-retired",
        estado="retired",
    )
    with Session.begin() as db:
        db.add_all(
            [
                models.User(
                    id=41,
                    email="campaign-owner@example.invalid",
                    hashed_password="hash",
                ),
                models.Empresa(id=301, razao_social="Owned", user_id=41),
                _oferta(models, 1, "tax-monthly-company"),
                _oferta(models, 2, "tax-monthly-company-v2"),
            ]
        )
        db.flush()
        db.add_all(
            [
                first_campaign,
                second_campaign,
                draft_same_offer,
                retired_same_offer,
            ]
        )
        db.flush()
        orders = [
            _ordem(
                models,
                identificador=1,
                offer_id=1,
                offer_code="tax-monthly-company",
            )
        ]
        orders.extend(
            _ordem(
                models,
                identificador=identifier,
                offer_id=1,
                offer_code="tax-monthly-company",
                campaign=first_campaign,
            )
            for identifier in range(2, 6)
        )
        db.add_all(orders)
        db.flush()
        db.add_all(
            [
                _reserva(
                    models,
                    identificador=21,
                    campaign_id=11,
                    ordem_id=2,
                    estado="reserved",
                ),
                _reserva(
                    models,
                    identificador=22,
                    campaign_id=11,
                    ordem_id=3,
                    estado="confirmed",
                ),
                _reserva(
                    models,
                    identificador=23,
                    campaign_id=11,
                    ordem_id=4,
                    estado="released",
                ),
                _reserva(
                    models,
                    identificador=24,
                    campaign_id=11,
                    ordem_id=5,
                    estado="expired",
                ),
            ]
        )

    _assert_integrity_error(
        Session,
        _campanha(
            models,
            identificador=15,
            offer_id=1,
            codigo="launch-second-active",
            estado="active",
        ),
    )

    with Session.begin() as db:
        legacy = db.get(models.OrdemCheckout, 1)
        assert all(
            getattr(legacy, column) is None for column in _ORDER_CAMPAIGN_COLUMNS
        )
        snapshotted = db.get(models.OrdemCheckout, 2)
        assert snapshotted.campaign_id == 11
        assert snapshotted.campaign_code == "launch-small-active"
        assert snapshotted.campaign_contract_version == 2
        assert snapshotted.campaign_purchase_limit == 3
        assert snapshotted.campaign_reservation_expires_at == datetime(
            2026, 9, 3, 12, 5, 0
        )
        campaign = db.get(campaign_model, 11)
        campaign.estado = "retired"
        campaign.purchase_limit = 31
        campaign.contract_version = 3

    with Session() as db:
        unchanged = db.get(models.OrdemCheckout, 2)
        assert unchanged.campaign_code == "launch-small-active"
        assert unchanged.campaign_contract_version == 2
        assert unchanged.campaign_purchase_limit == 3
        assert unchanged.valor == Decimal("49.90")
        assert unchanged.usage_limit is None

    invalid_campaigns = (
        {"codigo": ""},
        {"codigo": " launch-invalid"},
        {"codigo": "launch-invalid "},
        {"codigo": "Launch-invalid"},
        {"codigo": "launch--invalid"},
        {"estado": "published"},
        {"purchase_limit": 0},
        {"purchase_limit": -1},
        {"reservation_ttl_seconds": 0},
        {"reservation_ttl_seconds": -1},
        {"contract_version": 0},
        {"contract_version": -1},
    )
    for offset, changes in enumerate(invalid_campaigns, start=100):
        values = {
            "identificador": offset,
            "offer_id": 2,
            "codigo": f"launch-invalid-{offset}",
        }
        values.update(changes)
        _assert_integrity_error(Session, _campanha(models, **values))
    _assert_integrity_error(
        Session,
        _campanha(
            models,
            identificador=200,
            offer_id=2,
            codigo="launch-other-retired",
        ),
    )
    _assert_integrity_error(
        Session,
        _campanha(
            models,
            identificador=201,
            offer_id=999,
            codigo="launch-missing-offer",
        ),
    )

    invalid_order_changes = (
        {"campaign_code": "launch-small-active"},
        {"campaign_id": 11},
        {
            "campaign_id": 11,
            "campaign_code": "launch-small-active",
            "campaign_contract_version": 2,
            "campaign_purchase_limit": 3,
        },
        {
            "campaign_id": 11,
            "campaign_code": "launch-small-active",
            "campaign_contract_version": 0,
            "campaign_purchase_limit": 3,
            "campaign_reservation_expires_at": datetime(2026, 9, 3, 12, 5, 0),
        },
        {
            "campaign_id": 11,
            "campaign_code": "launch-small-active",
            "campaign_contract_version": 2,
            "campaign_purchase_limit": 0,
            "campaign_reservation_expires_at": datetime(2026, 9, 3, 12, 5, 0),
        },
    )
    for offset, changes in enumerate(invalid_order_changes, start=300):
        _assert_integrity_error(
            Session,
            _ordem(
                models,
                identificador=offset,
                offer_id=1,
                offer_code="tax-monthly-company",
                **changes,
            ),
        )

    invalid_reservations = (
        {"estado": "unknown"},
        {"estado": "reserved", "confirmed_at": datetime(2026, 9, 3, 12, 0, 2)},
        {"estado": "confirmed", "confirmed_at": None},
        {"estado": "confirmed", "released_at": datetime(2026, 9, 3, 12, 0, 3)},
        {"estado": "released", "released_at": None},
        {"estado": "released", "expired_at": datetime(2026, 9, 3, 12, 0, 17)},
        {"estado": "expired", "expired_at": None},
        {"estado": "expired", "confirmed_at": datetime(2026, 9, 3, 12, 0, 2)},
        {"estado": "reserved", "expires_at": datetime(2026, 9, 3, 12, 0, 0)},
    )
    for offset, changes in enumerate(invalid_reservations, start=400):
        values = {
            "identificador": offset,
            "campaign_id": 11,
            "ordem_id": 1,
            "estado": changes["estado"],
        }
        values.update({key: value for key, value in changes.items() if key != "estado"})
        _assert_integrity_error(Session, _reserva(models, **values))
    _assert_integrity_error(
        Session,
        _reserva(
            models,
            identificador=500,
            campaign_id=11,
            ordem_id=2,
            estado="reserved",
        ),
    )
    _assert_integrity_error(
        Session,
        _reserva(
            models,
            identificador=501,
            campaign_id=999,
            ordem_id=1,
            estado="reserved",
        ),
    )
