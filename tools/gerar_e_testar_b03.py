"""
gerar_e_testar_b03.py

Resolve a dependencia de dado real num unico passo: busca uma regra
normativa JA EXISTENTE na BD (via listar_base_normativa, nao
reimplementado), constroi um XML sintetico minimo com essa UF+NCM+data
reais, e roda confrontar_xml_b03 duas vezes (sem divergencia, com
divergencia forcada). Nao precisa de mais nenhuma decisao antes de rodar.

Uso (a partir da raiz do repo):
    python tools\\gerar_e_testar_b03.py
"""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.services.tabela_normativa_service import listar_base_normativa
from app.services.fiscal_utils import resolver_aliquota_e_mva
from app.motor_fiscal import MotorFiscal
from app.services.enterprise_b03_item_reconciliation import confrontar_xml_b03


def _campo(obj, *nomes):
    for nome in nomes:
        if isinstance(obj, dict) and nome in obj:
            return obj[nome]
        if hasattr(obj, nome):
            return getattr(obj, nome)
    return None


def _montar_xml(uf, ncm, data_operacao, valor_produto, base_st, valor_st, chave):
    return f"""<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
<NFe><infNFe Id="NFe{chave}">
<ide><dhEmi>{data_operacao.isoformat()}T10:00:00-03:00</dhEmi></ide>
<emit><enderEmit><UF>{uf}</UF></enderEmit></emit>
<dest><enderDest><UF>{uf}</UF></enderDest></dest>
<det nItem="1"><prod><NCM>{ncm}</NCM><CFOP>5405</CFOP><vProd>{valor_produto:.2f}</vProd></prod>
<imposto><ICMS><ICMS10><vBCST>{base_st:.2f}</vBCST><vICMSST>{valor_st:.2f}</vICMSST></ICMS10></ICMS></imposto>
</det>
</infNFe></NFe>
<protNFe><infProt><chNFe>{chave}</chNFe></infProt></protNFe>
</nfeProc>""".encode("utf-8")


def main():
    db = SessionLocal()
    try:
        base = listar_base_normativa(db)
        if not base:
            print("ERRO: listar_base_normativa devolveu vazio -- sem regra real na BD para testar.")
            return

        print(f"Total de regras na base normativa: {len(base)}")

        # Tenta cada regra ate encontrar uma que resolver_aliquota_e_mva autorize
        # (a base normativa pode ter entradas parciais/so-MVA sem aliquota).
        for candidata in base:
            uf = _campo(candidata, "uf", "estado")
            ncm = _campo(candidata, "ncm")
            vigencia_inicio = _campo(candidata, "vigencia_inicio")

            if not uf or not ncm:
                continue

            data_operacao = vigencia_inicio if isinstance(vigencia_inicio, date) else date.today()
            if isinstance(vigencia_inicio, str):
                try:
                    data_operacao = date.fromisoformat(vigencia_inicio[:10])
                except ValueError:
                    data_operacao = date.today()

            regra = resolver_aliquota_e_mva(db, uf, ncm, data_operacao)
            if regra.get("calculo_autorizado"):
                print(f"\nRegra usavel encontrada: UF={uf} NCM={ncm} data={data_operacao}")
                print("regra:", regra)
                break
        else:
            print("\nNenhuma regra da base normativa passou por resolver_aliquota_e_mva "
                  "com calculo_autorizado=True. Primeira candidata (diagnostico):")
            primeira = base[0]
            print(" tipo:", type(primeira))
            if isinstance(primeira, dict):
                print(" chaves:", list(primeira.keys()))
            else:
                print(" atributos:", [a for a in dir(primeira) if not a.startswith("_")])
            return

        valor_produto = 300.00
        motor = MotorFiscal()
        # MotorFiscal espera percentual (45, nao 0.45) -- mesma conversao
        # agora aplicada dentro de confrontar_documento_b03.
        mva_percentual = regra["mva"] * 100
        aliquota_percentual = regra["aliquota"] * 100
        base_st = motor.calcular_base_st(valor_produto, mva_percentual)
        icms_proprio = motor.calcular_icms_proprio(valor_produto, aliquota_percentual)
        icms_st = motor.calcular_icms_st(base_st, aliquota_percentual, icms_proprio)
        print(f"calculado (esperado para bater): base_st={base_st} icms_st={icms_st}")

        chave = "9" * 44
        xml_ok = _montar_xml(uf, ncm, data_operacao, valor_produto, base_st, icms_st, chave)
        resultado = confrontar_xml_b03(db=db, xml_bytes=xml_ok)
        print("\n=== CASO 1: valores do XML batem com o calculo (esperado SEM_DIVERGENCIA) ===")
        print("estado:", resultado["estado"])
        print("autoridade_fiscal:", resultado["autoridade_fiscal"])
        if resultado["estado"] != "SEM_DIVERGENCIA":
            print("resultado_bruto:", resultado.get("resultado_bruto"))

        xml_divergente = _montar_xml(uf, ncm, data_operacao, valor_produto, base_st, 999999.99, chave)
        resultado2 = confrontar_xml_b03(db=db, xml_bytes=xml_divergente)
        print("\n=== CASO 2: valor_st do XML forcado errado (esperado DIVERGENCIA_ENCONTRADA) ===")
        print("estado:", resultado2["estado"])
        print("divergencias:", resultado2["resultado_bruto"].get("divergencias"))

    finally:
        db.close()


if __name__ == "__main__":
    main()
