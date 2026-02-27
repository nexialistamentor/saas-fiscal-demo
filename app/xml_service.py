import os
import xml.etree.ElementTree as ET


def ler_xml_unico(caminho_xml: str):

    tree = ET.parse(caminho_xml)
    root = tree.getroot()

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    emit = root.find(".//nfe:emit", ns)
    ide = root.find(".//nfe:ide", ns)
    total = root.find(".//nfe:ICMSTot", ns)

    # CNPJ e Razão Social
    if emit is not None:
        cnpj_tag = emit.find("nfe:CNPJ", ns)
        nome_tag = emit.find("nfe:xNome", ns)

        cnpj = cnpj_tag.text if cnpj_tag is not None else None
        razao_social = nome_tag.text if nome_tag is not None else None
    else:
        cnpj = None
        razao_social = None

    # Data
    data_emissao = ide.find("nfe:dhEmi", ns).text if ide is not None else None

    # Valor Total
    valor_total = total.find("nfe:vNF", ns).text if total is not None else None

    return {
        "cnpj": cnpj,
        "razao_social": razao_social,
        "data_emissao": data_emissao,
        "valor_total": valor_total,
    }
