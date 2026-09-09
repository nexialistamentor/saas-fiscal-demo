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


def _add_custom_init(module, class_name):
    model_class = _class(module, class_name)
    custom_init = ast.parse(
        "def __init__(self, **kwargs):\n"
        "    self.id = kwargs.get('id')\n"
    ).body[0]
    model_class.body.append(custom_init)
    ast.fix_missing_locations(model_class)


def _add_insert_validator(module, model_name):
    validator_maps = [
        statement.value
        for statement in module.tree.body
        if (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "_ADR020_INSERT_VALIDATORS"
                for target in statement.targets
            )
            and isinstance(statement.value, ast.Dict)
        )
    ]
    assert len(validator_maps) == 1
    validator_maps[0].keys.append(ast.Name(id=model_name, ctx=ast.Load()))
    validator_maps[0].values.append(ast.Name(id="validator", ctx=ast.Load()))
    ast.fix_missing_locations(validator_maps[0])


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


def test_auth_register_plano_custom_constructor_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    _add_custom_init(modules["app.models"], "Plano")

    _assert_not_no_canonical(modules, monkeypatch)


def test_auth_register_empresa_custom_constructor_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    _add_custom_init(modules["app.models"], "Empresa")

    _assert_not_no_canonical(modules, monkeypatch)


def test_auth_register_plano_insert_validator_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    _add_insert_validator(modules["app.models"], "Plano")

    _assert_not_no_canonical(modules, monkeypatch)


def test_auth_register_empresa_insert_validator_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    _add_insert_validator(modules["app.models"], "Empresa")

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
