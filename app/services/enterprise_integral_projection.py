"""I0 Enterprise: censo executavel e projeção PURA, INTERNA, sem autoridade comercial.

Entrada: payload empresarial ja verificado na fronteira de chamada, nunca dados HTTP crus.
Saida: manifesto deterministico dos motores/capacidades e suas lacunas.
Nao interpreta lei, nao recalcula tributos, nao grava BD, nao concede direito a pagamento.
Alem disso, a integridade externa/fingerprint NAO e verificada aqui.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite


class EnterpriseIntegralProjectionError(ValueError):
    """Recusa projeção cujo sujeito ou estrutura foram corrompidos."""


# (id unico, grupo, tipo de origem, chave no snapshot, caminho opcional).
# source='pendente' significa que o produtor existe, mas nao ha vinculo ao caso.
# Nenhum produtor assinalado como 'pendente' e automaticamente executado.
_CAPACIDADES = (
    ("pis", "tributos", "engine", "pis_cofins", ("tributos", "pis")),
    ("cofins", "tributos", "engine", "pis_cofins", ("tributos", "cofins")),
    ("credito_pis", "tributos", "engine", "pis_cofins", ("creditos", "pis")),
    ("credito_cofins", "tributos", "engine", "pis_cofins", ("creditos", "cofins")),
    ("irpj", "tributos", "engine", "irpj", ()),
    ("irpj_adicional", "tributos", "engine", "irpj", ("adicional_irpj",)),
    ("csll", "tributos", "engine", "csll", ()),
    ("lucro_real", "regimes", "engine", "lucro_real", ()),
    ("lucro_presumido", "regimes", "engine", "lucro_presumido", ()),
    ("planejamento_tributario", "regimes", "engine", "tax_planning", ()),
    ("recuperacao_tributaria", "tributos", "engine", "tax_recovery", ()),
    ("comparativo_regime", "regimes", "snapshot", "comparativo_regime", ()),
    ("simples_fator_r", "regimes", "pendente", "regime_engine", ()),
    ("icms_st", "icms_st", "pendente", "st_service", ()),
    ("mva", "icms_st", "pendente", "fiscal_utils", ()),
    ("pmpf", "icms_st", "pendente", "tabela_normativa_service", ()),
    ("consistencia_fiscal", "icms_st", "pendente", "tax_consistency_engine", ()),
    ("creditos_st", "icms_st", "snapshot", "creditos_detectados", ()),
    ("distorcoes_st_mva", "icms_st", "snapshot", "oportunidades", ()),
    ("restituicao_st", "icms_st", "pendente", "st_service_restituicao", ()),
    ("cnae", "classificacao", "pendente", "cnae_engine", ()),
    ("ncm", "classificacao", "pendente", "classificacao_ncm", ()),
    ("nfe_xml", "documentos", "snapshot", "dados_fiscais", ()),
    ("insights_documentais", "documentos", "snapshot", "insights.documental", ()),
    ("danfe_ocr", "documentos", "pendente", "document_ingestion", ()),
    ("conciliacao_danfe_xml", "documentos", "pendente", "conciliacao_danfe_xml", ()),
    ("nfse_efd_recolhimentos", "documentos", "pendente", "fontes_complementares", ()),
    ("risco_tributario", "inteligencia", "snapshot", "risco_tributario", ()),
    ("score_tributario", "inteligencia", "pendente", "score_global_tributario_service", ()),
    ("ranking_restituicao", "inteligencia", "pendente", "ranking_restituicao_service", ()),
    ("ranking_estrategico", "inteligencia", "pendente", "ranking_estrategico_service", ()),
    ("mapa_oportunidades", "inteligencia", "snapshot", "oportunidades", ()),
    ("previsao_recuperacao", "inteligencia", "snapshot", "previsao_recuperacao", ()),
    ("projecao_recuperacao", "inteligencia", "pendente", "projecao_recuperacao_service", ()),
    ("impacto_financeiro", "inteligencia", "pendente", "impacto_financeiro_service", ()),
    ("anomalias", "inteligencia", "pendente", "anomalias_tributarias_service", ()),
    ("eficiencia", "inteligencia", "pendente", "eficiencia_tributaria_service", ()),
    ("complexidade", "inteligencia", "pendente", "complexidade_tributaria_service", ()),
    ("maturidade", "inteligencia", "pendente", "maturidade_tributaria_service", ()),
    ("benchmark", "inteligencia", "pendente", "benchmark_fiscal_service", ()),
    ("radar", "inteligencia", "pendente", "radar_tributario_service", ()),
    ("historico", "temporal", "pendente", "historico_inteligencia_service", ()),
    ("tendencia", "temporal", "pendente", "tendencia_inteligencia_service", ()),
    ("comparacao_temporal", "temporal", "pendente", "comparacao_temporal_service", ()),
    ("normativa_l2", "normativa", "pendente", "source_authority_guard", ()),
    ("adr020", "normativa", "pendente", "adr020_bindings", ()),
    ("parsers_dou_sefaz", "normativa", "pendente", "orquestrador_parsers", ()),
    ("agentes_l3", "agentes", "pendente", "agent_executor", ()),
    ("reforma_cbs_ibs", "normativa", "pendente", "reforma_tributaria", ()),
    ("aquisição_enterprise", "comercial", "pendente", "enterprise_diagnostic_documental", ()),
    ("pdf_enterprise", "comercial", "pendente", "enterprise_paid_report_pdf", ()),
    ("dashboard_enterprise", "comercial", "pendente", "useEmpresaDashboard", ()),
)

SCHEMA_VERSION = "ENTERPRISE_INTEGRAL_I0_V1"
ESTADOS = frozenset({"informativo_sem_prova", "nao_apurado", "falha_motor", "nao_integrado_ao_snapshot"})


def catalogo_integral() -> tuple[dict, ...]:
    """Manifesto integral de cobertura; nao contem alegacoes sobre runtime."""
    return tuple(
        {"id": nome, "grupo": grupo, "origem": origem,
         "produtor_ou_chave": chave, "caminho": list(caminho)}
        for nome, grupo, origem, chave, caminho in _CAPACIDADES
    )


def _campo(source: object, path: tuple[str, ...]):
    for part in path:
        if type(source) is not dict or part not in source:
            return None
        source = source[part]
    return source


def _valor_sensivel(nome: str, value: object) -> bool:
    # campos financeiros destacados so sao apresentados como material interno,
    # nunca como credito/prova/autorizacao de venda.
    if nome not in {"pis", "cofins", "credito_pis", "credito_cofins", "irpj_adicional"}:
        return False
    return type(value) not in (int, float) or (type(value) is float and not isfinite(value))


def projetar_diagnostico_integral_i0(*, resultado: dict, empresa_id: int) -> dict:
    """Produz censo + projecao interna, SEM fiscalizar ou habilitar checkout.

    Chamar APENAS apos validar posse da empresa, snapshot/fingerprint/proveniencia
    e permissao na camada de origem. Este modulo nao substitui essas fronteiras.
    """
    if type(empresa_id) is not int or empresa_id <= 0:
        raise EnterpriseIntegralProjectionError("I0_EMPRESA_ID_INVALIDO")
    if type(resultado) is not dict or type(resultado.get("empresa_id")) is not int:
        raise EnterpriseIntegralProjectionError("I0_RESULTADO_INVALIDO")
    if resultado["empresa_id"] != empresa_id:
        raise EnterpriseIntegralProjectionError("I0_EMPRESA_DIVERGENTE")
    engines = resultado.get("resultados_engines")
    if engines is not None and type(engines) is not dict:
        raise EnterpriseIntegralProjectionError("I0_ENGINES_ESTRUTURA_INVALIDA")
    engines = engines or {}
    flags = resultado.get("context_flags")
    incomplete = (
        type(flags) is dict
        and type(flags.get("empresarial")) is dict
        and flags["empresarial"].get("dados_incompletos") is True
    )
    capacidades = []
    for nome, grupo, origem, chave, caminho in _CAPACIDADES:
        entry = {"id": nome, "grupo": grupo, "origem": origem,
                 "produtor_ou_chave": chave, "estado": "nao_apurado",
                 "causa": None, "autoridade_fiscal": False,
                 "resultado_bruto_nao_validado": None}
        if origem == "pendente":
            entry["estado"] = "nao_integrado_ao_snapshot"
            entry["causa"] = "PRODUTOR_EXISTENTE_OU_PLANEADO_SEM_VINCULO_CAUSAL_NESTE_RESULTADO"
        else:
            if origem == "engine":
                source = engines.get(chave)
                if type(source) is dict and ("erro" in source or source.get("estado_l3") == "bloqueado"):
                    entry["estado"] = "falha_motor"
                    entry["causa"] = str(source.get("codigo") or "MOTOR_SEM_RESULTADO_AUTORIZADO")
                    capacidades.append(entry)
                    continue
            elif chave == "insights.documental":
                source = _campo(resultado, ("insights", "documental"))
            else:
                source = resultado.get(chave)
            part = _campo(source, caminho)
            if part is None or _valor_sensivel(nome, part):
                entry["estado"] = "nao_apurado"
                entry["causa"] = "CAMPO_OU_RESULTADO_AUSENTE_OU_INVALIDO"
            else:
                entry["estado"] = "informativo_sem_prova"
                entry["causa"] = "SEM_VINCULO_ITEM_NORMA_ESCRITURACAO_E_RECOLHIMENTO"
                entry["resultado_bruto_nao_validado"] = deepcopy(part)
                if incomplete:
                    entry["causa"] = "CONTEXTO_EMPRESARIAL_INCOMPLETO_SEM_PROVA_CONCLUSIVA"
                if nome in {"pis", "cofins", "credito_pis", "credito_cofins"}:
                    entry["causa"] = "PIS_COFINS_BASE_ICMS_PROPRIO_NAO_VERIFICADA_ST_NAO_E_ICMS_PROPRIO"
        capacidades.append(entry)
    ids_registrados = {chave for _, _, origem, chave, _ in _CAPACIDADES if origem == "engine"}
    nao_catalogadas = sorted(chave for chave in engines if chave not in ids_registrados)
    return {
        "schema_version": SCHEMA_VERSION,
        "empresa_id": empresa_id,
        "uso": "INTERNO_NAO_PUBLICAVEL",
        "checkout_autorizado": False,
        "diagnostico_empresarial_completo": False,
        "comprovacao_normativa": False,
        "cobertura": capacidades,
        "engines_nao_catalogadas": nao_catalogadas,
        "exige_ratificacao_para_expor_pdf_api_ui": True,
    }


__all__ = ["SCHEMA_VERSION", "ESTADOS", "EnterpriseIntegralProjectionError",
           "catalogo_integral", "projetar_diagnostico_integral_i0"]
