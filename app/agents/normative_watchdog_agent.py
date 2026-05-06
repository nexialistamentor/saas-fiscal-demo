"""
AG3 — NormativeWatchdogAgent: monitoriza a base normativa em busca de
vigências expiradas, fontes sem rastreabilidade e NCMs sem cobertura nacional.
Integra com API do Diário Oficial da União para detecção de novos actos normativos.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List

import httpx
from sqlalchemy import func

from app.database import SessionLocal
from app.models import AlertaFiscal as AlertaFiscalModel
from app.models import Insight

logger = logging.getLogger(__name__)

_DOU_API_URL = "https://www.in.gov.br/consulta/-/buscar/dou"
_DOU_TERMOS = [
    "ICMS",
    "MVA",
    "substituição tributária",
    "Convênio ICMS",
    "alíquota",
]


def _data_ultima_verificacao_dou() -> str:
    """Lê do BD a data do último alerta DOU processado; fallback 30 dias atrás."""
    db = SessionLocal()
    try:
        ultimo = (
            db.query(func.max(AlertaFiscalModel.criado_em))
            .filter(AlertaFiscalModel.tipo == "NOVIDADE_DOU_ICMS_ST")
            .scalar()
        )
        if ultimo:
            return ultimo.strftime("%d-%m-%Y")
    except Exception:
        pass
    finally:
        db.close()
    return (datetime.utcnow() - timedelta(days=30)).strftime("%d-%m-%Y")


_UFS_OBRIGATORIAS = [
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]


def _criar_alerta(tipo: str, descricao: str, nivel: str) -> Dict:
    return {"tipo": tipo, "descricao": descricao, "nivel": nivel}


def _consultar_dou(termo: str, data_de: str) -> list[dict]:
    """
    Consulta API pública do DOU por termo a partir de data_de (YYYY-MM-DD).
    Retorna lista de resultados ou [] em caso de falha.
    """
    try:
        resp = httpx.get(
            _DOU_API_URL,
            params={
                "q": termo,
                "exactDate": "personalizado",
                "initialDate": data_de,
                "finalDate": datetime.utcnow().strftime("%d-%m-%Y"),
                "s": "do1",  # Diário Oficial secção 1
            },
            timeout=10,
            headers={"User-Agent": "SaasFiscalMonitor/1.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("content", []) or []
    except Exception as exc:
        logger.warning("AG3: falha ao consultar DOU (%s): %s", termo, exc)
    return []


class NormativeWatchdogAgent:
    """
    Monitoriza base normativa MVA:
    - Vigências expiradas sem substituto
    - NCMs sem cobertura em UFs obrigatórias
    - Fontes sem rastreabilidade legal
    - Insights com NCMs afectados por nova normativa
    - Novos actos no DOU relevantes para ICMS/ST
    """

    name = "normative_agent"  # mantém o name do registry
    permissions = ["monitor_normative", "read_tabela_mva", "read_insights"]

    async def _persistir_alertas(self, alertas: List[Dict], db) -> None:
        for alerta in alertas:
            existente = (
                db.query(AlertaFiscalModel)
                .filter(
                    AlertaFiscalModel.tipo == alerta["tipo"],
                    AlertaFiscalModel.descricao == alerta["descricao"],
                    AlertaFiscalModel.criado_em >= datetime.utcnow() - timedelta(hours=24),
                )
                .first()
            )
            if not existente:
                db.add(
                    AlertaFiscalModel(
                        tipo=alerta["tipo"],
                        descricao=alerta["descricao"],
                        nivel=alerta["nivel"],
                        agente=self.name,
                    )
                )

    async def run(self, context: Dict) -> Dict:
        alertas: List[Dict] = []
        hoje = date.today()
        tabela: list[dict] = context.get("tabela_normativa", [])

        if not tabela:
            return {
                "agent": self.name,
                "total_alertas": 1,
                "alertas": [
                    _criar_alerta(
                        "BASE_NORMATIVA_AUSENTE",
                        "Base normativa não carregada no contexto.",
                        "critico",
                    )
                ],
                "status": "executado",
            }

        # ── 1. Vigências expiradas sem substituto ────────────────────
        ncm_uf_vigentes: set[tuple] = set()
        for r in tabela:
            vf = r.get("vigencia_fim")
            if vf is None:
                ncm_uf_vigentes.add((r["estado"], r["ncm"]))

        for r in tabela:
            vf = r.get("vigencia_fim")
            if vf and date.fromisoformat(vf) < hoje:
                chave = (r["estado"], r["ncm"])
                if chave not in ncm_uf_vigentes:
                    alertas.append(
                        _criar_alerta(
                            "VIGENCIA_EXPIRADA_SEM_SUBSTITUTO",
                            f"Regra MVA expirada em {vf} para {r['estado']}/{r['ncm']} sem substituto vigente.",
                            "critico",
                        )
                    )

        # ── 2. Fontes sem rastreabilidade ────────────────────────────
        sem_fonte = [
            r
            for r in tabela
            if not r.get("fonte_legal") and r.get("nivel_confianca_fonte") != "sem_fonte"
        ]
        if sem_fonte:
            alertas.append(
                _criar_alerta(
                    "REGRAS_SEM_FONTE_LEGAL",
                    f"{len(sem_fonte)} regras MVA activas sem fonte_legal preenchida.",
                    "alto",
                )
            )

        # ── 3. UFs obrigatórias sem cobertura ────────────────────────
        ufs_com_dados = {
            r["estado"]
            for r in tabela
            if not r.get("vigencia_fim")
            or date.fromisoformat(r["vigencia_fim"]) >= hoje
        }
        ufs_sem_dados = [uf for uf in _UFS_OBRIGATORIAS if uf not in ufs_com_dados]
        if ufs_sem_dados:
            alertas.append(
                _criar_alerta(
                    "UFS_SEM_COBERTURA_MVA",
                    f"{len(ufs_sem_dados)} UFs sem dados MVA vigentes: {', '.join(sorted(ufs_sem_dados))}.",
                    "alto",
                )
            )

        # ── 4. Insights com NCMs afectados por vigência expirada ─────
        ncms_expirados = {
            r["ncm"]
            for r in tabela
            if r.get("vigencia_fim") and date.fromisoformat(r["vigencia_fim"]) < hoje
        }
        if ncms_expirados:
            db = SessionLocal()
            try:
                insights_afectados = (
                    db.query(Insight)
                    .filter(
                        Insight.ncm.in_(list(ncms_expirados)),
                        Insight.superseded == False,  # noqa: E712
                    )
                    .count()
                )
                if insights_afectados:
                    alertas.append(
                        _criar_alerta(
                            "INSIGHTS_COM_NCM_EXPIRADO",
                            f"{insights_afectados} insights activos usam NCMs com vigência MVA expirada — recálculo necessário.",
                            "critico",
                        )
                    )
            except Exception as exc:
                logger.warning("AG3: falha ao verificar insights afectados: %s", exc)
            finally:
                db.close()

        # ── 5. Monitorização DOU ─────────────────────────────────────
        data_ultima_verificacao = context.get(
            "dou_ultima_verificacao",
            _data_ultima_verificacao_dou(),
        )
        novidades_dou: list[str] = []
        for termo in _DOU_TERMOS:
            resultados = _consultar_dou(termo, data_ultima_verificacao)
            for item in resultados[:3]:  # máx 3 por termo para não saturar alertas
                titulo = item.get("title") or item.get("titulo") or "sem título"
                novidades_dou.append(f"[{termo}] {titulo}")

        if novidades_dou:
            alertas.append(
                _criar_alerta(
                    "NOVIDADE_DOU_ICMS_ST",
                    f"{len(novidades_dou)} publicações relevantes no DOU: "
                    + "; ".join(novidades_dou[:5]),
                    "alto",
                )
            )

        db = SessionLocal()
        try:
            await self._persistir_alertas(alertas, db)
            db.commit()
        except Exception as exc:
            logger.error("AG3: erro ao persistir alertas: %s", exc)
        finally:
            db.close()

        return {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
            "ufs_sem_cobertura": ufs_sem_dados,
            "ncms_expirados": list(ncms_expirados),
        }


normative_watchdog_agent = NormativeWatchdogAgent()
