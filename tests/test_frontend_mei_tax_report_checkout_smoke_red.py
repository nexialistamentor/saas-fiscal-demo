import re
from pathlib import Path

APP = (
    Path(__file__).resolve().parents[1]
    / "frontend-dashboard"
    / "src"
    / "App.jsx"
).read_text(encoding="utf-8")

checkout_start = APP.index("async function iniciarCheckout(")
checkout_end = APP.index("async function retomarAquisicaoTaxReport(", checkout_start)
CHECKOUT = APP[checkout_start:checkout_end]

recovery_call = APP.index("void recuperarTaxReportCheckoutDoServidor(idPerfil)")
RECOVERY = APP[max(0, recovery_call - 700):recovery_call]


def test_mei_cannot_reach_enterprise_tax_report_checkout():
    guard = re.search(
        r'if\s*\(\s*tipoPerfil\s*!==\s*"empresa"\s*\|\|'
        r'[^{}]*\)\s*\{\s*return\s*;?\s*\}',
        CHECKOUT,
    )
    assert guard, "CROSS_VERTICAL_CHECKOUT: MEI deve retornar antes do Tax Report"
    assert guard.end() < CHECKOUT.index("persistirTaxReportCheckoutIntent(")
    assert guard.end() < CHECKOUT.index("/checkout/one-time")


def test_mei_cannot_run_enterprise_tax_report_checkout_recovery():
    assert re.search(
        r'if\s*\(\s*tipoPerfil\s*!==\s*"empresa"\s*\|\|'
        r'[^{}]*\)\s*\{\s*return\s*;?\s*\}',
        RECOVERY,
    ), "CROSS_VERTICAL_RECOVERY: efeito Tax Report deve bloquear MEI"


def test_mei_keeps_its_own_competence_checkout_infrastructure():
    assert 'import useMeiCompetenciaCheckout from "./hooks/useMeiCompetenciaCheckout"' in APP
    assert "const checkoutMei = useMeiCompetenciaCheckout({" in APP
    assert "await checkoutMei.iniciar()" in APP
    mei_client = (
        Path(__file__).resolve().parents[1]
        / "frontend-dashboard/src/services/meiCompetenciaCheckout.js"
    ).read_text(encoding="utf-8")
    assert "tax-report-one-time-company" not in mei_client


def test_checkout_keeps_canonical_authority():
    assert "/checkout/one-time" in CHECKOUT
    assert "tax-report-one-time-company" in CHECKOUT
    assert "empresa_id: idPerfil" in CHECKOUT
