import logging
import os
from typing import Generator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine
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

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

from app import models  # noqa: F401, E402


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()