"""Persist explicitly informed revenue, with owner validation and replay safety.

The caller supplies authenticated usuario_id, never a browser-provided actor.
Flushes only; transaction commit belongs to the caller. No provider calls.
"""
from datetime import date
from decimal import Decimal
import re
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app import models

_VALUE = re.compile(r"(?:0|[1-9][0-9]{0,12})\.[0-9]{2}", re.ASCII)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", re.ASCII)

class MeiReceitaInformadaWriterError(ValueError):
    """Sanitized error; no database or input details."""

class MeiReceitaInformadaWriter:
    def __init__(self, db):
        self._db = db

    def registrar(self, *, empresa_id, usuario_id, identidade_receita,
                  data_receita, valor, categoria):
        for value in (empresa_id, usuario_id):
            if type(value) is not int or value <= 0:
                self._fail()
        if type(identidade_receita) is not str:
            self._fail()
        try:
            identity = UUID(identidade_receita)
        except (ValueError, AttributeError):
            self._fail()
        if str(identity) != identidade_receita or identity.version != 4:
            self._fail()
        if type(data_receita) is not str or not _DATE.fullmatch(data_receita):
            self._fail()
        try:
            emitted = date.fromisoformat(data_receita)
        except ValueError:
            self._fail()
        if emitted.year < 1900:
            self._fail()
        if type(valor) is not str or not _VALUE.fullmatch(valor):
            self._fail()
        if type(categoria) is not str or categoria not in ("comercio_industria", "servicos"):
            self._fail()
        amount = Decimal(valor)
        try:
            company = self._db.scalar(select(models.Empresa).where(
                models.Empresa.id == empresa_id,
                models.Empresa.user_id == usuario_id,
            ))
            if company is None or company.regime_tributario != "mei" or company.status_empresa != "ativa":
                self._fail()
            existing = self._find(empresa_id, identidade_receita)
            if existing is not None:
                return self._replay(existing, usuario_id, emitted, amount, categoria)
            row = models.MeiReceitaInformada(
                empresa_id=empresa_id, usuario_id=usuario_id,
                identidade_receita=identidade_receita, data_receita=emitted,
                valor=amount, categoria=categoria, origem="informada_sem_nota",
            )
            try:
                # sqlite3 legacy mode may release the first SAVEPOINT as a
                # commit unless an outer transaction actually began.
                connection = self._db.connection()
                if connection.dialect.name == "sqlite":
                    driver = connection.connection.driver_connection
                    if not driver.in_transaction:
                        connection.exec_driver_sql("BEGIN")
                with self._db.begin_nested():
                    self._db.add(row)
                    self._db.flush()
            except IntegrityError:
                existing = self._find(empresa_id, identidade_receita)
                if existing is None:
                    self._fail()
                return self._replay(existing, usuario_id, emitted, amount, categoria)
            return row
        except SQLAlchemyError:
            raise MeiReceitaInformadaWriterError("RECEITA_INFORMADA_RECUSADA") from None

    def _find(self, empresa_id, identity):
        return self._db.scalar(select(models.MeiReceitaInformada).where(
            models.MeiReceitaInformada.empresa_id == empresa_id,
            models.MeiReceitaInformada.identidade_receita == identity,
        ))

    @classmethod
    def _replay(cls, row, usuario_id, emitted, amount, categoria):
        if (row.usuario_id != usuario_id or row.data_receita != emitted
                or row.valor != amount or row.categoria != categoria
                or row.origem != "informada_sem_nota"):
            cls._fail()
        return row

    @staticmethod
    def _fail():
        raise MeiReceitaInformadaWriterError("RECEITA_INFORMADA_RECUSADA")
