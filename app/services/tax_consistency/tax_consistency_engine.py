"""
Tax Consistency Engine — Motor de consistência tributária.

Detecta inconsistências entre:
- Valores declarados no XML da NF-e (ICMS-ST, base de cálculo, etc.)
- Valores recalculados pelo motor fiscal

Exemplo: ICMS-ST declarado no XML vs. ICMS-ST recalculado pelo motor.
"""

from __future__ import annotations


class TaxConsistencyEngine:
    """
    Serviço responsável por verificar inconsistências entre o cálculo
    do motor e o que veio no XML.
    """

    def verificar_consistencia(self, dados_xml: dict, dados_motor: dict) -> dict:
        """
        Executa todas as verificações de consistência fiscal.
        """
        resultados = []
        divergencias = []

        # executar verificações
        r_icms = self.verificar_icms_st(dados_xml, dados_motor)
        r_mva = self.verificar_mva(dados_xml, dados_motor)
        r_base = self.verificar_base_st(dados_xml, dados_motor)

        resultados.extend([r_icms, r_mva, r_base])

        # consolidar divergências
        for r in resultados:
            divergencias.extend(r.get("divergencias", []))

        return {
            "consistente": len(divergencias) == 0,
            "divergencias": divergencias
        }

    def verificar_icms_st(self, dados_xml: dict, dados_motor: dict) -> dict:
        """
        Compara ICMS-ST declarado no XML com o ICMS-ST recalculado pelo motor.
        """
        divergencias = []

        icms_xml = dados_xml.get("valor_st")
        icms_motor = dados_motor.get("icms_st")

        if icms_xml is None or icms_motor is None:
            return {
                "consistente": True,
                "divergencias": []
            }

        # tolerância para arredondamento
        tolerancia = 0.01

        if abs(float(icms_xml) - float(icms_motor)) > tolerancia:
            divergencias.append({
                "tipo": "ICMS_ST_DIVERGENTE",
                "valor_xml": icms_xml,
                "valor_motor": icms_motor
            })

        return {
            "consistente": len(divergencias) == 0,
            "divergencias": divergencias
        }

    def verificar_mva(self, dados_xml: dict, dados_motor: dict) -> dict:
        """
        Compara a MVA declarada no XML com a MVA utilizada pelo motor fiscal.
        """
        divergencias = []

        mva_xml = dados_xml.get("mva_xml")
        mva_motor = dados_motor.get("mva_utilizada")

        if mva_xml is None or mva_motor is None:
            return {
                "consistente": True,
                "divergencias": []
            }

        tolerancia = 0.01

        if abs(float(mva_xml) - float(mva_motor)) > tolerancia:
            divergencias.append({
                "tipo": "MVA_DIVERGENTE",
                "mva_xml": mva_xml,
                "mva_motor": mva_motor
            })

        return {
            "consistente": len(divergencias) == 0,
            "divergencias": divergencias
        }

    def verificar_base_st(self, dados_xml: dict, dados_motor: dict) -> dict:
        """
        Compara a base de cálculo do ICMS-ST declarada no XML com a base recalculada pelo motor fiscal.
        """
        divergencias = []

        base_xml = dados_xml.get("base_st")
        base_motor = dados_motor.get("base_st_calculada")

        if base_xml is None or base_motor is None:
            return {
                "consistente": True,
                "divergencias": []
            }

        tolerancia = 0.01

        if abs(float(base_xml) - float(base_motor)) > tolerancia:
            divergencias.append({
                "tipo": "BASE_ST_DIVERGENTE",
                "base_xml": base_xml,
                "base_motor": base_motor
            })

        return {
            "consistente": len(divergencias) == 0,
            "divergencias": divergencias
        }
