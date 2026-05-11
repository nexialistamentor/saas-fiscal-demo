"""
Testes do motor de confiança documental soberano — V1 heurístico.
"""

from app.services.document_ingestion.confidence import (
    DecisaoProcessamento,
    LIMITE_AUTO,
    LIMITE_FILA,
    calcular,
)


def test_texto_vazio_rejeita():
    r = calcular("")
    assert r.decisao == DecisaoProcessamento.REJEITAR
    assert r.score == 0.0


def test_texto_sem_campos_fiscais_rejeita():
    r = calcular("lorem ipsum dolor sit amet")
    assert r.decisao == DecisaoProcessamento.REJEITAR
    assert r.score < LIMITE_FILA


def test_documento_rico_auto_processa():
    texto = (
        "DANFE DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA "
        "CNPJ 12.345.678/0001-90 Chave de Acesso 1234 "
        "CFOP 5102 ICMS 12% valor total R$ 1.500,00 "
        "base de calculo aliquota NCM 84713012 "
        "emitente destinatario data de emissao"
    )
    r = calcular(texto, requer_ocr=False)
    assert r.decisao == DecisaoProcessamento.AUTO_PROCESSAR
    assert r.score >= LIMITE_AUTO


def test_penalidade_ocr_reduz_score():
    texto = (
        "DANFE CNPJ Chave de Acesso CFOP ICMS "
        "valor total base de calculo aliquota NCM "
        "emitente destinatario data de emissao"
    )
    sem_ocr = calcular(texto, requer_ocr=False)
    com_ocr = calcular(texto, requer_ocr=True)
    assert com_ocr.score < sem_ocr.score


def test_documento_parcial_fila_homologacao():
    texto = "nota fiscal CNPJ emitente valor total"
    r = calcular(texto, requer_ocr=False)
    assert r.decisao in (
        DecisaoProcessamento.FILA_HOMOLOGACAO,
        DecisaoProcessamento.REJEITAR,
    )


def test_campos_detectados_listados():
    texto = "CNPJ 12.345.678/0001-90 CFOP 5102 ICMS"
    r = calcular(texto)
    assert "cnpj" in r.campos_detectados
    assert "cfop" in r.campos_detectados
    assert "icms" in r.campos_detectados


def test_score_entre_0_e_100():
    for texto in ["", "CNPJ CFOP ICMS valor total DANFE chave de acesso", "x" * 1000]:
        r = calcular(texto)
        assert 0.0 <= r.score <= 100.0


def test_motivos_sempre_presentes():
    r = calcular("qualquer texto")
    assert len(r.motivos) > 0
