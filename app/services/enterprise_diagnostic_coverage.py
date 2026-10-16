"""P1-02B — cobertura documental NF-e, limitada e somente informativa.

Nao cria elegibilidade de checkout, oferta, credito ou direito fiscal. A
verificacao do resultado persistido, fingerprint e empresa pertence ao futuro
chamador autorizado. Nao modifica as flags legadas nem a politica P1-02A.

``st_nao_destacado_observado`` significa apenas que os itens examinados
possuem grupos ICMS legiveis e nao trazem campos de destaque ST. NAO
significa isencao, nao incidencia nem prova de credito/restituicao.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

_NS_URI = "http://www.portalfiscal.inf.br/nfe"
_NS = {"nfe": _NS_URI}
_CHAVE = re.compile(r"[0-9]{44}\Z")
_UFS = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
})
_FIELDS_ST = ("vBCST", "vST", "vICMSST")
_EMPTY = {
    "documental_suficiente": False,
    "empresarial_completo": False,
    "st_nao_destacado_observado": False,
}


def _valor(valor: object) -> Decimal | None:
    if type(valor) is bool or type(valor) not in (int, float, str):
        return None
    if type(valor) is str and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", valor):
        return None
    try:
        x = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None
    return x if x.is_finite() and x >= 0 else None


def _grupo_icms_legivel(det: object) -> tuple[bool, bool]:
    """(ICMS documental legivel, existe campo ST em algum grupo)."""
    imp = det.find("nfe:imposto/nfe:ICMS", _NS)
    if imp is None or len(imp) != 1:
        return False, False
    grupo = imp[0]
    if not isinstance(grupo.tag, str) or not grupo.tag.startswith("{" + _NS_URI + "}ICMS"):
        return False, False
    cst = grupo.find("nfe:CST", _NS)
    csosn = grupo.find("nfe:CSOSN", _NS)
    codigo = cst if cst is not None else csosn
    origem = grupo.find("nfe:orig", _NS)
    if origem is None or not (origem.text or "").strip():
        return False, False
    if codigo is None or not (codigo.text or "").strip():
        return False, False
    # O grupo fiscal esta identificado; ausencia de vBCST/vST nao significa
    # pagamento zero e tampouco autoriza deducao sobre incidencia de ST.
    st = any(grupo.find("nfe:" + campo, _NS) is not None for campo in _FIELDS_ST)
    return True, st


def avaliar_cobertura_nfe_documental(
    xml_bytes: bytes, resultado: object, *, empresa_id: int
) -> dict[str, bool]:
    """Descreve evidencia XML; NUNCA decide autorizacao de compra.

    Recebe o payload empresarial do chamador, que ainda deve impor
    provenance/fingerprint/status/ownership antes de qualquer uso comercial.
    Nao reinterpreta ``dados_incompletos`` global ou ST legado.
    """
    negado = dict(_EMPTY)
    if type(empresa_id) is not int or empresa_id <= 0:
        return negado
    if type(resultado) is not dict or type(resultado.get("empresa_id")) is not int:
        return negado
    if resultado["empresa_id"] != empresa_id:
        return negado
    if type(xml_bytes) is not bytes or not xml_bytes or len(xml_bytes) > 20_000_000:
        return negado
    fiscal = resultado.get("dados_fiscais")
    if type(fiscal) is not dict or fiscal.get("erro"):
        return negado
    if type(resultado.get("insights")) is not dict:
        return negado
    if type(resultado["insights"].get("documental")) is not list:
        return negado
    if type(resultado.get("previsao_recuperacao")) is not dict:
        return negado

    try:
        root = ET.fromstring(xml_bytes)
        if root.tag not in ("{" + _NS_URI + "}nfeProc", "{" + _NS_URI + "}NFe"):
            return negado
        infos = root.findall(".//nfe:infNFe", _NS)
        if len(infos) != 1:
            return negado
        chave = infos[0].get("Id")
        if type(chave) is not str or not chave.startswith("NFe"):
            return negado
        chave = chave[3:]
        if _CHAVE.fullmatch(chave) is None:
            return negado
        # Comparacao escopada da evidencia documental com o snapshot:
        # evita importar o parser central (que inicializa models/database).
        # Nao e segunda autoridade de calculo tributario nem parser geral.
        info = infos[0]
        if fiscal.get("chave_nfe") != chave:
            return negado
        valor_xml = info.findtext("nfe:total/nfe:ICMSTot/nfe:vNF", namespaces=_NS)
        total_xml = _valor(valor_xml)
        total_payload = _valor(fiscal.get("valor_total_nota"))
        if total_xml is None or total_payload is None or total_xml != total_payload:
            return negado
        observadas = {
            "uf_emit": info.findtext("nfe:emit/nfe:enderEmit/nfe:UF", namespaces=_NS),
            "uf_dest": info.findtext("nfe:dest/nfe:enderDest/nfe:UF", namespaces=_NS),
        }
        for campo, uf in observadas.items():
            if uf not in _UFS or fiscal.get(campo) != uf:
                return negado
        cnpj = info.findtext("nfe:emit/nfe:CNPJ", namespaces=_NS)
        if (type(cnpj) is not str or
                re.fullmatch(r"[0-9]{14}", cnpj) is None or
                fiscal.get("cnpj_emitente") != cnpj):
            return negado

        itens = info.findall("nfe:det", _NS)
        if not itens:
            return negado
        st_encontrado = False
        for item in itens:
            if item.find("nfe:prod", _NS) is None:
                return negado
            legivel, st = _grupo_icms_legivel(item)
            if not legivel:
                return negado
            st_encontrado = st_encontrado or st
    except (ET.ParseError, DefusedXmlException, ValueError, TypeError, LookupError, AttributeError):
        return negado

    # A cobertura empresarial completa necessita de evidencia independente.
    # Flags empresariais ou listas vazias NAO comprovam auditoria integral.
    return {
        "documental_suficiente": True,
        "empresarial_completo": False,
        "st_nao_destacado_observado": not st_encontrado,
    }
