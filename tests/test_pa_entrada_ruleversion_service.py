"""Fase 4: contrato condicional PA sem qualquer promocao fiscal."""
from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace

from app.models import ExtractionResult, NormativeArtifact, RuleVersion
from app.services.pa_entrada_ruleversion_service import cotejar_candidato_pa_entrada


H = "a" * 64
I = "b" * 64
J = "c" * 64


class DBFalsa:
    def __init__(self, records):
        self.records = records
        self.calls = 0
        self.no_autoflush = nullcontext()

    def get(self, model, ident):
        self.calls += 1
        return self.records.get((model, ident))


def _caso():
    data = {
        "pa_entrada_22021000_v1": {
            "uf_operacao": "PA", "ncm": "22021000", "cest": "0301001",
            "categoria_remetente": "distribuidor_deposito_atacadista",
            "tipo_operacao": "antecipacao_na_entrada",
            "vigencia_inicio": "2024-01-01", "vigencia_fim": None,
            "mva_percentual": "40", "aliquota_interna_percentual": "21",
        }
    }
    rule = SimpleNamespace(
        rule_version_record_id="rv-pa-1", extraction_result_id="ex-pa-1",
        extraction_result_record_hash=I, rule_hash=H, record_hash=J,
        structured_content=data,
        declared_material_validity={"vigencia_inicio": "2024-01-01", "vigencia_fim": None},
    )
    extraction = SimpleNamespace(
        extraction_result_id="ex-pa-1", record_hash=I,
        normative_artifact_id="doc-pa-1", artifact_hash=H,
        outcome="conclusivo", structured_content=data,
    )
    artifact = SimpleNamespace(normative_artifact_id="doc-pa-1", artifact_hash=H)
    db = DBFalsa({
        (RuleVersion, "rv-pa-1"): rule,
        (ExtractionResult, "ex-pa-1"): extraction,
        (NormativeArtifact, "doc-pa-1"): artifact,
    })
    args = dict(db=db, rule_version_record_id="rv-pa-1", uf_operacao="PA",
                ncm="22021000", cest="0301001",
                categoria_remetente="distribuidor_deposito_atacadista",
                tipo_operacao="antecipacao_na_entrada",
                data_referencia=date(2024, 6, 1))
    return rule, extraction, artifact, args


def test_cadeia_exata_cotejada_nunca_autoriza_calculo():
    _, _, _, args = _caso()
    resultado = cotejar_candidato_pa_entrada(**args)
    assert resultado["estado"] == "CANDIDATO_CONDICIONAL_COTEJADO_SEM_AUTORIDADE"
    assert resultado["vinculos_declarados_cotejados"] is True
    assert resultado["autoridade_normativa_verificada"] is False
    assert resultado["calculo_autorizado"] is False
    assert resultado["norma_resolvida"] is None
    assert "mva" not in resultado and "aliquota" not in resultado


def test_remetente_ausente_bloqueia_sem_consultar_o_banco():
    _, _, _, args = _caso()
    args["categoria_remetente"] = None
    resultado = cotejar_candidato_pa_entrada(**args)
    assert resultado["estado"] == "ABSTENCAO"
    assert resultado["calculo_autorizado"] is False
    assert args["db"].calls == 0


def test_nao_inferir_modalidade_ou_cest():
    for campo, valor in (("tipo_operacao", "saida_interna"), ("cest", None),
                          ("uf_operacao", "SP"), ("ncm", "22029900")):
        _, _, _, args = _caso()
        args[campo] = valor
        assert cotejar_candidato_pa_entrada(**args)["estado"] == "ABSTENCAO"
        assert args["db"].calls == 0


def test_identidade_documental_divergente_bloqueia():
    _, extraction, _, args = _caso()
    extraction.artifact_hash = "f" * 64
    resultado = cotejar_candidato_pa_entrada(**args)
    assert resultado["motivo"] == "IDENTIDADE_DOCUMENTAL_DIVERGENTE"
    assert resultado["calculo_autorizado"] is False


def test_contrato_saida_interna_na_ruleversion_nao_entra():
    rule, _, _, args = _caso()
    rule.structured_content = {
        "g113_v1": {"operacao": "saida_interna"},
    }
    resultado = cotejar_candidato_pa_entrada(**args)
    assert resultado["motivo"] == "CONTRATO_REGRA_EXTRACAO_INCOMPATIVEL"


def test_regra_fora_da_vigencia_bloqueia():
    _, _, _, args = _caso()
    args["data_referencia"] = date(2023, 12, 31)
    resultado = cotejar_candidato_pa_entrada(**args)
    assert resultado["motivo"] == "VIGENCIA_OU_PARAMETROS_NAO_COTEJADOS"
    assert resultado["calculo_autorizado"] is False


def test_sem_ruleversion_bloqueia():
    _, _, _, args = _caso()
    args["db"] = DBFalsa({})
    resultado = cotejar_candidato_pa_entrada(**args)
    assert resultado["motivo"] == "CADEIA_ADR020_INCOMPLETA"


def test_nenhuma_saida_habilita_numeros_mesmo_com_registo_completo():
    rule, _, _, args = _caso()
    rule.structured_content["pa_entrada_22021000_v1"]["mva_percentual"] = "140"
    resultado = cotejar_candidato_pa_entrada(**args)
    assert resultado["motivo"] == "VIGENCIA_OU_PARAMETROS_NAO_COTEJADOS"
    assert resultado["calculo_autorizado"] is False
    assert resultado["norma_resolvida"] is None


def test_cest_0301100_requer_mva_70_para_distribuidor():
    rule, _, _, args = _caso()
    args["cest"] = "0301100"
    data = rule.structured_content["pa_entrada_22021000_v1"]
    data["cest"] = "0301100"
    data["mva_percentual"] = "70"
    assert cotejar_candidato_pa_entrada(**args)["vinculos_declarados_cotejados"] is True


def test_industrial_requer_mva_140():
    rule, _, _, args = _caso()
    args["categoria_remetente"] = "industrial_importador_arrematante_engarrafador"
    data = rule.structured_content["pa_entrada_22021000_v1"]
    data["categoria_remetente"] = args["categoria_remetente"]
    data["mva_percentual"] = "140"
    assert cotejar_candidato_pa_entrada(**args)["vinculos_declarados_cotejados"] is True


def test_metadados_externos_a_subchave_podem_diferir():
    rule, extraction, _, args = _caso()
    rule.structured_content["metadata_regra"] = {"origem": "rule_version"}
    extraction.structured_content = {
        **extraction.structured_content,
        "metadata_extracao": {"origem": "extraction_result"},
    }
    resultado = cotejar_candidato_pa_entrada(**args)
    assert resultado["estado"] == "CANDIDATO_CONDICIONAL_COTEJADO_SEM_AUTORIDADE"
    assert resultado["vinculos_declarados_cotejados"] is True
    assert resultado["calculo_autorizado"] is False


def test_divergencia_dentro_da_subchave_bloqueia():
    from copy import deepcopy
    _, extraction, _, args = _caso()
    extraction.structured_content = deepcopy(extraction.structured_content)
    extraction.structured_content["pa_entrada_22021000_v1"]["mva_percentual"] = "140"
    resultado = cotejar_candidato_pa_entrada(**args)
    assert resultado["estado"] == "ABSTENCAO"
    assert resultado["motivo"] == "CONTRATO_REGRA_EXTRACAO_INCOMPATIVEL"
    assert resultado["calculo_autorizado"] is False
    assert resultado["norma_resolvida"] is None
