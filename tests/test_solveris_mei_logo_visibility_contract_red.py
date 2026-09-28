from pathlib import Path
import re

CSS = Path("frontend-dashboard/src/App.css").read_text(encoding="utf-8")


def blocks(selector):
    pattern = r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}"
    return re.findall(pattern, CSS)


def test_solveris_logo_has_mobile_prominence():
    logo = blocks(".solveris-brand-lockup .solveris-logo")
    brand = blocks(".solveris-brand-lockup")

    assert len(logo) >= 2
    assert len(brand) >= 2

    # A imagem deve manter proporções e distinguir-se do fundo.
    assert "border:" in logo[0]

    mobile_width = re.search(r"\bwidth:\s*(\d+)px", logo[-1])
    mobile_height = re.search(r"\bheight:\s*(\d+)px", logo[-1])

    assert mobile_width and mobile_height
    assert int(mobile_width.group(1)) >= 104
    assert mobile_width.group(1) == mobile_height.group(1)

    # No celular, a marca deve ter espaço próprio, sem comprimir o título.
    assert "flex-direction: column-reverse" in brand[-1]
