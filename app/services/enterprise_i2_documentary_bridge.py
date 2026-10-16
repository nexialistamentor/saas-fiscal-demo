"""I2 Enterprise — ponte read-only entre NF-e persistida e projecao I1.

Prova APENAS integridade interna do XML e vinculo ao sujeito/relatorio/itens.
Nao autentica SEFAZ, EFD, escrita contabil, norma ou cobertura mensal.
Nao toca nas rotas legadas, nao altera motor fiscal nem autoriza checkout.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import re

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from app.models import DocumentoFiscal, Empresa, RelatorioAnalise
from app.services.enterprise_pis_cofins_authority_i1 import (
    projetar_diagnostico_integral_i1,
)
from app.services.enterprise_xml_evidence_binding import (
    KEY as XML_EVIDENCE_KEY,
    validar_vinculo_documento_relatorio,
)
from app.services.resultado_provenance_service import verificar_resultado_persistido

SCHEMA_VERSION = 'ENTERPRISE_I2_DOCUMENTARY_BRIDGE_V1'
_NS = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
_URI = '{http://www.portalfiscal.inf.br/nfe}'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_NFE_KEY = re.compile(r'[0-9]{44}\Z')
_MONEY = re.compile(r'(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?\Z')
_CNPJ = re.compile(r'[0-9]{14}\Z')
_ALLOWED_ICMS = frozenset({'ICMS00', 'ICMS10', 'ICMS20', 'ICMS70', 'ICMS90'})


class EnterpriseI2EvidenceError(ValueError):
    """STOP explicito por falha de identidade ou por evidencia ausente."""


def _stop(code: str):
    raise EnterpriseI2EvidenceError(code)


def _positive_id(value: object) -> bool:
    return type(value) is int and value > 0


def _money(value: object) -> Decimal:
    if type(value) is not str or _MONEY.fullmatch(value) is None:
        _stop('I2_MONEY_XML_INVALID')
    try:
        n = Decimal(value)
    except (InvalidOperation, ValueError):
        _stop('I2_MONEY_XML_INVALID')
    if not n.is_finite() or n < 0:
        _stop('I2_MONEY_XML_INVALID')
    return n


def _db_money(value: object) -> Decimal:
    if value is None or type(value) is bool:
        _stop('I2_ITEM_DB_AMOUNT_MISSING')
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError):
        _stop('I2_ITEM_DB_AMOUNT_INVALID')
    if not n.is_finite() or n < 0 or n.as_tuple().exponent < -2:
        _stop('I2_ITEM_DB_AMOUNT_INVALID')
    return n


def _observed_xml(xml_bytes: bytes, chave_esperada: str, cnpj_esperado: str):
    """Leitura estrita da NF-e e dos itens; SEM atestar base juridica de PIS/Cofins."""
    try:
        root = ET.fromstring(xml_bytes, forbid_dtd=True,
                             forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException, ValueError, TypeError):
        _stop('I2_XML_NOT_PARSEABLE')
    if root.tag not in (_URI + 'NFe', _URI + 'nfeProc'):
        _stop('I2_NOT_NFE')
    nfe_nodes = [root] if root.tag == _URI + 'NFe' else root.findall('nfe:NFe', _NS)
    if len(nfe_nodes) != 1:
        _stop('I2_NFE_CARDINALITY')
    infos = nfe_nodes[0].findall('nfe:infNFe', _NS)
    if len(infos) != 1:
        _stop('I2_INF_NFE_CARDINALITY')
    inf = infos[0]
    if inf.get('Id') != 'NFe' + chave_esperada or _NFE_KEY.fullmatch(chave_esperada) is None:
        _stop('I2_NFE_KEY_MISMATCH')
    protocols = root.findall('.//nfe:infProt', _NS)
    if len(protocols) > 1 or (protocols and
        protocols[0].findtext('nfe:chNFe', namespaces=_NS) != chave_esperada):
        _stop('I2_PROTOCOL_KEY_MISMATCH')
    emitter = inf.findtext('nfe:emit/nfe:CNPJ', namespaces=_NS)
    if emitter != cnpj_esperado or _CNPJ.fullmatch(cnpj_esperado) is None:
        _stop('I2_EMITTER_CNPJ_MISMATCH')
    if inf.findtext('nfe:ide/nfe:tpNF', namespaces=_NS) != '1':
        _stop('I2_ONLY_OUTGOING_NFE')
    if inf.findtext('nfe:ide/nfe:finNFe', namespaces=_NS) != '1':
        _stop('I2_ONLY_NORMAL_NFE')
    stamp = inf.findtext('nfe:ide/nfe:dhEmi', namespaces=_NS)
    if type(stamp) is not str:
        _stop('I2_ISSUE_DATE_MISSING')
    try:
        issue = datetime.fromisoformat(stamp).date()
    except (ValueError, TypeError):
        _stop('I2_ISSUE_DATE_INVALID')
    if not date(2000, 1, 1) <= issue <= date(2100, 12, 31):
        _stop('I2_ISSUE_DATE_INVALID')
    vnf = _money(inf.findtext('nfe:total/nfe:ICMSTot/nfe:vNF', namespaces=_NS))
    if vnf <= 0:
        _stop('I2_TOTAL_MISSING')
    deta = inf.findall('nfe:det', _NS)
    if not deta or len(deta) > 500:
        _stop('I2_ITEMS_CARDINALITY')
    signatures, items = [], []
    for idx, det in enumerate(deta, 1):
        if det.get('nItem') != str(idx):
            _stop('I2_ITEM_NUMBER_MISMATCH')
        prod = det.find('nfe:prod', _NS)
        icms = det.find('nfe:imposto/nfe:ICMS', _NS)
        if prod is None or icms is None or len(icms) != 1:
            _stop('I2_ICMS_ITEM_NOT_EVALUABLE')
        group = icms[0]
        if group.tag not in {_URI + n for n in _ALLOWED_ICMS}:
            _stop('I2_ICMS_PROPRIO_NOT_OBSERVED')
        amount_text = group.findtext('nfe:vICMS', namespaces=_NS)
        base_text = group.findtext('nfe:vBC', namespaces=_NS)
        if amount_text is None or base_text is None:
            _stop('I2_ICMS_PROPRIO_NOT_OBSERVED')
        proper = _money(amount_text)
        tax_base = _money(base_text)
        if proper > tax_base or tax_base == 0 and proper > 0:
            _stop('I2_ICMS_ITEM_INCOHERENT')
        price = _money(prod.findtext('nfe:vProd', namespaces=_NS))
        ncm = prod.findtext('nfe:NCM', namespaces=_NS)
        cfop = prod.findtext('nfe:CFOP', namespaces=_NS)
        if (type(ncm) is not str or not re.fullmatch('[0-9]{8}', ncm)
                or type(cfop) is not str or not re.fullmatch('[56][0-9]{3}', cfop)):
            _stop('I2_ITEM_CLASSIFICATION_UNSUPPORTED')
        st_text = group.findtext('nfe:vST', namespaces=_NS)
        if st_text is None:
            st_text = group.findtext('nfe:vICMSST', namespaces=_NS)
        st = _money(st_text) if st_text is not None else None
        signatures.append((ncm, cfop, price, proper))
        items.append({'nItem': idx, 'ncm': ncm, 'cfop': cfop,
                      'valor_produto_observado': str(price),
                      'icms_proprio_observado': str(proper),
                      'icms_st_separado_observado': str(st) if st is not None else None})
    # vNF contem descontos/frete/outros tributos em muitas NF-es; a I2 cobre
    # somente o subconjunto de amostras em que todos os itens reconciliam.
    if sum((x[2] for x in signatures), Decimal('0')) != vnf:
        _stop('I2_DOC_TOTAL_NOT_EQUAL_ITEM_PRODUCTS')
    return {'competencia': issue.strftime('%Y-%m'), 'data_emissao': issue,
            'total_produtos': vnf, 'icms_proprio': sum((x[3] for x in signatures), Decimal('0')),
            'itens': items, 'assinaturas': signatures}


def projetar_diagnostico_integral_i2(*, db: object, authenticated_user_id: int,
                                     empresa_id: int, relatorio_id: int,
                                     xml_bytes: bytes) -> dict:
    """Fronteira EXCLUSIVAMENTE interna; exige posse, integridade e itens.

    O unico XML documentado nao autoriza somar faturacao mensal, excluir ICMS
    juridicamente ou interpretar NF-e como escritura fiscal. A simulacao I1
    continua apenas condicional, nunca disponivel para venda.
    """
    if (db is None or not all(_positive_id(x) for x in
        (authenticated_user_id, empresa_id, relatorio_id))
        or type(xml_bytes) is not bytes or not (0 < len(xml_bytes) <= 2 * 1024 * 1024)):
        _stop('I2_INPUT_INVALID')
    try:
        empresa = db.get(Empresa, empresa_id)
        rel = db.get(RelatorioAnalise, relatorio_id)
    except Exception:
        _stop('I2_DB_READ_FAILED')
    if (empresa is None or empresa.id != empresa_id or empresa.user_id != authenticated_user_id
        or getattr(empresa, 'optante_mei', None) is True or
        getattr(empresa, 'regime_tributario', None) not in ('real', 'presumido')):
        _stop('I2_SUBJECT_REGIME_OR_OWNER_INVALID')
    if (rel is None or rel.id != relatorio_id or rel.user_id != authenticated_user_id
        or rel.empresa_id != empresa_id or rel.analysis_type != 'xml_analise'
        or rel.status != 'ok'):
        _stop('I2_REPORT_OWNER_OR_STATUS_INVALID')
    try:
        resultado = verificar_resultado_persistido(rel)
    except Exception:
        _stop('I2_REPORT_FINGERPRINT_INVALID')
    if type(resultado) is not dict or resultado.get('empresa_id') != empresa_id:
        _stop('I2_RESULT_COMPANY_MISMATCH')
    binding = resultado.get(XML_EVIDENCE_KEY)
    documento_id = binding.get('documento_id') if type(binding) is dict else None
    if not _positive_id(documento_id):
        _stop('I2_NO_BOUND_DOCUMENT')
    try:
        doc = db.get(DocumentoFiscal, documento_id)
    except Exception:
        _stop('I2_DB_READ_FAILED')
    if (doc is None or doc.id != documento_id or doc.empresa_id != empresa_id
        or doc.usuario_id != authenticated_user_id or doc.tipo != 'saida'):
        _stop('I2_DOCUMENT_OWNER_OR_TYPE_INVALID')
    if not validar_vinculo_documento_relatorio(rel, doc, empresa_id=empresa_id):
        _stop('I2_XML_REPORT_BINDING_INVALID')
    digest = hashlib.sha256(xml_bytes).hexdigest()
    stored = getattr(doc, 'conteudo_sha256', None)
    if (type(stored) is not str or _SHA.fullmatch(stored) is None
        or not hmac.compare_digest(digest, stored)):
        _stop('I2_BYTES_HASH_MISMATCH')
    observed = _observed_xml(xml_bytes, binding['xml_chave'], empresa.cnpj)
    if (doc.cnpj_emitente != empresa.cnpj or doc.chave_nfe != binding['xml_chave']
        or getattr(doc, 'data_emissao', None) != observed['data_emissao']
        or type(resultado.get('dados_fiscais')) is not dict
        or resultado['dados_fiscais'].get('cnpj_emitente') != empresa.cnpj):
        _stop('I2_DOCUMENT_XML_METADATA_MISMATCH')
    orm_items = getattr(doc, 'itens', None)
    if not isinstance(orm_items, (list, tuple)) or len(orm_items) != len(observed['itens']):
        _stop('I2_ITEM_DB_CARDINALITY_MISMATCH')
    db_signatures = Counter()
    for row in orm_items:
        if not _positive_id(getattr(row, 'id', None)) or row.documento_id != documento_id:
            _stop('I2_ITEM_DB_IDENTITY_INVALID')
        db_signatures[(row.ncm, row.cfop, _db_money(row.valor_produto),
                       _db_money(row.valor_icms))] += 1
    if db_signatures != Counter(observed['assinaturas']):
        _stop('I2_ITEM_DB_XML_MISMATCH')

    evidence = {'empresa_id': empresa_id, 'regime': empresa.regime_tributario,
                'competencia': observed['competencia'], 'documentos': [{
                    'empresa_id': empresa_id, 'documento_id': documento_id,
                    'sha256': digest, 'competencia': observed['competencia'],
                    'tipo_operacao': 'saida', 'papel_empresa': 'emitente',
                    'modalidade_icms': 'ICMS_PROPRIO',
                    'receita_documental': str(observed['total_produtos']),
                    'icms_proprio_documental': str(observed['icms_proprio'])}]}
    # A I1 recebe apenas valores extraidos de bytes ligados a relatorio e itens;
    # nao aceita inputs monetarios fornecidos livremente pelo chamador.
    projection = projetar_diagnostico_integral_i1(
        resultado=resultado, empresa_id=empresa_id, evidencia_documental=evidence,
    )
    projection['schema_version'] = SCHEMA_VERSION
    projection['uso'] = 'INTERNO_NAO_PUBLICAVEL'
    projection['checkout_autorizado'] = False
    projection['diagnostico_empresarial_completo'] = False
    projection['comprovacao_normativa'] = False
    projection['documental_i2'] = {
        'estado': 'DOCUMENTO_INTERNO_RECONCILIADO',
        'limite': 'NF_E_UNICA_NAO_COMPROVA_FATURACAO_DA_COMPETENCIA',
        'autenticidade_sefaz_verificada': False,
        'escrituracao_efd_verificada': False,
        'norma_vigente_verificada': False,
        'recolhimento_verificado': False,
        'credibilidade_credito_fiscal': False,
        'documento_id': documento_id, 'relatorio_id': relatorio_id,
        'xml_sha256': digest, 'chave_nfe': binding['xml_chave'],
        'competencia_observada': observed['competencia'],
        'itens_xml_observados': observed['itens'],
    }
    return projection


__all__ = ['SCHEMA_VERSION', 'EnterpriseI2EvidenceError',
           'projetar_diagnostico_integral_i2']
