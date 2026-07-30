from app.services import assistente_service
from app.services.assistente_service import extrair_ano_referencia


def test_ano_temporal_prevalece_sobre_faturamento_que_parece_ano():
    resultado = extrair_ano_referencia(
        "quanto pago de MEI em 2026 com 2000 por mes"
    )

    assert resultado == 2026


def test_ano_de_referencia_explicito_prevalece_sobre_valor_financeiro():
    resultado = extrair_ano_referencia(
        "ano de referencia 2026 com faturamento de 2025 por mes"
    )

    assert resultado == 2026


def test_faturamento_2000_sem_contexto_temporal_nao_vira_ano():
    resultado = extrair_ano_referencia(
        "faturamos 2000 por mes"
    )

    assert resultado is None


def test_anos_temporais_conflitantes_nao_sao_resolvidos_por_posicao():
    resultado = extrair_ano_referencia(
        "compare as regras do MEI em 2025 e em 2026"
    )

    assert resultado is None


def test_ano_unico_sem_marcador_temporal_preserva_contrato_legado():
    resultado = extrair_ano_referencia(
        "regra do MEI 2026"
    )

    assert resultado == 2026


def test_mei_entrega_ano_temporal_e_faturamento_correctos_ao_motor(
    monkeypatch,
):
    chamada = {}

    def fake_engine(analysis_type, dados):
        chamada["analysis_type"] = analysis_type
        chamada["dados"] = dados
        return {
            "tributos": {"das": 82.05},
            "alertas": [],
        }

    monkeypatch.setattr(
        assistente_service,
        "executar_analise",
        fake_engine,
    )

    resultado = assistente_service._resposta_assistente_mei(
        "quanto pago de MEI em 2026 com 2000 por mes"
    )

    assert chamada["analysis_type"] == "mei_tax"
    assert chamada["dados"]["faturamento"] == 2_000
    assert chamada["dados"]["ano_referencia"] == 2026
    assert resultado.get("bloqueado") is not True
