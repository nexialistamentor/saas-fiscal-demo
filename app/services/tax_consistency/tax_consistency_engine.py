"""Enterprise G1 — consistência numérica fiscal com origem por item (fail-closed).

NAO atesta conformidade tributária, vigência normativa, recolhimento,
revogação, crédito, restituição ou autorização comercial. O motor legado
`analisar_xml()` espelha valores do XML: não constitui recálculo independente.

Os relatórios documentais podem consumir este resultado informativo, mas
`consistente` fica sempre None até existir um árbitro normativo independente
com proveniência, competência e fontes oficiais verificadas.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


_VALORES = ("ICMS_ST", "BASE_ST")


class TaxConsistencyEngine:
    """Compara SOMENTE pares de itens com identidade e cálculo separados."""

    @staticmethod
    def _moeda(valor: object) -> Decimal | None:
        if type(valor) not in (int, float, str, Decimal):
            return None
        if type(valor) is str and (not valor or valor.strip() != valor or "e" in valor.lower()):
            return None
        try:
            n = Decimal(str(valor))
        except (ValueError, InvalidOperation):
            return None
        if not n.is_finite() or n < 0 or n > Decimal("9999999999999.99"):
            return None
        if n.as_tuple().exponent < -2:
            return None
        return n.quantize(Decimal("0.01"))

    @staticmethod
    def _nao_avaliado(motivo: str) -> dict:
        return {
            "estado": "NAO_AVALIADO",
            "motivo": motivo,
            "consistente": None,
            "coincidencia_numerica": None,
            "divergencias": [],
            "comparacoes_realizadas": 0,
            "itens_comparados": 0,
            "autoridade_fiscal": False,
            "credito_confirmado": False,
            "checkout_autorizado": False,
        }

    def verificar_consistencia(self, dados_xml: dict, dados_motor: dict) -> dict:
        """Somente `itens_calculados` explícitos podem originar confronto numérico.

        `dados_motor` sem itens independentes (como a saída real de
        `motor_fiscal.analisar_xml`) é NAO_AVALIADO, nunca consistente=True.

        Um chamador externo pode fabricar a entrada `itens_calculados`;
        por isso mesmo um confronto totalmente coincidente é SEM AUTORIDADE.
        """
        if type(dados_xml) is not dict or type(dados_motor) is not dict:
            return self._nao_avaliado("ENTRADA_AUSENTE_OU_MALFORMADA")
        if dados_motor.get("erro") is not None:
            return self._nao_avaliado("MOTOR_COM_ERRO")
        calculados = dados_motor.get("itens_calculados")
        if calculados is None:
            return self._nao_avaliado("SEM_RECALCULO_POR_ITEM_INDEPENDENTE")
        originais = dados_xml.get("itens")
        if (type(originais) is not list or type(calculados) is not list
                or not originais or len(originais) != len(calculados)
                or len(originais) > 500):
            return self._nao_avaliado("CARDINALIDADE_ITENS_NAO_CONCILIADA")
        chave_xml = dados_xml.get("chave_nfe")
        chave_motor = dados_motor.get("chave_nfe")
        if (type(chave_xml) is not str or len(chave_xml) != 44
                or not chave_xml.isascii() or not chave_xml.isdecimal()
                or chave_motor != chave_xml):
            return self._nao_avaliado("IDENTIDADE_DOCUMENTO_NAO_CONCILIADA")

        calculados_por_indice: dict[int, dict] = {}
        for item in calculados:
            if type(item) is not dict:
                return self._nao_avaliado("CALCULO_ITEM_MALFORMADO")
            indice = item.get("indice_item")
            if (type(indice) is not int or not 1 <= indice <= len(originais)
                    or indice in calculados_por_indice):
                return self._nao_avaliado("INDICE_CALCULO_DUPLICADO_OU_INVALIDO")
            calculados_por_indice[indice] = item

        comparacoes = []
        divergencias = []
        itens_comparados = 0
        motivos_pendentes = []
        for indice, xml_item in enumerate(originais, 1):
            calculado = calculados_por_indice.get(indice)
            if type(xml_item) is not dict or calculado is None:
                return self._nao_avaliado("ITEM_XML_MALFORMADO_OU_AUSENTE")
            # Compara identidade NCM/CFOP estritamente; evita misturar itens.
            ncm, cfop = xml_item.get("ncm"), xml_item.get("cfop")
            if (type(ncm) is not str or type(cfop) is not str
                    or not ncm or not cfop
                    or calculado.get("ncm") != ncm
                    or calculado.get("cfop") != cfop):
                return self._nao_avaliado("CLASSIFICACAO_ITEM_NAO_CONCILIADA")
            if xml_item.get("st_observado_xml") is not True:
                motivos_pendentes.append(f"ITEM_{indice}_ST_NAO_OBSERVADO_XML")
                continue
            pares = (("ICMS_ST", "valor_st", "valor_st_calculado"),
                     ("BASE_ST", "base_st", "base_st_calculada"))
            validos = []
            for tipo, campo_xml, campo_motor in pares:
                a = self._moeda(xml_item.get(campo_xml))
                b = self._moeda(calculado.get(campo_motor))
                if a is None or b is None:
                    motivos_pendentes.append(f"ITEM_{indice}_{tipo}_VALORES_NAO_COMPROVADOS")
                    continue
                validos.append((tipo, a, b))
            if len(validos) == 2:
                itens_comparados += 1
            for tipo, a, b in validos:
                diferente = abs(a - b) > Decimal("0.01")
                resultado = {
                    "indice_item": indice,
                    "tipo": tipo,
                    "valor_xml": str(a),
                    "valor_motor": str(b),
                    "divergencia_numerica": diferente,
                    "prova_normativa": False,
                }
                comparacoes.append(resultado)
                if diferente:
                    divergencias.append(resultado)
        if not comparacoes:
            return self._nao_avaliado("SEM_PARES_NUMERICOS_COMPARAVEIS")
        total = 2 * len(originais)
        completo = len(comparacoes) == total and itens_comparados == len(originais)
        return {
            "estado": "COMPARACAO_NUMERICA_SEM_AUTORIDADE" if completo else "PARCIAL_SEM_AUTORIDADE",
            "motivo": "SEM_PROVA_NORMATIVA_E_RECOLHIMENTO" if completo else "ITENS_OU_CAMPOS_NAO_AVALIADOS",
            "consistente": None,
            "coincidencia_numerica": (not divergencias) if completo else None,
            "divergencias": divergencias,
            "comparacoes": comparacoes,
            "comparacoes_realizadas": len(comparacoes),
            "itens_comparados": itens_comparados,
            "itens_total": len(originais),
            "motivos_pendentes": motivos_pendentes,
            "autoridade_fiscal": False,
            "credito_confirmado": False,
            "checkout_autorizado": False,
        }

    # Métodos históricos diretos: um escalar sem identidade do item e do
    # cálculo não constitui uma comparação fiscal causal.
    def verificar_icms_st(self, dados_xml: dict, dados_motor: dict) -> dict:
        return self._nao_avaliado("SEM_IDENTIDADE_ITEM_E_FONTE_INDEPENDENTE_ICMS_ST")

    def verificar_mva(self, dados_xml: dict, dados_motor: dict) -> dict:
        return self._nao_avaliado("MVA_XML_NAO_OBSERVADA_POR_ITEM")

    def verificar_base_st(self, dados_xml: dict, dados_motor: dict) -> dict:
        return self._nao_avaliado("SEM_IDENTIDADE_ITEM_E_FONTE_INDEPENDENTE_BASE_ST")
