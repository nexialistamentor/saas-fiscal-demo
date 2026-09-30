"""Both AST readers accept one UTF-8 BOM without hiding malformed source."""

import ast
import codecs

import pytest

from app.scripts import mei_publication_reachability_census as census


SOURCE = 'class Example:\n    def run(self):\n        return "ação"\n'


@pytest.fixture
def source_path(tmp_path, monkeypatch):
    monkeypatch.setattr(census, "ROOT", tmp_path)
    path = tmp_path / "app" / "example.py"
    path.parent.mkdir()
    census._app_class_defines_method.cache_clear()
    yield path
    census._app_class_defines_method.cache_clear()


@pytest.mark.parametrize("prefix", [b"", codecs.BOM_UTF8])
def test_readers_preserve_ast_and_source_bytes(source_path, prefix):
    raw = prefix + SOURCE.encode("utf-8")
    source_path.write_bytes(raw)

    module = census._parse_app()["app.example"]
    expected = ast.parse(SOURCE, filename=str(source_path))
    assert ast.dump(module.tree, include_attributes=True) == ast.dump(
        expected, include_attributes=True
    )
    assert "Example" in {node.name for node in module.tree.body}
    assert census._app_class_defines_method("app.example.Example", "run") is True
    assert census._app_class_defines_method("app.example.Example", "missing") is False
    assert source_path.read_bytes() == raw


@pytest.mark.parametrize("reader", ["inventory", "class"])
@pytest.mark.parametrize(
    "raw,error_type",
    [
        (b"\xff", "UnicodeDecodeError"),
        (codecs.BOM_UTF8 + b"def broken(:\n", "SyntaxError"),
        (codecs.BOM_UTF8 * 2 + SOURCE.encode("utf-8"), "SyntaxError"),
        (b"x = 1\n" + codecs.BOM_UTF8 + b"y = 2\n", "SyntaxError"),
    ],
)
def test_readers_remain_fail_closed_on_invalid_source(source_path, reader, raw, error_type):
    source_path.write_bytes(raw)
    prefix = "MEI_REACHABILITY_SCAN_FAILED" if reader == "inventory" else "MEI_REACHABILITY_CLASS_SCAN_FAILED"
    with pytest.raises(RuntimeError, match=f"{prefix}.*{error_type}"):
        if reader == "inventory":
            census._parse_app()
        else:
            census._app_class_defines_method("app.example.Example", "run")
    assert source_path.read_bytes() == raw
