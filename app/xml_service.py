import defusedxml.ElementTree as ET
from datetime import datetime

from app.models import DocumentoFiscal, ItemFiscal
from app.motor_fiscal import MotorFiscal, analisar_xml, carregar_mva
from app.services.tax_consistency.tax_consistency_engine import TaxConsistencyEngine

ALIQUOTA_ICMS_PADRAO = 18.0


def _extrair_texto(elemento, tag, ns):
    """Retorna o texto da tag ou None."""
    if elemento is None:
        return None
    el = elemento.find(tag, ns)
    return el.text if el is not None else None


def _extrair_valor_icms_detalhe(det, ns):
    """Extrai base_icms, valor_icms, base_st, valor_st do bloco ICMS do det."""
    imposto = det.find("nfe:imposto", ns)
    if imposto is None:
        return None, None, None, None

    icms = imposto.find("nfe:ICMS", ns)
    if icms is None:
        return None, None, None, None

    # Busca recursivamente em qualquer grupo (ICMS00, ICMS10, ICMSSN500, etc.)
    base_icms = None
    valor_icms = None
    base_st = None
    valor_st = None

    for filho in icms:
        vbc = _extrair_texto(filho, "nfe:vBC", ns)
        vicms = _extrair_texto(filho, "nfe:vICMS", ns)
        vbcst = _extrair_texto(filho, "nfe:vBCST", ns)
        # vST (NF-e antiga) ou vICMSST (ICMS10/30/70 na NF-e 4.0)
        vst = _extrair_texto(filho, "nfe:vST", ns) or _extrair_texto(filho, "nfe:vICMSST", ns)
        if vbc is not None:
            base_icms = vbc
        if vicms is not None:
            valor_icms = vicms
        if vbcst is not None:
            base_st = vbcst
        if vst is not None:
            valor_st = vst

    return base_icms, valor_icms, base_st, valor_st


def ler_xml_unico(caminho_xml: str = None, xml_bytes: bytes = None):

    if xml_bytes:
        root = ET.fromstring(xml_bytes)
    else:
        tree = ET.parse(caminho_xml)
        root = tree.getroot()

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    emit = root.find(".//nfe:emit", ns)
    ide = root.find(".//nfe:ide", ns)
    total = root.find(".//nfe:ICMSTot", ns)
    inf_prot = root.find(".//nfe:infProt", ns)
    inf_nfe = root.find(".//nfe:infNFe", ns)

    # CNPJ e Razão Social
    if emit is not None:
        cnpj = _extrair_texto(emit, "nfe:CNPJ", ns)
        razao_social = _extrair_texto(emit, "nfe:xNome", ns)
    else:
        cnpj = None
        razao_social = None

    # UF emitente e destinatário
    uf_emit = root.findtext(".//nfe:emit/nfe:enderEmit/nfe:UF", namespaces=ns)
    uf_dest = root.findtext(".//nfe:dest/nfe:enderDest/nfe:UF", namespaces=ns)

    # Data
    data_emissao = _extrair_texto(ide, "nfe:dhEmi", ns)

    # Valor Total
    valor_total = _extrair_texto(total, "nfe:vNF", ns)

    # Chave NF-e (protNFe/infProt/chNFe ou extrair do Id do infNFe)
    chave_nfe = None
    if inf_prot is not None:
        chave_nfe = _extrair_texto(inf_prot, "nfe:chNFe", ns)
    if chave_nfe is None and inf_nfe is not None:
        id_attr = inf_nfe.get("Id")
        if id_attr and id_attr.startswith("NFe"):
            chave_nfe = id_attr[3:]  # Remove prefixo "NFe"

    # Número da nota
    numero_nota = _extrair_texto(ide, "nfe:nNF", ns)

    # Tipo: entrada (0) ou saida (1)
    tp_nf = _extrair_texto(ide, "nfe:tpNF", ns)
    tipo = "saida" if tp_nf == "1" else "entrada"

    # Itens (cada <det>)
    itens = []
    for det in root.findall(".//nfe:det", ns):
        prod = det.find("nfe:prod", ns)
        if prod is None:
            continue

        ncm = _extrair_texto(prod, "nfe:NCM", ns)
        cfop = _extrair_texto(prod, "nfe:CFOP", ns)
        qcom = _extrair_texto(prod, "nfe:qCom", ns)
        valor_produto = _extrair_texto(prod, "nfe:vProd", ns)
        base_icms, valor_icms, base_st, valor_st = _extrair_valor_icms_detalhe(
            det, ns
        )

        itens.append({
            "ncm": ncm,
            "cfop": cfop,
            "quantidade": _parse_float(qcom) if qcom else 1,
            "valor_produto": valor_produto,
            "base_icms": base_icms,
            "valor_icms": valor_icms,
            "base_st": base_st,
            "valor_st": valor_st,
        })

    resultado = {
        "chave_nfe": chave_nfe,
        "numero_nota": numero_nota,
        "tipo": tipo,
        "cnpj": cnpj,
        "razao_social": razao_social,
        "data_emissao": data_emissao,
        "valor_total": valor_total,
        "uf_emit": uf_emit,
        "uf_dest": uf_dest,
        "itens": itens,
    }
    
    
    return resultado


def _parse_float(val):
    """Converte string para float (aceita ',' ou '.')."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", "."))
    except (TypeError, ValueError):
        return None


def enriquecer_st_se_necessario(dados: dict, analise: dict) -> None:
    """
    Motor dual para ICMS-ST:
    - Se XML tem ST (base_st, valor_st nos itens) → mantém (validar)
    - Se XML não tem ST → calcula usando MotorFiscal + carregar_mva
    Modifica dados in-place.
    """
    uf = dados.get("uf_dest") or dados.get("uf_emit") or analise.get("uf_operacao")
    mva_doc = analise.get("mva_utilizada") or analise.get("mva_percentual")
    if mva_doc is not None:
        mva_doc = _parse_float(mva_doc)

    for item in dados.get("itens", []):
        base_st = item.get("base_st")
        valor_st = item.get("valor_st")
        # ST já presente no XML → manter (validar)
        if base_st is not None and str(base_st).strip() and float(str(base_st).replace(",", ".") or 0) > 0:
            continue
        if valor_st is not None and str(valor_st).strip() and float(str(valor_st).replace(",", ".") or 0) > 0:
            continue

        # ST ausente → calcular
        valor_prod = _parse_float(item.get("valor_produto"))
        ncm = item.get("ncm")
        if valor_prod is None or valor_prod <= 0 or not ncm:
            continue

        mva = mva_doc or carregar_mva(ncm, uf)
        if mva is None:
            continue
        base_st_calc = MotorFiscal.calcular_base_st(valor_prod, mva)
        icms_proprio = MotorFiscal.calcular_icms_proprio(valor_prod, ALIQUOTA_ICMS_PADRAO)
        icms_st_calc = MotorFiscal.calcular_icms_st(
            base_st_calc, ALIQUOTA_ICMS_PADRAO, icms_proprio
        )

        item["base_st"] = round(base_st_calc, 2)
        item["valor_st"] = round(icms_st_calc, 2)

    # MVA no documento: usar da análise ou da primeira MVA calculada
    if mva_doc is None and dados.get("itens"):
        first_ncm = next((i.get("ncm") for i in dados["itens"] if i.get("ncm")), None)
        if first_ncm:
            dados["mva_utilizada"] = carregar_mva(first_ncm, uf)


def _parse_data_emissao(val):
    """Converte string ISO para date (SQLite exige date, não string)."""
    if val is None:
        return None
    if hasattr(val, "date"):
        return val.date() if callable(getattr(val, "date", None)) else val
    if isinstance(val, str):
        try:
            # Extrair só a parte da data (YYYY-MM-DD) para evitar problemas de timezone
            partes = val.split("T")[0].split(" ")[0]
            if len(partes) >= 10:
                return datetime.strptime(partes[:10], "%Y-%m-%d").date()
            return datetime.strptime(partes, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    return None


def processar_e_persistir_xml(db, usuario_atual, empresa, xml_bytes: bytes, dados_pre_parse: dict | None = None):
    """
    Pipeline compartilhado de processamento + persistência fiscal.
    Reaproveita exatamente a lógica já usada no upload síncrono.
    Retorna (documento, dados, analise).
    """
    dados = dados_pre_parse or ler_xml_unico(xml_bytes=xml_bytes)
    analise = analisar_xml(xml_bytes)

    engine = TaxConsistencyEngine()
    consistencia = engine.verificar_consistencia(
        dados_xml=dados,
        dados_motor=analise
    )
    analise["consistencia_fiscal"] = consistencia

    enriquecer_st_se_necessario(dados, analise)

    mva = analise.get("mva_utilizada") or analise.get("mva_percentual")
    if mva is not None:
        dados["mva_utilizada"] = float(mva) if isinstance(mva, str) else mva

    documento = persistir_documento_fiscal(db, usuario_atual, empresa, dados)
    return documento, dados, analise


def persistir_documento_fiscal(db, usuario_atual, empresa, dados):
    from app import models

    # 1️⃣ Criar documento
    mva = dados.get("mva_utilizada")
    if mva is not None and isinstance(mva, str):
        try:
            mva = float(mva)
        except (TypeError, ValueError):
            mva = None

    data_emissao = _parse_data_emissao(dados.get("data_emissao"))

    documento = models.DocumentoFiscal(
        usuario_id=usuario_atual.id,
        empresa_id=empresa.id,
        chave_nfe=dados.get("chave_nfe"),
        numero_nota=dados.get("numero_nota"),
        data_emissao=data_emissao,
        tipo=dados.get("tipo"),
        valor_total=dados.get("valor_total"),
        mva_utilizada=mva,
        uf_emit=dados.get("uf_emit"),
        uf_dest=dados.get("uf_dest"),
    )

    db.add(documento)
    db.flush()  # garante que documento.id já exista

    # 2️⃣ Inserir itens
    for item_data in dados.get("itens", []):
        item = models.ItemFiscal(
            documento_id=documento.id,
            ncm=item_data.get("ncm"),
            cfop=item_data.get("cfop"),
            quantidade=item_data.get("quantidade"),
            valor_produto=item_data.get("valor_produto"),
            base_icms=item_data.get("base_icms"),
            valor_icms=item_data.get("valor_icms"),
            base_st=item_data.get("base_st"),
            valor_st=item_data.get("valor_st"),
        )
        db.add(item)

    # 3️⃣ Commit único
    db.commit()

    return documento

