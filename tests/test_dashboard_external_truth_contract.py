import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend-dashboard" / "src" / "App.jsx"
EMPRESA_HOOK = ROOT / "frontend-dashboard" / "src" / "hooks" / "useEmpresaDashboard.js"
PDF_SERVICE = ROOT / "app" / "services" / "pdf_report_service.py"


def test_dashboard_does_not_use_fictitious_evolution_series():
    app = APP.read_text(encoding="utf-8")
    fictitious_series = r"P1[\s\S]*?20[\s\S]*?P2[\s\S]*?35[\s\S]*?P3[\s\S]*?30[\s\S]*?P4[\s\S]*?48[\s\S]*?P5[\s\S]*?52"

    assert not re.search(fictitious_series, app)


def test_score_global_is_not_renamed_as_recuperacao():
    app = APP.read_text(encoding="utf-8")

    assert not re.search(r"\brecuperacao\s*:\s*item\.score_global\b", app)


def test_missing_risco_tributario_percentual_remains_unavailable():
    hook = EMPRESA_HOOK.read_text(encoding="utf-8")
    risco_assignment = re.search(
        r"\bconst\s+risco\s*=\s*(?P<value>.*?)(?=\bconst\s+pontuacao\b)",
        hook,
        flags=re.DOTALL,
    )

    assert risco_assignment is not None
    assert "?? 0" not in risco_assignment.group("value")
    assert "-1" in risco_assignment.group("value")


def test_pdf_does_not_present_score_global_as_tax_score():
    pdf_service = PDF_SERVICE.read_text(encoding="utf-8")

    assert not re.search(
        r"score\s*=\s*relatorio\.get\([\"']score_global[\"']\)[\s\S]{0,300}Score tribut.rio",
        pdf_service,
    )


def test_ncm_distribution_surface_is_not_backed_by_hardcoded_empty_data():
    app = APP.read_text(encoding="utf-8")
    hardcoded_empty_ncm = re.search(r"\bconst\s+dadosNCM\s*=\s*\[\s*\]", app)
    ncm_distribution_surface = re.search(
        r"Distribui..o por NCM[\s\S]{0,1500}data\s*=\s*\{dadosNCM\}",
        app,
    )

    assert not (hardcoded_empty_ncm and ncm_distribution_surface)
