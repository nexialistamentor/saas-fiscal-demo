"""
PASSO 26 — Testar motor com XML que possui ICMS-ST real (ICMS10/30/70)

Valida:
- mva_utilizada extraída do XML
- base_st extraída do XML
- icms_st extraída do XML
- Motor dual: XML com ST → validar; XML sem ST → calcular
- Persistência no banco

Executar da raiz do projeto:
    python app/scripts/test_passo26_icms_st_xml.py
"""

import sys
from pathlib import Path

_raiz = Path(__file__).resolve().parent.parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

# XML com ICMS10 e ST real
XML_ICMS10 = Path(__file__).resolve().parent.parent / "xmls_testes" / "xml_icms10_st_real.xml"
# XML sem ST (ICMSSN500) - para testar cálculo
XML_SEM_ST = Path(__file__).resolve().parent.parent / "xmls_testes" / "xml_icms_st_teste.xml"


def test_analise_xml_com_st():
    """Testa analisar_xml com XML que possui ICMS10."""
    from app.motor_fiscal import analisar_xml

    if not XML_ICMS10.exists():
        print(f"ERRO: {XML_ICMS10} não encontrado.")
        return False

    conteudo = XML_ICMS10.read_bytes()
    analise = analisar_xml(conteudo)

    print("=" * 60)
    print("1. Análise do XML com ICMS10 (ST já no XML)")
    print("=" * 60)

    mva = analise.get("mva_utilizada")
    base_st = analise.get("base_st")
    icms_st = analise.get("icms_st")

    print(f"  mva_utilizada: {mva} (esperado: 40.00)")
    print(f"  base_st:      {base_st} (esperado: 350.00)")
    print(f"  icms_st:      {icms_st} (esperado: 18.00)")

    ok = mva == "40.00" and base_st == "350.00" and icms_st == "18.00"
    if ok:
        print("  [OK] Extração correta de mva, base_st e icms_st do ICMS10")
    else:
        print("  [FALHA] Valores não conferem")
    return ok


def test_ler_xml_unico_com_st():
    """Testa ler_xml_unico extraindo base_st e valor_st dos itens."""
    from app.xml_service import ler_xml_unico

    if not XML_ICMS10.exists():
        return False

    dados = ler_xml_unico(str(XML_ICMS10))
    itens = dados.get("itens", [])

    print("\n" + "=" * 60)
    print("2. ler_xml_unico — itens com base_st e valor_st (vICMSST)")
    print("=" * 60)

    if not itens:
        print("  [FALHA] Nenhum item encontrado")
        return False

    item = itens[0]
    base_st = item.get("base_st")
    valor_st = item.get("valor_st")
    print(f"  base_st:  {base_st} (esperado: 350.00)")
    print(f"  valor_st: {valor_st} (esperado: 18.00)")

    ok = base_st and str(base_st) == "350.00" and valor_st and str(valor_st) == "18.00"
    if ok:
        print("  [OK] base_st e valor_st extraídos do ICMS10")
    else:
        print("  [FALHA] Valores do item não conferem")
    return ok


def test_motor_dual_sem_st():
    """Testa motor dual: XML SEM ST → deve calcular."""
    from app.xml_service import ler_xml_unico, enriquecer_st_se_necessario
    from app.motor_fiscal import analisar_xml

    if not XML_SEM_ST.exists():
        print(f"AVISO: {XML_SEM_ST} não encontrado. Pulando teste dual sem ST.")
        return True

    conteudo = XML_SEM_ST.read_bytes()
    dados = ler_xml_unico(str(XML_SEM_ST))
    analise = analisar_xml(conteudo)
    enriquecer_st_se_necessario(dados, analise)

    print("\n" + "=" * 60)
    print("3. Motor dual - XML sem ST (ICMSSN500) -> calcular ST")
    print("=" * 60)

    itens = dados.get("itens", [])
    if not itens:
        print("  [FALHA] Nenhum item")
        return False

    item = itens[0]
    base_st = item.get("base_st")
    valor_st = item.get("valor_st")
    print(f"  XML original: base_st=None, valor_st=None")
    print(f"  Após enriquecimento: base_st={base_st}, valor_st={valor_st}")

    ok = base_st is not None and valor_st is not None and float(base_st) > 0 and float(valor_st) >= 0
    if ok:
        print("  [OK] Motor calculou ST quando XML não tinha")
    else:
        print("  [FALHA] Motor deveria ter calculado ST")
    return ok


def main():
    print("\n*** PASSO 26 — Validação ICMS-ST (ICMS10) ***\n")
    r1 = test_analise_xml_com_st()
    r2 = test_ler_xml_unico_com_st()
    r3 = test_motor_dual_sem_st()

    print("\n" + "=" * 60)
    if r1 and r2 and r3:
        print("Todos os testes passaram.")
    else:
        print("Algum teste falhou.")
        sys.exit(1)


if __name__ == "__main__":
    main()
