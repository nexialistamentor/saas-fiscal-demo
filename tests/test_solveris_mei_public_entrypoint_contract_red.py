import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_solveris_mei_public_entrypoint_contract() -> None:
    vite_config = _read("frontend-dashboard/vite.config.js")
    frontend_config = _read("frontend-dashboard/src/config.js")
    index_html = _read("frontend-dashboard/index.html")
    main_source = _read("app/main.py")

    assert 'base: "/mei/"' in vite_config
    assert '"/login"' not in frontend_config
    assert "'/login'" not in frontend_config
    assert "import.meta.env.BASE_URL" in frontend_config
    assert '<html lang="pt-BR">' in index_html
    assert "<title>SOLVERIS | MEI</title>" in index_html
    assert 'href="%BASE_URL%favicon.svg"' in index_html

    main_tree = ast.parse(main_source)
    allow_origins = [
        keyword.value
        for node in ast.walk(main_tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "allow_origins"
    ]
    assert len(allow_origins) == 1
    assert isinstance(allow_origins[0], ast.List)

    origins = [
        element.value
        for element in allow_origins[0].elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    ]
    assert origins.count("https://solveris.ia.br") == 1
