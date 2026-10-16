"""I4N Enterprise: contrato CLI para uma consulta nacional, operada fora do Python.

Nenhuma rede, BD, certificado, SEFAZ ou cobranca ocorre neste modulo. Atestar
origem TLS/mTLS e autorizacao pertence ao operador Schannel (PowerShell).
O resultado e observacao documental de uma chave, nao apuracao ou credito.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import sys

from app.services.enterprise_nfe_sefaz_nacional_i3n import (
    MAX_RESPONSE_BYTES,
    interpretar_consulta_nfe_nacional,
    preparar_consulta_nfe_nacional,
)

SCHEMA = "ENTERPRISE_NFE_OPERADOR_I4N_V1"


def preparar_execucao_unica(chave_nfe: str) -> dict:
    plan = preparar_consulta_nfe_nacional(chave_nfe)
    return {
        "schema_version": SCHEMA,
        "endpoint": plan["endpoint_oficial_catalogado"],
        "autorizador": plan["autorizador"],
        "uf_emissora": plan["uf_emissora_chave"],
        "action": plan["acao_soap"],
        "ambiente": "producao",
        "chave_sha256": sha256(chave_nfe.encode("ascii")).hexdigest(),
        "soap_sha256": sha256(plan["soap_bytes"]).hexdigest(),
        "soap_base64": base64.b64encode(plan["soap_bytes"]).decode("ascii"),
        "consulta_real_executada": False,
        "checkout_autorizado": False,
    }


def interpretar_observacao_unica(*, chave_nfe: str, resposta_soap: bytes) -> dict:
    """Interpreta uma resposta; NAO aceita atestacoes de transporte externas."""
    plan = preparar_consulta_nfe_nacional(chave_nfe)
    parsed = interpretar_consulta_nfe_nacional(
        resposta_soap=resposta_soap, chave_esperada=chave_nfe,
    )
    return {
        "schema_version": SCHEMA,
        "observacao": "RETORNO_SOAP_INTERPRETADO_SEM_ATESTACAO_DE_TRANSPORTE",
        "endpoint_catalogado": plan["endpoint_oficial_catalogado"],
        "autorizador": plan["autorizador"],
        "uf_emissora": plan["uf_emissora_chave"],
        "chave_sha256": sha256(chave_nfe.encode("ascii")).hexdigest(),
        "resposta_sha256": sha256(resposta_soap).hexdigest(),
        "cstat": parsed["cstat"],
        "situacao_declarada": parsed["situacao_declarada_pela_resposta"],
        "protocolo_declarado": parsed["protocolo_declarado"],
        "momento_interpretacao_utc": datetime.now(timezone.utc).isoformat(),
        "canal_mtls_verificado_por_este_modulo": False,
        "autenticidade_xml_verificada": False,
        "escrituracao_verificada": False,
        "norma_vigente_verificada": False,
        "credito_fiscal_comprovado": False,
        "apuracao_mensal_completa": False,
        "checkout_autorizado": False,
        "uso": "INTERNO_NAO_PUBLICAVEL",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solveris-i4n", description="Planeador/interpretador offline da consulta")
    parser.add_argument("action", choices=("plan", "parse"))
    parser.add_argument("--chave", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "plan":
            out = preparar_execucao_unica(args.chave)
        else:
            data = sys.stdin.buffer.read(MAX_RESPONSE_BYTES + 1)
            out = interpretar_observacao_unica(chave_nfe=args.chave, resposta_soap=data)
        sys.stdout.write(json.dumps(out, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n")
        return 0
    except (TypeError, ValueError, UnicodeError) as exc:
        # Saida nao revela chave, SOAP bruto, URL arbitraria nem certificado.
        sys.stderr.write("STOP_I4N: RESPOSTA_OU_CHAVE_INVALIDA\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
