
"""

app/agents/readers/ag_encerramento.py — ADR-010 B14.3B.

Implementação SQLAlchemy do EncerramentoPendenciaReader.

Síncrono por reflectir sqlalchemy.orm.Session.

Nunca devolve ORM, sessão, str(exc) nem traceback.

Nunca executa escrita. Nunca transporta Session entre threads.

"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.contracts.ag_encerramento import (
    EncerramentoAccessDeniedError,
    EncerramentoDataUnavailableError,
    EncerramentoPendenciaSnapshot,
)
from app.models import Empresa, Insight, RelatorioAnalise


class AgEncerramentoReader:
    """
    Reader soberano read-only para o canário AgEncerramentoAgent (MEI).

    A sessão é injectada no construtor e nunca sai deste módulo.
    Todas as consultas correm dentro de no_autoflush para prevenir
    escrita implícita.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def obter_snapshot(
        self,
        *,
        tenant_id: int,
        actor_id: int,
        empresa_id: int,
        reference_at: datetime,
    ) -> EncerramentoPendenciaSnapshot:
        """
        Devolve um snapshot factual imutável das pendências da empresa.

        Levanta:
            EncerramentoAccessDeniedError:
                empresa inexistente, não autorizada ou identidade divergente.

            EncerramentoDataUnavailableError:
                falha técnica, parâmetros inválidos ou dados inconsistentes.
        """
        try:
            return self._obter_snapshot_interno(
                tenant_id=tenant_id,
                actor_id=actor_id,
                empresa_id=empresa_id,
                reference_at=reference_at,
            )
        except EncerramentoAccessDeniedError:
            raise
        except EncerramentoDataUnavailableError:
            raise
        except Exception:
            raise EncerramentoDataUnavailableError() from None

    def _obter_snapshot_interno(
        self,
        *,
        tenant_id: int,
        actor_id: int,
        empresa_id: int,
        reference_at: datetime,
    ) -> EncerramentoPendenciaSnapshot:
        # Defesa em profundidade da identidade e do isolamento de tenant.
        # type(...) is int rejeita bool, pois bool é subclasse de int.
        if (
            type(tenant_id) is not int
            or tenant_id <= 0
            or type(actor_id) is not int
            or actor_id <= 0
            or actor_id != tenant_id
        ):
            raise EncerramentoAccessDeniedError() from None

        if type(empresa_id) is not int or empresa_id <= 0:
            raise EncerramentoDataUnavailableError() from None

        if (
            not isinstance(reference_at, datetime)
            or reference_at.tzinfo is None
            or reference_at.utcoffset() != timedelta(0)
        ):
            raise EncerramentoDataUnavailableError() from None

        with self._db.no_autoflush:
            # Verificação inicial de autorização.
            empresa_autorizada = (
                self._db.query(Empresa.id)
                .filter(
                    Empresa.id == empresa_id,
                    Empresa.user_id == tenant_id,
                )
                .first()
            )

            if empresa_autorizada is None:
                raise EncerramentoAccessDeniedError() from None

            # Predicado repetido em todas as consultas fiscais para reduzir
            # a janela entre autorização e utilização do recurso.
            empresa_autorizada_exists = (
                self._db.query(Empresa.id)
                .filter(
                    Empresa.id == empresa_id,
                    Empresa.user_id == tenant_id,
                )
                .exists()
            )

            # Query 1 — contagem de insights activos.
            total_insights_raw = (
                self._db.query(func.count(Insight.id))
                .filter(
                    Insight.empresa_id == empresa_id,
                    Insight.superseded.is_(False),
                    empresa_autorizada_exists,
                )
                .scalar()
            )

            total_insights_ativos = (
                0 if total_insights_raw is None else total_insights_raw
            )

            if (
                type(total_insights_ativos) is not int
                or total_insights_ativos < 0
            ):
                raise EncerramentoDataUnavailableError() from None

            # Query 2 — consulta agregada única dos relatórios.
            # MAX ignora NULL por definição SQL.
            total_relatorios, ultimo_created_at = (
                self._db.query(
                    func.count(RelatorioAnalise.id),
                    func.max(RelatorioAnalise.created_at),
                )
                .filter(
                    RelatorioAnalise.empresa_id == empresa_id,
                    empresa_autorizada_exists,
                )
                .one()
            )

            if type(total_relatorios) is not int or total_relatorios < 0:
                raise EncerramentoDataUnavailableError() from None

            # Determinação soberana do estado temporal.
            if total_relatorios == 0:
                estado = "ausente"
                ultimo_relatorio_em = None

            elif ultimo_created_at is None:
                estado = "timestamp_ausente"
                ultimo_relatorio_em = None

            elif not isinstance(ultimo_created_at, datetime):
                raise EncerramentoDataUnavailableError() from None

            elif (
                ultimo_created_at.tzinfo is None
                or ultimo_created_at.utcoffset() is None
            ):
                # Datetime naïve: nunca atribuir timezone por hipótese.
                estado = "timestamp_naive"
                ultimo_relatorio_em = None

            else:
                # Datetime aware: normalização legítima para UTC.
                estado = "timestamp_aware"
                ultimo_relatorio_em = ultimo_created_at.astimezone(
                    timezone.utc
                )

            # Reconfirmação final antes de libertar o snapshot.
            reconfirmacao = (
                self._db.query(Empresa.id)
                .filter(
                    Empresa.id == empresa_id,
                    Empresa.user_id == tenant_id,
                )
                .first()
            )

            if reconfirmacao is None:
                raise EncerramentoAccessDeniedError() from None

        return EncerramentoPendenciaSnapshot(
            empresa_id=empresa_id,
            reference_at=reference_at,
            total_insights_ativos=total_insights_ativos,
            estado_ultimo_relatorio=estado,
            ultimo_relatorio_em=ultimo_relatorio_em,
        )