"""SOLVERIS Enterprise G1.13-C3: temporally select PDF-observed MVA candidates.

Evidence is bound to exact original PDF bytes, page text and an unambiguous
literal row. Selection is bounded to the independently declared observation
window; NEVER proves legal applicability, retrospective exhaustive changes,
actual NF-e ownership, confirmed credit, or payment eligibility.

Read-only, opt-in; no ORM/database, no external requests, no filesystem writes.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
from io import BytesIO
import re
from urllib.parse import urlsplit

from pypdf import PdfReader

SCHEMA = 'SOLVERIS_ENTERPRISE_G113_C3_TEMPORAL_MVA_EVIDENCE_V1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_NCM = re.compile(r'[0-9]{8}\Z')
_CEST = re.compile(r'[0-9]{7}\Z')
_MVA = re.compile(r'(?:0|[1-9][0-9]{0,2})\.[0-9]{2}\Z')
_NUMBER = re.compile(r'(?<![0-9])([0-9]{1,3})[ \t]*,[ \t]*([0-9]{2})(?![0-9])')
_FIELDS = frozenset({
    'versao_id', 'uf', 'ncm', 'cest', 'descricao_marcador',
    'source_url', 'pdf_sha256', 'pagina_1_based', 'pagina_texto_sha256',
    'inicio_caracter', 'excerto_sha256', 'proximo_cest',
    'numero_proxima_linha', 'mva_original_percentual',
    'vigencia_inicio_declarada', 'vigencia_fim_declarada',
    'observacao_inicio', 'observacao_fim', 'dispositivo_declarado',
})
_RESTRICTED = (
    'fonte_primaria_autenticada', 'vigencia_juridica_comprovada',
    'completude_alteracoes_posteriores', 'aplicabilidade_st_comprovada',
    'condicoes_operacionais_comprovadas', 'aliquota_interna_comprovada',
    'reconciliacao_monetaria_com_nf_e', 'autoridade_fiscal',
    'credito_confirmado', 'checkout_autorizado', 'usavel_comercialmente',
)

class G113C3EvidenceError(ValueError):
    """STOP on malformed or inconsistent evidence, never return a false proof."""


def _stop(reason):
    raise G113C3EvidenceError('G113_C3_' + reason)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _sha(s):
    return type(s) is str and _SHA.fullmatch(s) is not None


def _iso(s):
    if type(s) is not str:
        _stop('DATA_INVALIDA')
    try:
        value = date.fromisoformat(s)
    except ValueError:
        _stop('DATA_INVALIDA')
    if value.isoformat() != s:
        _stop('DATA_NAO_CANONICA')
    return value


def _url(s):
    if type(s) is not str or not 1 <= len(s) <= 2048 or '\\' in s:
        return False
    try:
        p = urlsplit(s)
        return (p.scheme == 'https' and bool(p.hostname) and p.port in (None, 443)
                and p.username is None and p.password is None and not p.fragment
                and not p.query and p.path.lower().endswith('.pdf'))
    except ValueError:
        return False


def _mva(s):
    if type(s) is not str or _MVA.fullmatch(s) is None:
        _stop('MVA_FORMATO_INVALIDO')
    try:
        value = Decimal(s)
    except InvalidOperation:
        _stop('MVA_DECIMAL_INVALIDA')
    if not value.is_finite() or value < 0 or value > 999:
        _stop('MVA_FORA_LIMITES')
    return value


def _evidence(v):
    if type(v) is not dict or set(v) != _FIELDS:
        _stop('CONTRATO_EVIDENCIA_INVALIDO')
    if (type(v['versao_id']) is not str or not 1 <= len(v['versao_id']) <= 100
        or type(v['uf']) is not str or not re.fullmatch(r'[A-Z]{2}', v['uf'])
        or type(v['ncm']) is not str or _NCM.fullmatch(v['ncm']) is None
        or type(v['cest']) is not str or _CEST.fullmatch(v['cest']) is None
        or type(v['proximo_cest']) is not str or _CEST.fullmatch(v['proximo_cest']) is None
        or v['proximo_cest'] == v['cest']
        or type(v['descricao_marcador']) is not str or not 3 <= len(v['descricao_marcador']) <= 60
        or type(v['dispositivo_declarado']) is not str or not 3 <= len(v['dispositivo_declarado']) <= 200
        or not _url(v['source_url'])
        or any(not _sha(v[k]) for k in ('pdf_sha256', 'pagina_texto_sha256', 'excerto_sha256'))
        or type(v['pagina_1_based']) is not int or not 1 <= v['pagina_1_based'] <= 800
        or type(v['inicio_caracter']) is not int or not 0 <= v['inicio_caracter'] <= 200000
        or type(v['numero_proxima_linha']) is not int or not 1 <= v['numero_proxima_linha'] <= 9999):
        _stop('CAMPOS_EVIDENCIA_INVALIDOS')
    start = _iso(v['observacao_inicio'])
    end = _iso(v['observacao_fim'])
    valid_start = (_iso(v['vigencia_inicio_declarada'])
                   if v['vigencia_inicio_declarada'] is not None else None)
    valid_end = (_iso(v['vigencia_fim_declarada'])
                 if v['vigencia_fim_declarada'] is not None else None)
    if (start > end or valid_start is not None and valid_end is not None and valid_start > valid_end
        or valid_start is not None and start < valid_start
        or valid_end is not None and end > valid_end):
        _stop('JANELA_FORA_DA_VIGENCIA_DECLARADA')
    return _mva(v['mva_original_percentual']), start, end


def _row(pdf, evidence, cache):
    url = evidence['source_url']
    if url not in pdf:
        _stop('PDF_FONTE_AUSENTE')
    raw = pdf[url]
    if type(raw) is not bytes or not 1024 <= len(raw) <= 40 * 1024 * 1024:
        _stop('PDF_BYTES_INVALIDOS')
    if not raw.startswith(b'%PDF-') or not hmac.compare_digest(_digest(raw), evidence['pdf_sha256']):
        _stop('PDF_SHA256_DIVERGENTE')
    if url not in cache:
        try:
            reader = PdfReader(BytesIO(raw), strict=True)
            total = len(reader.pages)
        except Exception as exc:
            raise G113C3EvidenceError('G113_C3_PDF_NAO_PARSEAVEL') from exc
        if not 1 <= total <= 800:
            _stop('PAGINACAO_NAO_SUPORTADA')
        cache[url] = (reader, {})
    reader, pages = cache[url]
    index = evidence['pagina_1_based'] - 1
    if index >= len(reader.pages):
        _stop('PAGINA_FORA_DO_PDF')
    if index not in pages:
        try:
            text = reader.pages[index].extract_text(extraction_mode='plain')
        except Exception as exc:
            raise G113C3EvidenceError('G113_C3_PAGINA_NAO_EXTRAIVEL') from exc
        if type(text) is not str or not text:
            _stop('PAGINA_SEM_TEXTO')
        pages[index] = text
    text = pages[index]
    if not hmac.compare_digest(_digest(text.encode('utf-8')), evidence['pagina_texto_sha256']):
        _stop('PAGINA_SHA256_DIVERGENTE')
    # Text extraction order and whitespace are evidence-specific, not guessed.
    this_cest = f"{evidence['cest'][:2]}.{evidence['cest'][2:5]}.{evidence['cest'][5:]}"
    next_cest = f"{evidence['proximo_cest'][:2]}.{evidence['proximo_cest'][2:5]}.{evidence['proximo_cest'][5:]}"
    if text.count(this_cest) != 1 or text.count(next_cest) != 1:
        _stop('CEST_NAO_UNICO')
    start = text.index(this_cest)
    end = text.index(next_cest)
    if end <= start or start != evidence['inicio_caracter']:
        _stop('POSICAO_CEST_DIVERGENTE')
    region = text[start:end]
    if not 25 <= len(region) <= 3000:
        _stop('LINHA_TEXTO_TAMANHO_INVALIDO')
    digits_ncm = f"{evidence['ncm'][:4]}.{evidence['ncm'][4:6]}.{evidence['ncm'][6:]}"
    if region.count(digits_ncm) != 1 or evidence['descricao_marcador'].casefold() not in region.casefold():
        _stop('PRODUTO_NCM_NAO_COTEJADOS')
    hits = list(_NUMBER.finditer(region))
    if len(hits) != 1:
        _stop('MVA_NAO_UNICA_NO_EXCERTO')
    hit = hits[0]
    observed = Decimal(hit.group(1) + '.' + hit.group(2))
    if observed != _mva(evidence['mva_original_percentual']):
        _stop('MVA_TEXTO_REGRA_DIVERGENTE')
    trailing = region[hit.end():].strip()
    if trailing != str(evidence['numero_proxima_linha']):
        _stop('LINHA_SEGUINTE_CONTAMINADA')
    excerpt = region[:hit.end()].strip()
    if not 25 <= len(excerpt) <= 1600 or text.count(excerpt) != 1:
        _stop('EXCERTO_NAO_UNICO')
    if not hmac.compare_digest(_digest(excerpt.encode('utf-8')), evidence['excerto_sha256']):
        _stop('EXCERTO_SHA256_DIVERGENTE')
    return excerpt


def selecionar_mva_temporal_g113_c3(*, pdfs_por_url: dict, item: dict,
                                     data_operacao: str, evidencias: list[dict]) -> dict:
    """Select at most one documentary candidate within a declared observed window.

    Caller item/date are NOT independent NF-e/subject authentication. Requires
    authorized upstream I2/G14 binding before any commercial use (still barred).
    Checks *all* supplied documentary evidence, not only the date-selected row.
    A missing window or overlapping versions returns explicit abstention.
    """
    if type(pdfs_por_url) is not dict or not 1 <= len(pdfs_por_url) <= 8:
        _stop('CORPUS_INVALIDO')
    if type(evidencias) is not list or not 1 <= len(evidencias) <= 32:
        _stop('VERSOES_INVALIDAS')
    if type(item) is not dict or set(item) != {'indice_item', 'uf', 'ncm', 'cest'}:
        _stop('IDENTIDADE_ITEM_INVALIDA')
    if (type(item['indice_item']) is not int or not 1 <= item['indice_item'] <= 500
        or type(item['uf']) is not str or not re.fullmatch(r'[A-Z]{2}', item['uf'])
        or type(item['ncm']) is not str or _NCM.fullmatch(item['ncm']) is None
        or type(item['cest']) is not str or _CEST.fullmatch(item['cest']) is None):
        _stop('CODIGOS_ITEM_INVALIDOS')
    operation = _iso(data_operacao)
    seen = set()
    selected = []
    cache = {}
    for evidence in evidencias:
        _, window_start, window_end = _evidence(evidence)
        version = evidence['versao_id']
        if version in seen:
            _stop('VERSAO_DUPLICADA')
        seen.add(version)
        _row(pdfs_por_url, evidence, cache)
        if (item['uf'] == evidence['uf'] and item['ncm'] == evidence['ncm']
            and item['cest'] == evidence['cest'] and window_start <= operation <= window_end):
            selected.append(evidence)
    if len(selected) > 1:
        state, reason, chosen = 'ABSTENCAO_TEMPORAL', 'SOBREPOSICAO_VERSOES_CANDIDATAS', None
    elif not selected:
        state, reason, chosen = 'ABSTENCAO_TEMPORAL', 'SEM_JANELA_DOCUMENTAL_COTEJADA', None
    else:
        state, reason, chosen = ('CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE',
                                  'NAO_PROVA_VIGENCIA_OU_APLICABILIDADE_JURIDICA', selected[0])
    return {
        'schema_version': SCHEMA, 'estado': state, 'motivo': reason,
        'data_operacao_declarada': data_operacao, 'indice_item': item['indice_item'],
        'uf': item['uf'], 'ncm': item['ncm'], 'cest': item['cest'],
        'versoes_documentais_cotejadas': len(evidencias),
        'versao_selecionada': chosen['versao_id'] if chosen is not None else None,
        'mva_original_percentual_observada': chosen['mva_original_percentual'] if chosen is not None else None,
        'pdf_sha256': chosen['pdf_sha256'] if chosen is not None else None,
        'excerto_sha256': chosen['excerto_sha256'] if chosen is not None else None,
        'verificacao_pdf_pagina_excerto': True,
        'prova_nf_e_real': False, 'prova_adr020_regra_persistida': False,
        'prova_ausencia_alteracoes_posteriores': False,
        'prova_relacao_semantica_com_formulas_fiscais': False,
        **{key: False for key in _RESTRICTED},
    }


__all__ = ['SCHEMA', 'G113C3EvidenceError', 'selecionar_mva_temporal_g113_c3']
