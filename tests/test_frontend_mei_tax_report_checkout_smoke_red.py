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


def test_mei_can_reach_checkout():
    assert re.search(
        r'\(tipoPerfil\s*!==\s*"empresa"\s*&&\s*'
        r'tipoPerfil\s*!==\s*"mei"\)\s*\|\|',
        CHECKOUT,
    )


def test_mei_can_run_checkout_recovery():
    assert re.search(
        r'\(tipoPerfil\s*!==\s*"empresa"\s*&&\s*'
        r'tipoPerfil\s*!==\s*"mei"\)\s*\|\|',
        RECOVERY,
    )


def test_checkout_keeps_canonical_authority():
    assert "/checkout/one-time" in CHECKOUT
    assert "tax-report-one-time-company" in CHECKOUT
    assert "empresa_id: idPerfil" in CHECKOUT
