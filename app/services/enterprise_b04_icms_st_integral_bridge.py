"""
enterprise_b04_icms_st_integral_bridge.py

B04 -- integracao ponta a ponta dos motores: liga o gate G13
(projetar_confronto_st_sujeito_g13, ja em producao via
registro_analise_service.py) a cadeia de projecao integral I0-I1-I2
(enterprise_integral_projection.py / enterprise_i2_documentary_bridge.py),
preenchendo as capacidades icms_st/mva/consistencia_fiscal do catalogo
(_CAPACIDADES) que estavam "pendente" (nao_integrado_ao_snapshot).

NAO reimplementa nenhum calculo. Compoe duas chamadas a funcoes puras ja
existentes e testadas:
  - projetar_diagnostico_integral_i2 (ja chama i1 e i0 internamente) --
    da a cobertura completa do catalogo nas 52 capacidades.
  - projetar_confronto_st_sujeito_g13 (ja chama G12 e, internamente, a
    mesma i2, de forma redundante mas correta -- chamada extra a funcao
    pura ja existente, nao duplicacao de logica).

Escopo honesto: G12/G13 so cobrem o metodo 'iva_st' (nao PMPF). Por isso
so tres capacidades mudam de estado aqui -- icms_st, mva, consistencia_fiscal
(via o confronto_g1/TaxConsistencyEngine que ja vive dentro do resultado de
G12). pmpf, restituicao_st, creditos_st, distorcoes_st_mva continuam
"pendente" -- nao ha produtor real ligado para essas ainda, nao inventar.

Ver docs/REGISTRO_CANONICO.json e docs/B03_FECHAMENTO.md (adendo) para o
historico desta decisao.
"""
from __future__ import annotations

from copy import deepcopy

from app.services.enterprise_i2_documentary_bridge import projetar_diagnostico_integral_i2
from app.services.enterprise_g13_subject_st_bridge import (
    projetar_confronto_st_sujeito_g13,
    EnterpriseG13GateError,
)

_COMPONENTES_ICMS_ST = ("icms_st", "mva", "consistencia_fiscal")

SCHEMA_VERSION = "SOLVERIS_ENTERPRISE_B04_ICMS_ST_INTEGRAL_BRIDGE_V1"


def projetar_diagnostico_integral_icms_st(
    *, db, authenticated_user_id: int, empresa_id: int, relatorio_id: int, xml_bytes: bytes,
) -> dict:
    """Projeta I2 e preenche icms_st/mva/consistencia_fiscal via G13 (G12).

    Mesmo padrao de I1 (quarentena PIS/Cofins): nunca promove o resultado
    condicional de G12/G13 a prova -- autoridade_fiscal permanece False,
    estado fica em 'informativo_sem_prova' (nunca 'apurado'), e o resultado
    bruto de G13 e preservado em 'resultado_bruto_nao_validado' para
    auditoria, nunca usado como numero comercial.
    """
    base = projetar_diagnostico_integral_i2(
        db=db, authenticated_user_id=authenticated_user_id,
        empresa_id=empresa_id, relatorio_id=relatorio_id, xml_bytes=xml_bytes,
    )
    saida = deepcopy(base)
    itens = {e["id"]: e for e in saida["cobertura"]}

    try:
        g13 = projetar_confronto_st_sujeito_g13(
            db=db, authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id, relatorio_id=relatorio_id, xml_bytes=xml_bytes,
        )
    except EnterpriseG13GateError as exc:
        causa = str(exc)
        for nome in _COMPONENTES_ICMS_ST:
            if nome in itens:
                itens[nome]["estado"] = "falha_motor"
                itens[nome]["causa"] = causa
        saida["icms_st_g13"] = {
            "estado": "falha_motor", "causa": causa,
            "itens_total": None, "itens_simulados": None,
        }
        return saida

    # Nunca promover a apurado/autoridade_fiscal=True -- G13 e sempre
    # "simulacao condicional sem autoridade", qualquer que seja o estado.
    for nome in _COMPONENTES_ICMS_ST:
        if nome not in itens:
            continue
        itens[nome]["estado"] = "informativo_sem_prova"
        itens[nome]["causa"] = f"G13_{g13['estado']}"
        itens[nome]["autoridade_fiscal"] = False
        itens[nome]["resultado_bruto_nao_validado"] = deepcopy(g13)

    saida["icms_st_g13"] = {
        "estado": g13["estado"],
        "itens_total": g13["itens_total"],
        "itens_simulados": g13["itens_simulados"],
        "chave_nfe": g13["chave_nfe"],
        "documento_id": g13["documento_id"],
        "competencia_declarada": g13["competencia_declarada"],
    }
    saida["schema_version"] = SCHEMA_VERSION
    return saida
