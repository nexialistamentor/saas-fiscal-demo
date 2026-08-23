import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _tree(relative):
    return ast.parse(
        (ROOT / relative).read_text(encoding="utf-8"),
        filename=relative,
    )


def _function(tree, name):
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def _call_name(call):
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = [func.attr]
        current = func.value
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
    return None


def _calls(node, name):
    return [
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and _call_name(item) == name
    ]


def test_xml_persistence_seals_result_before_finalizer():
    tree = _tree("app/services/registro_analise_service.py")
    fn = _function(tree, "executar_e_registrar_analise_xml")

    assert len(_calls(fn, "selar_resultado_nao_mei")) == 1


def test_finalizer_uses_central_fingerprint_function():
    tree = _tree("app/services/registro_analise_service.py")
    fn = _function(tree, "finalizar_registro_analise")

    assert len(_calls(fn, "fingerprint_resultado_json")) == 1


def test_relatorio_mei_tax_direct_writer_seals_and_fingerprints_result():
    tree = _tree("app/routes/relatorio_router.py")
    fn = _function(tree, "gerar_relatorio_mei_tax")

    assert len(_calls(fn, "selar_resultado_nao_mei")) == 1
    assert len(_calls(fn, "fingerprint_resultado_json")) == 1


def test_generic_relatorio_reads_only_verified_persisted_payload():
    tree = _tree("app/routes/relatorio_router.py")
    fn = _function(tree, "obter_relatorio")

    assert len(_calls(fn, "verificar_resultado_persistido")) == 1
    assert not any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "rel"
        and node.attr == "resultado_json"
        for node in ast.walk(fn)
    )


def test_mei_tax_get_reads_only_verified_persisted_payload():
    tree = _tree("app/routes/relatorio_router.py")
    fn = _function(tree, "buscar_relatorio_mei_tax")

    assert len(_calls(fn, "verificar_resultado_persistido")) == 1
    assert not any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "rel"
        and node.attr == "resultado_json"
        for node in ast.walk(fn)
    )


def test_dashboard_opportunities_reads_only_verified_persisted_payload():
    tree = _tree("app/routers/dashboard_router.py")
    fn = _function(tree, "oportunidades_por_relatorio")

    assert len(_calls(fn, "verificar_resultado_persistido")) == 1
    assert not any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "rel"
        and node.attr == "resultado_json"
        for node in ast.walk(fn)
    )
