"""
Orquestrador de parsers normativos.
Executa todos os parsers, submete ao pipeline e regista resultados.
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.database import SessionLocal
from app.services.parsers.dou_parser import DOUParser
from app.services.parsers.sefaz_sp_parser import SefazSPParser
from app.services.parsers.sefaz_mg_parser import SefazMGParser
from app.services.pipeline_normativo import importar_regras

logger = logging.getLogger(__name__)


def executar_parsers(dry_run: bool = True) -> dict:
    """
    Executa todos os parsers disponíveis e submete ao pipeline_normativo.
    dry_run=True por defeito — nunca commita sem confirmação explícita.
    """
    parsers = [
        DOUParser(dias_atras=30),
        SefazSPParser(),
        SefazMGParser(),
    ]

    resumo: dict = {
        "dry_run": dry_run,
        "executado_em": datetime.utcnow().isoformat(),
        "parsers": [],
    }

    db = SessionLocal()
    try:
        for parser in parsers:
            resultado_parser = parser.extrair_seguro()

            if resultado_parser.regras:
                resultado_import = importar_regras(
                    db,
                    resultado_parser.regras,
                    dry_run=dry_run,
                )
                resumo["parsers"].append({
                    "fonte": resultado_parser.fonte,
                    "url": resultado_parser.url_consultada,
                    "regras_extraidas": len(resultado_parser.regras),
                    "inseridos": resultado_import.inseridos,
                    "atualizados": resultado_import.atualizados,
                    "ignorados": resultado_import.ignorados,
                    "erros_parser": resultado_parser.erros,
                    "erros_import": resultado_import.erros,
                })
            else:
                resumo["parsers"].append({
                    "fonte": resultado_parser.fonte,
                    "url": resultado_parser.url_consultada,
                    "regras_extraidas": 0,
                    "erros_parser": resultado_parser.erros,
                })

            if resultado_parser.erros:
                for e in resultado_parser.erros:
                    logger.warning("Parser %s: %s", resultado_parser.fonte, e)

    finally:
        db.close()

    return resumo


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(executar_parsers(dry_run=True), indent=2, ensure_ascii=False))
