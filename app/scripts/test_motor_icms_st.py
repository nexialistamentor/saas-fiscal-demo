"""
PASSO 18 — Validar cálculo real de ICMS-ST

Valida que o motor fiscal utiliza a MVA da tabela_mva (banco) em vez do JSON.

O teste processa um XML de NF-e, extrai UF e NCM dos itens,
consulta MVA no banco (com UF para regras estaduais) e calcula:
- Base ST
- ICMS ST devido

Se MVA aplicada = 40.0 para NCM 22021000/PA, o sistema está lendo corretamente tabela_mva.

Executar da raiz do projeto:
    python app/scripts/test_motor_icms_st.py
"""

import sys
import defusedxml.ElementTree as ET
from pathlib import Path

# Garante que a raiz do projeto está no PYTHONPATH
_raiz = Path(__file__).resolve().parent.parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

from app.motor_fiscal import MotorFiscal, carregar_mva

ALIQUOTA_ICMS_PADRAO = 18.0

# XML de teste com NCM 22021000 (MVA 40% em PA)
XML_TESTE = Path(__file__).resolve().parent.parent / "xmls_testes" / "xml_icms_st_teste.xml"


def _extrair_texto(elemento, tag: str, ns: dict):
    if elemento is None:
        return None
    el = elemento.find(tag, ns)
    return el.text if el is not None else None


def processar_xml_e_calcular_icms_st(caminho_xml: Path):
    """Processa XML, extrai itens e calcula ICMS-ST usando MVA do banco."""
    tree = ET.parse(caminho_xml)
    root = tree.getroot()
    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    uf_emit = root.findtext(".//nfe:emit/nfe:enderEmit/nfe:UF", namespaces=ns)
    uf_dest = root.findtext(".//nfe:dest/nfe:enderDest/nfe:UF", namespaces=ns)
    uf_operacao = uf_dest if uf_dest else uf_emit

    resultados = []
    for det in root.findall(".//nfe:det", ns):
        prod = det.find("nfe:prod", ns)
        if prod is None:
            continue

        ncm = _extrair_texto(prod, "nfe:NCM", ns)
        valor_produto = _extrair_texto(prod, "nfe:vProd", ns)
        if not ncm or not valor_produto:
            continue

        valor = float(valor_produto.replace(",", "."))
        if valor <= 0:
            continue

        # Consulta MVA no banco (passando UF para usar tabela_mva)
        mva = carregar_mva(ncm, uf_operacao)
        if mva is None:
            continue  # Não calcula ST quando MVA não encontrada
        base_st = MotorFiscal.calcular_base_st(valor, mva)
        icms_proprio = MotorFiscal.calcular_icms_proprio(valor, ALIQUOTA_ICMS_PADRAO)
        icms_st_devido = MotorFiscal.calcular_icms_st(
            base_st, ALIQUOTA_ICMS_PADRAO, icms_proprio
        )

        resultados.append({
            "uf_operacao": uf_operacao,
            "ncm": ncm,
            "valor_produto": valor,
            "mva_aplicada": mva,
            "base_st": base_st,
            "icms_st_devido": icms_st_devido,
        })

    return resultados


def main():
    if not XML_TESTE.exists():
        print(f"ERRO: XML de teste não encontrado em {XML_TESTE}")
        sys.exit(1)

    print("=" * 60)
    print("PASSO 18 — Validação do Motor Fiscal (ICMS-ST com MVA do banco)")
    print("=" * 60)

    resultados = processar_xml_e_calcular_icms_st(XML_TESTE)

    if not resultados:
        print("Nenhum item encontrado no XML.")
        sys.exit(1)

    for r in resultados:
        print(f"UF operação: {r['uf_operacao']}")
        print(f"NCM: {r['ncm']}")
        print(f"Valor produto: R$ {r['valor_produto']:.2f}")
        print(f"MVA aplicada: {r['mva_aplicada']}")
        print(f"Base ST: R$ {r['base_st']:.2f}")
        print(f"ICMS ST devido: R$ {r['icms_st_devido']:.2f}")
        print("-" * 40)

    # Validação: NCM 22021000 em PA deve ter MVA 40.0
    item_22021000 = next((r for r in resultados if r["ncm"] == "22021000"), None)
    if item_22021000 and item_22021000["mva_aplicada"] == 40.0:
        print("[OK] MVA 40.0 = sistema lendo corretamente a tabela_mva (banco).")
    else:
        mva_obtida = item_22021000["mva_aplicada"] if item_22021000 else "N/A"
        print(f"[ATENÇÃO] MVA esperada 40.0 para NCM 22021000/PA. Obtida: {mva_obtida}")
        print("Verifique se a tabela_mva foi populada (seed_mva ou importar_mvas).")


if __name__ == "__main__":
    main()
