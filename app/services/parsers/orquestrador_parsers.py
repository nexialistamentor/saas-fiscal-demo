"""
Orquestrador de parsers normativos.
Executa todos os parsers, submete ao pipeline e regista resultados.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime

from app.database import SessionLocal
from app.services.parsers.dou_dados_abertos_parser import DOUDadosAbertosParser
from app.services.parsers.dou_parser import DOUParser
from app.services.parsers.sefaz_sp_parser import SefazSPParser
from app.services.parsers.sefaz_mg_parser import SefazMGParser
from app.services.pipeline_normativo import importar_regras

logger = logging.getLogger(__name__)


def executar_parsers(dry_run: bool = True) -> dict:
    """
    Executa todos os parsers disponíveis e submete ao pipeline_normativo.
    dry_run=True por defeito — nunca commita sem confirmação explícita.

    Cada item de `parsers` no resumo inclui:
    - estatísticas de import (inseridos / atualizados / ignorados)
    - erros do parser e do pipeline
    - diagnostico HTTP detalhado (status_code, bytes, content_type, preview)
    """
    parsers = [
        DOUDadosAbertosParser(dias_atras=30),
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
            entrada: dict = {
                "fonte": resultado_parser.fonte,
                "url": resultado_parser.url_consultada,
                "regras_extraidas": len(resultado_parser.regras),
                "erros_parser": resultado_parser.erros,
                "diagnostico": [asdict(d) for d in resultado_parser.diagnostico],
            }

            if resultado_parser.regras:
                resultado_import = importar_regras(
                    db,
                    resultado_parser.regras,
                    dry_run=dry_run,
                )
                entrada.update(
                    {
                        "inseridos": resultado_import.inseridos,
                        "atualizados": resultado_import.atualizados,
                        "ignorados": resultado_import.ignorados,
                        "erros_import": resultado_import.erros,
                    }
                )

            resumo["parsers"].append(entrada)

            for d in resultado_parser.diagnostico:
                logger.info(
                    "[%s] %s status=%s bytes=%d ctype=%s",
                    resultado_parser.fonte,
                    d.url,
                    d.status_code,
                    d.bytes_recebidos,
                    d.content_type,
                )
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
