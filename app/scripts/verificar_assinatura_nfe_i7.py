"""CLI opt-in: inspecao offline de assinatura NF-e. Nunca publica chave/CNPJ.

Invocacao manual: python -B -m app.scripts.verificar_assinatura_nfe_i7 <caminho>
Sem rede, banco, SEFAZ ou modificacao do XML; protocolo nao atestado.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re

from app.services.enterprise_nfe_i7_xml_signature import (
    EnterpriseI7SignatureError,
    verificar_assinatura_nfe_i7,
)

_MAX = 2 * 1024 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Verifica a matematica XMLDSig de NF-e local, offline')
    parser.add_argument('xml_path', help='Ficheiro local de XML NF-e, qualquer extensao')
    args = parser.parse_args(argv)
    try:
        path = Path(args.xml_path)
        if not path.is_file() or path.stat().st_size > _MAX or path.stat().st_size < 1:
            raise EnterpriseI7SignatureError('I7_CLI_FILE_INVALID')
        with path.open('rb') as fh:
            raw = fh.read(_MAX + 1)
        if not 0 < len(raw) <= _MAX:
            raise EnterpriseI7SignatureError('I7_CLI_FILE_INVALID')
        candidates = re.findall(rb'\bId\s*=\s*["\']NFe([0-9]{44})["\']', raw)
        if len(candidates) != 1:
            raise EnterpriseI7SignatureError('I7_CLI_NFE_KEY_UNRECOGNIZED')
        key = candidates[0].decode('ascii')
        receipt = verificar_assinatura_nfe_i7(
            xml_bytes=raw, chave_nfe_esperada=key,
            xml_sha256_esperado=hashlib.sha256(raw).hexdigest())
        print('SOLVERIS_I7_OFFLINE_SIGNATURE_MATH_PASS')
        print('XML_SHA256='+receipt['xml_sha256'])
        print('CERT_DER_SHA256='+receipt['certificado_embutido_der_sha256'])
        print('ALGORITMO='+receipt['algoritmo_observado'])
        print('CA_ICP_BRASIL_VERIFICADA=FALSE')
        print('SEFAZ_AUTENTICADA=FALSE')
        print('NO_NETWORK_NO_DB_NO_MEI_NO_PAYMENT_NO_DEPLOY')
        return 0
    except (EnterpriseI7SignatureError, OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, EnterpriseI7SignatureError) else 'I7_CLI_FILE_UNREADABLE'
        print('SOLVERIS_I7_SIGNATURE_NOT_VERIFIED: '+code)
        print('NO_SEFAZ_CLAIM_NO_CREDIT_CLAIM')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
