import logging
import os
from typing import Generator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

_RAW_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower().strip()

_SSL_MODES_SECURE = frozenset({"require", "verify-ca", "verify-full"})
_SSL_MODES_INSECURE = frozenset({"disable", "allow", "prefer"})
_SSL_MODES_ALL = _SSL_MODES_SECURE | _SSL_MODES_INSECURE


class DatabaseConfigError(Exception):
    """Configuração de banco de dados inválida ou insegura."""


def _parse_scheme(url: str) -> str:
    """Retorna o scheme normalizado da URL de banco (sqlite, postgresql, etc)."""
    parsed = urlparse(url)
    return parsed.scheme.split("+")[0].lower()


def _extract_sslmode(url: str) -> str | None:
    """Extrai sslmode da query string via parsing semântico. Retorna None se ausente."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    values = params.get("sslmode", [])
    if not values:
        return None
    return values[0].lower().strip()


def _inject_sslmode(url: str, mode: str) -> str:
    """Injeta sslmode na query string de forma semântica, sem duplicar."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["sslmode"] = [mode]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _validate_ssl_policy(sslmode: str | None, environment: str) -> str:
    """
    Política centralizada de SSL.

    Retorna o sslmode final validado.
    Levanta DatabaseConfigError se a configuração viola a política do ambiente.

    Política:
      - strict (production, staging):  SSL obrigatório. sslmode inseguro → erro fatal.
                                        Padrão quando ausente: verify-full.
      - development:  Tolerante. Se ausente, injeta 'require'. Inseguro → aviso.
    """
    is_strict = environment in ("production", "staging")

    if sslmode is None:
        resolved = "verify-full" if is_strict else "require"
        logger.info(
            "SSL: sslmode ausente na URL — aplicando política padrão: '%s' (env=%s)",
            resolved, environment,
        )
        return resolved

    if sslmode not in _SSL_MODES_ALL:
        raise DatabaseConfigError(
            f"sslmode='{sslmode}' não é reconhecido. "
            f"Valores válidos: {sorted(_SSL_MODES_ALL)}"
        )

    if sslmode in _SSL_MODES_INSECURE:
        if is_strict:
            raise DatabaseConfigError(
                f"BLOQUEADO: sslmode='{sslmode}' é inseguro para ambiente '{environment}'. "
                f"Valores permitidos: {sorted(_SSL_MODES_SECURE)}"
            )
        logger.warning(
            "SSL: sslmode='%s' é inseguro — tolerado apenas em ambiente '%s'. "
            "NÃO use esta configuração em produção.",
            sslmode, environment,
        )

    logger.info("SSL: usando sslmode='%s' (env=%s)", sslmode, environment)
    return sslmode


def _build_connection_url_and_kwargs(raw_url: str, environment: str) -> tuple[str, dict]:
    """
    Ponto único e auditável de construção da URL final e engine_kwargs.

    Retorna (url_final, engine_kwargs).
    """
    scheme = _parse_scheme(raw_url)
    engine_kwargs: dict = {"pool_pre_ping": True}

    if scheme == "sqlite":
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        logger.info("DB: SQLite detectado — SSL não aplicável (env=%s)", environment)
        return raw_url, engine_kwargs

    if scheme not in ("postgresql", "postgres", "mysql", "mariadb"):
        logger.warning("DB: scheme '%s' não é reconhecido — nenhuma política SSL aplicada", scheme)
        return raw_url, engine_kwargs

    existing_sslmode = _extract_sslmode(raw_url)
    validated_sslmode = _validate_ssl_policy(existing_sslmode, environment)

    final_url = _inject_sslmode(raw_url, validated_sslmode)

    return final_url, engine_kwargs


DATABASE_URL, _engine_kwargs = _build_connection_url_and_kwargs(_RAW_DATABASE_URL, ENVIRONMENT)
engine = create_engine(DATABASE_URL, **_engine_kwargs)


def _set_postgresql_session_timezone_utc(
    dbapi_connection: object,
    _connection_record: object,
    _connection_proxy: object,
) -> None:
    """Reassert UTC durably before a pooled PostgreSQL connection is delivered."""
    original_autocommit = dbapi_connection.autocommit
    cursor = None
    try:
        dbapi_connection.autocommit = True
        cursor = dbapi_connection.cursor()
        cursor.execute("SET SESSION TIME ZONE 'UTC'")
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            dbapi_connection.autocommit = original_autocommit


if _parse_scheme(DATABASE_URL) in ("postgresql", "postgres"):
    event.listen(engine, "checkout", _set_postgresql_session_timezone_utc)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

def _sqlite_add_missing_columns(model_cls: type) -> None:
    """Acrescenta colunas do modelo em falta (histórico: DB criado antes do modelo atual)."""
    table_name = model_cls.__tablename__
    insp = inspect(engine)
    if table_name not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns(table_name)}
    dialect = engine.dialect
    with engine.begin() as conn:
        row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
        for col in model_cls.__table__.columns:
            if col.primary_key or col.name in existing:
                continue
            coltype = col.type.compile(dialect=dialect)
            ddl = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {coltype}"
            if not col.nullable:
                if row_count and col.server_default is None and col.name == "origem_cliente":
                    # 0014 / ADR-005: backfill retroactivo em SQLite de testes (sem migration Alembic)
                    ddl += " NOT NULL DEFAULT 'legado'"
                else:
                    ddl += " NOT NULL"
            conn.execute(text(ddl))


def _sqlite_ensure_alert_effect_idempotency_unique() -> None:
    """Garante UNIQUE fisico da identidade de efeito em SQLite legado."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_alertas_fiscais_effect_idempotency_key "
                "ON alertas_fiscais (effect_idempotency_key)"
            )
        )

def ensure_sqlite_schema_compat() -> None:
    """
    SQLite legado: ``create_all`` não altera tabelas já criadas.
    Alinha colunas das tabelas normativas com os modelos (pytest / test.db).
    Import local de models evita ciclo de import com Alembic.
    """
    if _parse_scheme(DATABASE_URL) != "sqlite":
        return
    from app import models  # import local — evita ciclo com Alembic/env.py

    models.Base.metadata.create_all(bind=engine)
    _sqlite_add_missing_columns(models.TabelaMVA)
    _sqlite_add_missing_columns(models.TabelaPMPF)
    _sqlite_add_missing_columns(models.ContadorEmpresaVinculo)
    _sqlite_add_missing_columns(models.AlertaFiscal)
    _sqlite_ensure_alert_effect_idempotency_unique()


if os.getenv("ALEMBIC_RUNNING") != "1":
    ensure_sqlite_schema_compat()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
