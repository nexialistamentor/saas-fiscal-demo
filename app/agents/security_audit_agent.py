"""
AG4 — SecurityAuditAgent: detecta padrões suspeitos de uso a partir de request_logs.
"""
from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import func

from app.database import SessionLocal
from app.models import RequestLog

_JANELA_MINUTOS = 60
_MAX_CONTAS_POR_IP = 3
_MAX_REQUESTS_POR_USER = 100


def _criar_alerta(tipo: str, descricao: str, nivel: str) -> Dict:
    return {"tipo": tipo, "descricao": descricao, "nivel": nivel}


class SecurityAuditAgent:
    """Monitoriza request_logs em busca de padrões de abuso e scraping."""

    name = "security_audit_agent"
    permissions = ["read_request_logs"]

    async def run(self, context: Dict) -> Dict:
        alertas: List[Dict] = []
        since = datetime.utcnow() - timedelta(minutes=_JANELA_MINUTOS)

        db = SessionLocal()
        try:
            # 1. Mesmo IP em múltiplas contas (>3 user_id distintos/hora por IP)
            rows = (
                db.query(RequestLog.ip, func.count(func.distinct(RequestLog.user_id)))
                .filter(RequestLog.criado_em >= since, RequestLog.user_id.isnot(None))
                .group_by(RequestLog.ip)
                .having(
                    func.count(func.distinct(RequestLog.user_id)) > _MAX_CONTAS_POR_IP
                )
                .all()
            )
            for ip, total in rows:
                alertas.append(
                    _criar_alerta(
                        "multi_conta_por_ip",
                        f"IP {ip} acedeu a {total} contas distintas na última hora.",
                        "critico",
                    )
                )

            # 2. Volume anormal por utilizador (>100 requests/hora)
            rows = (
                db.query(RequestLog.user_id, func.count(RequestLog.id))
                .filter(RequestLog.criado_em >= since, RequestLog.user_id.isnot(None))
                .group_by(RequestLog.user_id)
                .having(func.count(RequestLog.id) > _MAX_REQUESTS_POR_USER)
                .all()
            )
            for user_id, total in rows:
                alertas.append(
                    _criar_alerta(
                        "volume_anormal",
                        f"Utilizador {user_id} fez {total} requests na última hora.",
                        "alto",
                    )
                )

            # 3. Scraping — requests sem User-Agent
            total_sem_ua = (
                db.query(func.count(RequestLog.id))
                .filter(
                    RequestLog.criado_em >= since,
                    (RequestLog.user_agent.is_(None)) | (RequestLog.user_agent == ""),
                )
                .scalar()
            )
            if total_sem_ua and total_sem_ua > 20:
                alertas.append(
                    _criar_alerta(
                        "scraping_sem_user_agent",
                        f"{total_sem_ua} requests sem User-Agent na última hora.",
                        "medio",
                    )
                )

        except Exception as exc:
            alertas.append(
                _criar_alerta(
                    "erro_auditoria",
                    f"SecurityAuditAgent falhou ao consultar logs: {exc}",
                    "medio",
                )
            )
        finally:
            db.close()

        return {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
        }


security_audit_agent = SecurityAuditAgent()
