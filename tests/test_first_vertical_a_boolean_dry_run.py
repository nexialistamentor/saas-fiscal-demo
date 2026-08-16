from types import SimpleNamespace

from app.main import app
from app.security import get_usuario_atual


def test_admin_executar_parsers_rejeita_string_false_antes_do_entrypoint(
    client, monkeypatch
):
    chamadas = []

    def spy_executar_parsers(*, dry_run):
        chamadas.append(dry_run)
        return {"status": "ok"}

    monkeypatch.setattr("app.main.executar_parsers", spy_executar_parsers)
    app.dependency_overrides[get_usuario_atual] = lambda: SimpleNamespace(
        role="admin"
    )

    try:
        response = client.post(
            "/admin/parsers/executar",
            json={"dry_run": "false"},
        )
    finally:
        app.dependency_overrides.pop(get_usuario_atual, None)

    assert response.status_code == 422
    assert chamadas == []
