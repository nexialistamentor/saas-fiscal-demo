"""
Import MVA nacional — Convênio ICMS 142/2018.

Fonte: data/mva/convenio_142_2018.csv (commitado no repo, data de consulta no cabeçalho).

Uso:
  python -m app.scripts.import_mva_convenio_142_2018 --dry-run
  python -m app.scripts.import_mva_convenio_142_2018 --commit
  python -m app.scripts.import_mva_convenio_142_2018 --commit --uf SP
"""

from __future__ import annotations

import argparse
import csv
import logging
from datetime import date
from pathlib import Path

from app.database import SessionLocal
from app.models import TabelaMVA

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "mva" / "convenio_142_2018.csv"
IMPORTADO_POR = "import_mva_convenio_142_2018.py v1.0"


def _parse_date(s: str) -> date | None:
    return date.fromisoformat(s) if s else None


def _aliquota_interna_e_nivel(row: dict) -> tuple[float, str]:
    """
    CSV vazio em aliquota_interna → placeholder 0.0 na BD e marcador de auditoria.
    """
    raw = (row.get("aliquota_interna") or "").strip()
    if not raw:
        return 0.0, "convenio_base_sem_aliquota"
    return float(raw), "convenio_base"


def _linhas_dados_csv(open_file):
    for row in open_file:
        if row.lstrip().startswith("#"):
            continue
        yield row


def importar(commit: bool = False, uf_filtro: str | None = None) -> dict:
    db = SessionLocal()
    inseridos = atualizados = ignorados = 0
    try:
        with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(_linhas_dados_csv(f))
            for row in reader:
                uf = (row.get("csvuf") or row.get("uf") or "").strip().upper()
                if not uf:
                    continue
                if uf_filtro and uf != uf_filtro.upper():
                    continue
                ncm = row["ncm"].strip()
                vi = _parse_date((row.get("vigencia_inicio") or "").strip())
                vf = _parse_date((row.get("vigencia_fim") or "").strip())

                existente = (
                    db.query(TabelaMVA)
                    .filter(
                        TabelaMVA.estado == uf,
                        TabelaMVA.ncm == ncm,
                        TabelaMVA.vigencia_inicio == vi,
                    )
                    .first()
                )
                ali, nivel = _aliquota_interna_e_nivel(row)
                if existente:
                    if existente.nivel_confianca_fonte == "oficial":
                        ignorados += 1
                        continue
                    existente.mva = float(row["mva"])
                    existente.aliquota_interna = ali
                    existente.vigencia_fim = vf
                    existente.fonte_legal = row["fonte_legal"]
                    existente.url_fonte = row.get("url_fonte")
                    existente.nivel_confianca_fonte = nivel
                    existente.importado_por = IMPORTADO_POR
                    atualizados += 1
                else:
                    db.add(
                        TabelaMVA(
                            estado=uf,
                            ncm=ncm,
                            mva=float(row["mva"]),
                            aliquota_interna=ali,
                            vigencia_inicio=vi,
                            vigencia_fim=vf,
                            fonte_legal=row["fonte_legal"],
                            url_fonte=row.get("url_fonte"),
                            nivel_confianca_fonte=nivel,
                            importado_por=IMPORTADO_POR,
                        )
                    )
                    inseridos += 1

        if commit:
            db.commit()
            logger.info(
                "Commit: %d inseridos, %d actualizados, %d ignorados (oficial)",
                inseridos,
                atualizados,
                ignorados,
            )
        else:
            db.rollback()
            logger.info(
                "Dry-run: %d a inserir, %d a actualizar, %d a ignorar (oficial)",
                inseridos,
                atualizados,
                ignorados,
            )
    finally:
        db.close()
    return {"inseridos": inseridos, "atualizados": atualizados, "ignorados": ignorados}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser()
    p.add_argument("--commit", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--uf", default=None)
    args = p.parse_args()
    do_commit = bool(args.commit) and not bool(args.dry_run)
    resultado = importar(commit=do_commit, uf_filtro=args.uf)
    print(resultado)
