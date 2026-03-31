import os
import defusedxml.ElementTree as ET

PASTA_XML = "."

def ler_xmls():
    arquivos = os.listdir(PASTA_XML)

    for arquivo in arquivos:
        if arquivo.endswith(".xml"):

            caminho_completo = os.path.join(PASTA_XML, arquivo)

            tree = ET.parse(caminho_completo)
            root = tree.getroot()

            ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

            emit = root.find(".//nfe:emit", ns)
            ide = root.find(".//nfe:ide", ns)
            total = root.find(".//nfe:ICMSTot", ns)

            # CNPJ
            if emit is not None:
                cnpj_tag = emit.find("nfe:CNPJ", ns)
                nome_tag = emit.find("nfe:xNome", ns)

                cnpj = cnpj_tag.text if cnpj_tag is not None else "Não encontrado"
                razao_social = nome_tag.text if nome_tag is not None else "Não encontrado"
            else:
                cnpj = "Emitente não encontrado"
                razao_social = "Emitente não encontrado"

            # Data emissão
            if ide is not None:
                data_tag = ide.find("nfe:dhEmi", ns)
                data_emissao = data_tag.text if data_tag is not None else "Não encontrada"
            else:
                data_emissao = "Não encontrada"

            # Valor total
            if total is not None:
                valor_tag = total.find("nfe:vNF", ns)
                valor_total = valor_tag.text if valor_tag is not None else "Não encontrado"
            else:
                valor_total = "Não encontrado"

            print("-------------------------------------------------")
            print(f"Arquivo: {arquivo}")
            print(f"CNPJ: {cnpj}")
            print(f"Razão Social: {razao_social}")
            print(f"Data Emissão: {data_emissao}")
            print(f"Valor Total: R$ {valor_total}")
            print("-------------------------------------------------\n")

if __name__ == "__main__":
    ler_xmls()
