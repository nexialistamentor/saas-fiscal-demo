#!/usr/bin/env python3
"""
Importação SAIF 062/2025 — PMPF MG (Anexo I) a partir do PDF oficial ou ficheiro local.

    python -m app.scripts.import_mg_saif062_pmpf --dry-run
    python -m app.scripts.import_mg_saif062_pmpf --commit

Requer variável de ambiente DATABASE_URL / config igual aos restantes scripts da app.
"""
from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.services.parsers.sefaz_mg_pdf_parser import (
    _URL_PDF_ANEXOS,
    extrair_regras_mg_pdf_de_bytes,
)
from app.services.pipeline_normativo import importar_regras_pmpf


def _carregar_pdf(args: argparse.Namespace) -> bytes:
    if args.pdf:
        return args.pdf.read_bytes()
    import httpx

    r = httpx.get(_URL_PDF_ANEXOS, follow_redirects=True, timeout=120.0)
    r.raise_for_status()
    return r.content


def pathlib_path(s: str):
    from pathlib import Path

    p = Path(s)
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"não é ficheiro: {s}")
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description="Importar PMPF MG (SAIF 062/2025 PDF)")
    ap.add_argument(
        "--pdf",
        type=pathlib_path,
        help="Caminho para port_saif062_2025_anexos.pdf (omitir = URL oficial)",
    )
    ap.add_argument(
        "--commit",
        action="store_true",
        help="Persistir em tabela_pmpf (sem esta flag = dry-run)",
    )
    args = ap.parse_args()
    dry_run = not args.commit

    raw = _carregar_pdf(args)
    regras, erros = extrair_regras_mg_pdf_de_bytes(raw)

    print(f"Linhas extraídas (Anexo I): {len(regras)}")
    if erros:
        print("Avisos / erros do parser:")
        for e in erros[:20]:
            print(f"  - {e}")
        if len(erros) > 20:
            print(f"  ... (+{len(erros) - 20})")

    if regras:
        amostra = regras[:5]
        print("\nPrimeiras 5 regras (resumo):")
        for r in amostra:
            print(
                f"  ncm={r.ncm} pmpf={r.pmpf_reais} marca={r.marca_produto!r} "
                f"emb_ml={r.embalagem_ml} vig_ini={r.vigencia_inicio}"
            )

    res = None
    db = SessionLocal()
    try:
        res = importar_regras_pmpf(db, regras, dry_run=dry_run)
        modo = "DRY-RUN" if dry_run else "COMMIT"
        print(f"\n[{modo}] inseridos={res.inseridos} atualizados={res.atualizados} ignorados={res.ignorados}")
        if res.erros:
            print("Erros validação:")
            for e in res.erros[:30]:
                print(f"  - {e}")
        if dry_run and res is not None and not res.erros and regras:
            print(
                "\nDry-run sem erros de validação. Para gravar na BD: "
                "python -m app.scripts.import_mg_saif062_pmpf --commit"
            )
    finally:
        db.close()

    erros_import = res.erros if res else []
    return 0 if not erros and not erros_import else 1


if __name__ == "__main__":
    sys.exit(main())
