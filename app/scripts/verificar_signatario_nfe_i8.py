"""I8 CLI offline: confere CNPJ no XML + chave + certificado embutido.

Le o ficheiro local, NAO imprime CNPJ, chave, nome, certificados ou XML.
Nao consulta rede, BD, SEFAZ nem valida CA/CRL/OCSP.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from lxml import etree
from app.services.enterprise_nfe_i8_signer_identity import (
    EnterpriseI8IdentityError, vincular_signatario_nfe_i8,
)

_N='{http://www.portalfiscal.inf.br/nfe}'
_MAX=2*1024*1024

def main(argv=None):
    parser=argparse.ArgumentParser(description='Concilia identidade de signatario NF-e offline')
    parser.add_argument('xml_path')
    opts=parser.parse_args(argv)
    try:
        path=Path(opts.xml_path)
        if not path.is_file() or not 0 < path.stat().st_size <= _MAX:
            raise EnterpriseI8IdentityError('I8_CLI_INPUT_INVALID')
        raw=path.read_bytes()
        xml_parser=etree.XMLParser(resolve_entities=False,load_dtd=False,no_network=True,
                                   huge_tree=False,recover=False)
        root=etree.fromstring(raw,parser=xml_parser)
        nfe=root if root.tag==_N+'NFe' else root.find(_N+'NFe') if root.tag==_N+'nfeProc' else None
        if nfe is None:raise EnterpriseI8IdentityError('I8_CLI_NFE_INVALID')
        inf=nfe.find(_N+'infNFe')
        if inf is None:raise EnterpriseI8IdentityError('I8_CLI_INF_INVALID')
        key=(inf.get('Id') or '')
        cnpj=inf.findtext(_N+'emit/'+_N+'CNPJ')
        receipt=vincular_signatario_nfe_i8(xml_bytes=raw,
            chave_nfe_esperada=key[3:] if key.startswith('NFe') else '',
            cnpj_emitente_esperado=cnpj,
            xml_sha256_esperado=hashlib.sha256(raw).hexdigest())
        print('SOLVERIS_I8_OFFLINE_SIGNER_IDENTITY_MATCH_PASS')
        print('XML_SHA256='+receipt['xml_sha256'])
        print('CERT_DER_SHA256='+receipt['certificado_embutido_der_sha256'])
        print('CA_ICP_BRASIL_VERIFICADA=FALSE')
        print('SEFAZ_CONFIRMADA=FALSE')
        print('NO_NETWORK_NO_DB_NO_MEI_NO_PAYMENT_NO_DEPLOY')
        return 0
    except (EnterpriseI8IdentityError,OSError,ValueError,etree.LxmlError):
        print('SOLVERIS_I8_OFFLINE_SIGNER_IDENTITY_NOT_VERIFIED')
        print('NO_SEFAZ_CLAIM_NO_CREDIT_CLAIM')
        return 2

if __name__=='__main__':
    raise SystemExit(main())
