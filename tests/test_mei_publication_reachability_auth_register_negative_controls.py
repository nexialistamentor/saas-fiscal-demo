import ast

from app.scripts import mei_publication_reachability_census as census_module


ENTRYPOINT = "/auth/register"


def _assert_not_no_canonical(modules, monkeypatch):
    monkeypatch.setattr(census_module, "_parse_app", lambda: modules)

    try:
        census = census_module.build_census()
    except RuntimeError:
        return

    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == ENTRYPOINT
    )
    assert path["mei_reachability"] != "NO_CANONICAL_MEI_PRODUCER"


def _class(module, name):
    matches = [
        node
        for node in module.tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def test_auth_register_user_custom_constructor_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    user_class = _class(modules["app.models"], "User")

    custom_init = ast.parse(
        "def __init__(self, **kwargs):\n"
        "    self.email = kwargs.get('email')\n"
    ).body[0]
    user_class.body.append(custom_init)
    ast.fix_missing_locations(user_class)

    _assert_not_no_canonical(modules, monkeypatch)


def test_auth_register_userresponse_must_remain_direct_basemodel(monkeypatch):
    modules = census_module._parse_app()
    schema_module = modules["app.schemas.user_schema"]
    response = _class(schema_module, "UserResponse")

    response.bases = [ast.Name(id="UserCreate", ctx=ast.Load())]
    ast.fix_missing_locations(response)

    _assert_not_no_canonical(modules, monkeypatch)


def test_auth_register_userresponse_custom_validator_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    response = _class(
        modules["app.schemas.user_schema"],
        "UserResponse",
    )

    validator = ast.parse(
        "@field_validator('email')\n"
        "@classmethod\n"
        "def validar_email(cls, value):\n"
        "    return value\n"
    ).body[0]
    response.body.append(validator)
    ast.fix_missing_locations(response)

    _assert_not_no_canonical(modules, monkeypatch)
