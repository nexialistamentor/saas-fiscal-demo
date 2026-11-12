"""Integração cirúrgica dos cinco produtores já invocados pelo escritor."""
from copy import deepcopy
import pytest

from app.services.enterprise_integral_projection import projetar_diagnostico_integral_i0
from app.services.resultado_empresarial_service import compor_resultado_empresarial


EMPRESA = 41
RELATORIO = 21
SHA = "a" * 64
FIVE = ("score_tributario", "maturidade", "ranking_restituicao",
        "ranking_estrategico", "impacto_financeiro")


def _input(capturas=None):
    dados = capturas if capturas is not None else {
        "score_tributario": {"score_global_tributario": 8.4, "nivel_empresa": "em_desenvolvimento"},
        "maturidade": {"score_maturidade_tributaria": 15.0, "nivel_maturidade": "iniciante"},
        "ranking_restituicao": [{"ncm": "12345678", "restituicao_estimada": 9.2}],
        "ranking_estrategico": [{"ncm": "12345678", "score": 8, "potencial": 4, "creditos": 3, "distorcao": 1}],
        "impacto_financeiro": [{"ncm": "12345678", "impacto_anual_estimado": 12.0, "prioridade_fiscal": 13.0}],
    }
    bruto = compor_resultado_empresarial(
        EMPRESA, {"dados_fiscais": {}},
        {"empresa_id": EMPRESA, "inteligencia_capturas": {
            "empresa_id": EMPRESA, "relatorio_id": RELATORIO, "dados": dados,
        }},
    )
    bruto["_enterprise_xml_evidence"] = {
        "schema_version": "ENTERPRISE_XML_EVIDENCE_V1", "empresa_id": EMPRESA,
        "relatorio_id": RELATORIO, "xml_sha256": SHA,
    }
    return bruto


def _bridge(raw):
    from app.services.enterprise_inteligencia_i0_bridge import fundir_inteligencia_i0
    original = projetar_diagnostico_integral_i0(resultado=raw, empresa_id=EMPRESA)
    original_copy = deepcopy(original)
    output = fundir_inteligencia_i0(i0=original, resultado=raw, empresa_id=EMPRESA,
                                  relatorio_id=RELATORIO, xml_sha256=SHA)
    assert original == original_copy  # sem mutação da base
    assert len(output["cobertura"]) == 52
    assert output["checkout_autorizado"] is False
    assert output["diagnostico_empresarial_completo"] is False
    assert output["comprovacao_normativa"] is False
    return {x["id"]: x for x in output["cobertura"]}


def test_captura_cinco_produtores_preserva_brutos_sem_promover_autoridade():
    raw = _input()
    first = deepcopy(raw)
    coverage = _bridge(raw)
    assert raw == first
    for name in FIVE:
        assert coverage[name]["estado"] == "informativo_sem_prova"
        assert coverage[name]["autoridade_fiscal"] is False
        assert coverage[name]["resultado_bruto_nao_validado"] == raw["inteligencia_capturas"]["dados"][name]
    assert coverage["radar"]["estado"] == "nao_integrado_ao_snapshot"
    assert coverage["benchmark"]["estado"] == "nao_integrado_ao_snapshot"
    assert coverage["projecao_recuperacao"]["estado"] == "nao_integrado_ao_snapshot"


def test_lista_vazia_esta_executada_mas_nao_apurada():
    raw = _input()
    raw["inteligencia_capturas"]["dados"]["ranking_restituicao"] = []
    coverage = _bridge(raw)
    assert coverage["ranking_restituicao"]["estado"] == "nao_apurado"
    assert coverage["ranking_restituicao"]["autoridade_fiscal"] is False


def test_ausencia_nao_promove_pendentes():
    raw = _input({"score_tributario": {"score_global_tributario": 1.2, "nivel_empresa": "em_desenvolvimento"}})
    coverage = _bridge(raw)
    assert coverage["score_tributario"]["estado"] == "informativo_sem_prova"
    for name in FIVE[1:]:
        assert coverage[name]["estado"] == "nao_integrado_ao_snapshot"


@pytest.mark.parametrize("key,value", [
    ("score_tributario", {}),
    ("maturidade", {"nivel_maturidade": "iniciante"}),
    ("ranking_restituicao", {"ncm": "12345678"}),
    ("ranking_estrategico", [{"foo": 1}]),
    ("impacto_financeiro", [{"impacto_anual_estimado": float("nan")}]),
])
def test_payload_invalido_falha_fechado(key,value):
    raw = _input()
    raw["inteligencia_capturas"]["dados"][key] = value
    coverage = _bridge(raw)
    assert coverage[key]["estado"] == "falha_motor"
    assert coverage[key]["resultado_bruto_nao_validado"] is None
    assert coverage[key]["autoridade_fiscal"] is False


@pytest.mark.parametrize("mutation", ["empresa", "relatorio", "sha", "i0"])
def test_vinculo_rejeita_identidade_divergente(mutation):
    from app.services.enterprise_inteligencia_i0_bridge import fundir_inteligencia_i0
    raw = _input()
    i0 = projetar_diagnostico_integral_i0(resultado=raw, empresa_id=EMPRESA)
    if mutation == "empresa":
        raw["inteligencia_capturas"]["empresa_id"] = 999
    elif mutation == "relatorio":
        raw["inteligencia_capturas"]["relatorio_id"] = 999
    elif mutation == "sha":
        raw["_enterprise_xml_evidence"]["xml_sha256"] = "b" * 64
    else:
        i0["empresa_id"] = 999
    with pytest.raises(ValueError, match="INTELIGENCIA_"):
        fundir_inteligencia_i0(i0=i0, resultado=raw, empresa_id=EMPRESA,
                               relatorio_id=RELATORIO, xml_sha256=SHA)


def test_ranking_produtores_executam_uma_vez_e_preservam_todas_linhas(monkeypatch):
    from unittest.mock import MagicMock
    from app.services import insights_engine as mod

    engine = mod.InsightEngine(MagicMock())
    capturas = {}
    table = {
        "ranking_restituicao": (
            "gerar_ranking_restituicao", "_analisar_ranking_restituicao",
            [{"ncm": str(i).zfill(8), "restituicao_estimada": float(i), "percentual_impacto": 0,
              "aliquota_fonte": "teste"} for i in range(1, 8)]
        ),
        "ranking_estrategico": (
            "gerar_ranking_estrategico", "_analisar_ranking_estrategico",
            [{"ncm": str(i).zfill(8), "score": i, "potencial": i, "creditos": i,
              "distorcao": i} for i in range(1, 8)]
        ),
        "impacto_financeiro": (
            "calcular_impacto_financeiro", "_analisar_impacto_financeiro",
            [{"ncm": str(i).zfill(8), "impacto_anual_estimado": float(i),
              "prioridade_fiscal": float(i)} for i in range(1, 8)]
        ),
    }
    for cap, (produtor, metodo, esperado) in table.items():
        mock = MagicMock(return_value=deepcopy(esperado))
        monkeypatch.setattr(mod, produtor, mock)
        resumidos = getattr(engine, metodo)(EMPRESA, capturas=capturas)
        mock.assert_called_once_with(engine.db, EMPRESA)
        assert len(resumidos) == 5
        assert len(capturas[cap]) == len(esperado)  # captura ANTES do top 5
        assert capturas[cap] == esperado
    capturas["ranking_restituicao"][0]["ncm"] = "99999999"
    assert table["ranking_restituicao"][2][0]["ncm"] == "00000001"


def test_snapshot_antigo_sem_capturas_permanece_pendente():
    raw = _input()
    del raw["inteligencia_capturas"]
    coverage = _bridge(raw)
    for nome in FIVE:
        assert coverage[nome]["estado"] == "nao_integrado_ao_snapshot"
