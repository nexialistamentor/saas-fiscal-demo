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
from typing import cast

from app.database import SessionLocal
from app.services.pipeline_normativo import (
    NivelConfianca,
    RegraNormativa,
    ResultadoImport,
    importar_regras,
)

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
    regras: list[RegraNormativa] = []
    res = ResultadoImport()
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
                if vi is None:
                    logger.warning("Linha sem vigencia_inicio válida (uf=%s ncm=%s); ignorada.", uf, ncm)
                    continue
                ali, nivel = _aliquota_interna_e_nivel(row)
                regras.append(
                    RegraNormativa(
                        estado=uf,
                        ncm=ncm,
                        mva=float(row["mva"]),
                        aliquota_interna=ali,
                        vigencia_inicio=vi,
                        vigencia_fim=vf,
                        fonte_legal=row["fonte_legal"],
                        url_fonte=row.get("url_fonte"),
                        nivel_confianca=cast(NivelConfianca, nivel),
                        importado_por=IMPORTADO_POR,
                    )
                )

        res = importar_regras(db, regras, dry_run=not commit)
        if res.erros:
            logger.warning("Erros no pipeline normativo: %s", res.erros)
        if commit:
            logger.info(
                "Commit: %d inseridos, %d actualizados, %d ignorados (oficial)",
                res.inseridos,
                res.atualizados,
                res.ignorados,
            )
        else:
            logger.info(
                "Dry-run: %d a inserir, %d a actualizar, %d a ignorar (oficial)",
                res.inseridos,
                res.atualizados,
                res.ignorados,
            )
    finally:
        db.close()
    return {
        "inseridos": res.inseridos,
        "atualizados": res.atualizados,
        "ignorados": res.ignorados,
        "erros": res.erros,
    }


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
