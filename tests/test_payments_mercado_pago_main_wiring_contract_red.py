"""Contrato RED test-only do wiring Mercado Pago em ``app.main``."""
import ast
import asyncio
import copy
import hashlib
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import pytest
_MAIN_PATH = Path(__file__).resolve().parents[1] / "app" / "main.py"
_LEGACY_LIFESPAN_HASH = (
    "b9710276af1f6247c99a43b53ac64ead038ed0151146fdf6613b765b97ce9dfe"
)
_LEGACY_SURFACE_HASH = (
    "ea15acae58deda7335d7c97d7b1f992d6e6e82a24e07c8cfe246d2d7f08a90e4"
)
_REQUIRED_IMPORTS = (
    ("app.database", "SessionLocal"),
    ("app.security", "get_usuario_atual"),
    (
        "app.services.mercado_pago_runtime_lifecycle",
        "ativar_mercado_pago",
    ),
    (
        "app.routers.checkout_offer_one_time_router",
        "criar_checkout_offer_one_time_router",
    ),
    (
        "app.routers.mercado_pago_webhook_router",
        "criar_mercado_pago_webhook_router",
    ),
)
class _BoundaryFailure(Exception):
    pass
class _ActivationDouble:
    def __init__(self, composition):
        self.composition = composition
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None
def _app_call(node, method):
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and _name(node.value.func) == f"app.{method}"
    )
def _middleware_definition(node):
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
        isinstance(item, ast.Call) and _name(item.func) == "app.middleware"
        for item in node.decorator_list
    )
def _semantic_hash(nodes):
    dumped = ast.dump(
        ast.Module(body=list(nodes), type_ignores=[]),
        include_attributes=False,
    )
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
def _owner(node, parents):
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return "<module>"
def _assert_close_is_finally(final_try, activation_name):
    assert final_try.handlers == final_try.orelse == []
    assert len(final_try.finalbody) == 1
    guard = final_try.finalbody[0]
    assert isinstance(guard, ast.If) and guard.orelse == []
    assert isinstance(guard.test, ast.Compare)
    assert (
        isinstance(guard.test.left, ast.Name)
        and guard.test.left.id == activation_name
        and len(guard.test.ops) == 1
        and isinstance(guard.test.ops[0], ast.IsNot)
        and len(guard.test.comparators) == 1
        and isinstance(guard.test.comparators[0], ast.Constant)
        and guard.test.comparators[0].value is None
    )
    assert len(guard.body) == 1 and isinstance(guard.body[0], ast.Expr)
    close_call = guard.body[0].value
    assert isinstance(close_call, ast.Call)
    assert _name(close_call.func) == f"{activation_name}.close"
    assert close_call.args == close_call.keywords == []
def _compile_isolated(node, namespace):
    isolated = copy.deepcopy(node)
    isolated.decorator_list = []
    isolated.returns = None
    arguments = (
        isolated.args.posonlyargs
        + isolated.args.args
        + isolated.args.kwonlyargs
    )
    for argument in arguments:
        argument.annotation = None
    module = ast.fix_missing_locations(
        ast.Module(body=[isolated], type_ignores=[])
    )
    scope = {"__builtins__": {"dict": dict}, **namespace}
    exec(compile(module, str(_MAIN_PATH), "exec"), scope)
    return scope["lifespan"]
def _scenario(lifespan, mode, fail_at=None):
    environment = {"BOUNDARY_SENTINEL": "snapshot-value"}
    engine = object()
    database_session = SimpleNamespace()
    checkout_application = object()
    webhook_orchestrator = object()
    checkout_router = object()
    webhook_router = object()
    http_client_factory = object()
    current_user_dependency = object()
    configuration_failure = _BoundaryFailure("invalid configuration")
    wiring_failure = _BoundaryFailure("wiring failure")
    factory_calls = {"checkout": [], "webhook": []}
    included = []
    composition = SimpleNamespace(
        checkout_application=checkout_application,
        webhook_orchestrator=webhook_orchestrator,
        max_body_bytes=32768,
    )
    activation = _ActivationDouble(composition)
    def create_all(*args, **kwargs):
        assert args == () and kwargs == {"bind": engine}
    def run_migrations(*args, **kwargs):
        assert args == () and kwargs == {}
    def close_database(*args, **kwargs):
        assert args == () and kwargs == {}
    database_session.close = close_database
    def session_local(*args, **kwargs):
        assert args == () and kwargs == {}
        return database_session
    def ensure_plans(*args, **kwargs):
        assert args == (database_session,) and kwargs == {}
    def purge(*args, **kwargs):
        assert args == () and kwargs == {}
    async def to_thread(*args, **kwargs):
        assert args == (purge,) and kwargs == {}
        return purge()
    def activate(*args, **kwargs):
        assert args == ()
        assert tuple(kwargs) == (
            "values",
            "session_factory",
            "http_client_factory",
        )
        assert type(kwargs["values"]) is dict
        assert kwargs["values"] == environment
        assert kwargs["values"] is not environment
        assert kwargs["session_factory"] is session_local
        assert kwargs["http_client_factory"] is http_client_factory
        if mode == "invalid":
            raise configuration_failure
        return None if mode == "disabled" else activation
    def checkout_factory(*args, **kwargs):
        assert args == ()
        assert kwargs == {
            "application_service": checkout_application,
            "current_user_dependency": current_user_dependency,
        }
        factory_calls["checkout"].append(dict(kwargs))
        if fail_at == "checkout_factory":
            raise wiring_failure
        return checkout_router
    def webhook_factory(*args, **kwargs):
        assert args == ()
        assert kwargs == {
            "orchestrator": webhook_orchestrator,
            "max_body_bytes": 32768,
        }
        factory_calls["webhook"].append(dict(kwargs))
        if fail_at == "webhook_factory":
            raise wiring_failure
        return webhook_router
    def include_router(router, *args, **kwargs):
        assert args == () and kwargs == {}
        if (
            fail_at == "checkout_include" and router is checkout_router
        ) or (fail_at == "webhook_include" and router is webhook_router):
            raise wiring_failure
        included.append(router)
    namespace = {
        "models": SimpleNamespace(
            Base=SimpleNamespace(metadata=SimpleNamespace(create_all=create_all))
        ),
        "engine": engine,
        "run_migrations": run_migrations,
        "SessionLocal": session_local,
        "ensure_planos": ensure_plans,
        "asyncio": SimpleNamespace(to_thread=to_thread),
        "_startup_purge_request_logs_sync": purge,
        "os": SimpleNamespace(environ=environment),
        "httpx": SimpleNamespace(Client=http_client_factory),
        "ativar_mercado_pago": activate,
        "criar_checkout_offer_one_time_router": checkout_factory,
        "criar_mercado_pago_webhook_router": webhook_factory,
        "get_usuario_atual": current_user_dependency,
    }
    return SimpleNamespace(
        function=_compile_isolated(lifespan, namespace),
        app=SimpleNamespace(include_router=include_router),
        activation=activation,
        configuration_failure=configuration_failure,
        wiring_failure=wiring_failure,
        factory_calls=factory_calls,
        included=included,
        checkout_router=checkout_router,
        webhook_router=webhook_router,
    )
async def _drive(scenario):
    generator = scenario.function(scenario.app)
    yielded = await generator.__anext__()
    close_calls_at_yield = scenario.activation.close_calls
    await generator.aclose()
    return yielded, close_calls_at_yield
async def _start(scenario):
    return await scenario.function(scenario.app).__anext__()
def test_payments_mercado_pago_main_wiring_contract_red():
    source = _MAIN_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_MAIN_PATH))
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    lifespans = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan"
    ]
    assert len(lifespans) == 1
    lifespan = lifespans[0]
    surface = [
        node
        for node in tree.body
        if _app_call(node, "include_router")
        or _app_call(node, "add_middleware")
        or _middleware_definition(node)
        or isinstance(node, ast.ClassDef)
        and node.name == "TermosMiddleware"
        or isinstance(node, ast.FunctionDef)
        and node.name == "create_tables"
    ]
    assert _semantic_hash(surface) == _LEGACY_SURFACE_HASH
    activation_calls = [
        node
        for node in ast.walk(lifespan)
        if isinstance(node, ast.Call) and _name(node.func) == "ativar_mercado_pago"
    ]
    prefix_end = next(
        (
            index
            for index, statement in enumerate(lifespan.body)
            if activation_calls and activation_calls[0] in ast.walk(statement)
        ),
        len(lifespan.body) - 1,
    )
    assert _semantic_hash(lifespan.body[:prefix_end]) == _LEGACY_LIFESPAN_HASH
    expected_create_all = ast.dump(
        ast.parse("models.Base.metadata.create_all(bind=engine)").body[0].value,
        include_attributes=False,
    )
    create_all_calls = sorted(
        (_owner(node, parents), ast.dump(node, include_attributes=False))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _name(node.func) == "models.Base.metadata.create_all"
    )
    assert create_all_calls == [
        ("create_tables", expected_create_all),
        ("lifespan", expected_create_all),
    ]
    private_constants = [
        node.value.lower()
        for node in ast.walk(lifespan)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert not any(
        marker in value
        for value in private_constants
        for marker in ("access_token", "webhook_secret", "credential")
    )
    assert len(activation_calls) == 1, (
        "wiring Mercado Pago ausente: lifespan deve chamar "
        "ativar_mercado_pago exatamente uma vez"
    )
    imports = [
        (node.module, alias.name, alias.asname)
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.level == 0
        for alias in node.names
    ]
    assert all(imports.count((*item, None)) == 1 for item in _REQUIRED_IMPORTS)
    httpx_imports = [
        alias
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "httpx"
    ]
    assert len(httpx_imports) == 1 and httpx_imports[0].asname is None
    activation = activation_calls[0]
    assert prefix_end == 5
    statement = lifespan.body[prefix_end]
    assert isinstance(statement, ast.Assign) and statement.value is activation
    assert len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name)
    activation_name = statement.targets[0].id
    assert activation.args == []
    assert [item.arg for item in activation.keywords] == [
        "values",
        "session_factory",
        "http_client_factory",
    ]
    values = {item.arg: item.value for item in activation.keywords}
    snapshot_dump = ast.dump(
        ast.parse("dict(os.environ)").body[0].value,
        include_attributes=False,
    )
    assert ast.dump(values["values"], include_attributes=False) == snapshot_dump
    assert _name(values["session_factory"]) == "SessionLocal"
    assert _name(values["http_client_factory"]) == "httpx.Client"
    snapshots = [
        node
        for node in ast.walk(lifespan)
        if isinstance(node, ast.Call)
        and ast.dump(node, include_attributes=False) == snapshot_dump
    ]
    environment_references = [
        node
        for node in ast.walk(lifespan)
        if isinstance(node, ast.Attribute) and _name(node) == "os.environ"
    ]
    assert len(snapshots) == len(environment_references) == 1
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom, ast.ExceptHandler))
        for node in ast.walk(lifespan)
    )
    forbidden = {"logger", "logging", "print", "getenv", "token", "secret"}
    assert not any(
        forbidden.intersection((_name(node) or "").lower().split("."))
        for node in ast.walk(lifespan)
        if isinstance(node, (ast.Name, ast.Attribute))
    )
    assert not any(
        isinstance(node, (ast.Attribute, ast.Subscript))
        and isinstance(node.ctx, ast.Store)
        for node in ast.walk(lifespan)
    )
    assert len(lifespan.body) == prefix_end + 2
    final_try = lifespan.body[-1]
    assert isinstance(final_try, ast.Try)
    _assert_close_is_finally(final_try, activation_name)
    yields = [node for node in ast.walk(lifespan) if isinstance(node, ast.Yield)]
    assert len(yields) == 1 and yields[0].value is None
    inventory = Counter(
        _name(node.func)
        for node in ast.walk(lifespan)
        if isinstance(node, ast.Call)
    )
    assert inventory == Counter(
        {
            "models.Base.metadata.create_all": 1,
            "run_migrations": 1,
            "SessionLocal": 1,
            "ensure_planos": 1,
            "db.close": 1,
            "asyncio.to_thread": 1,
            "dict": 1,
            "ativar_mercado_pago": 1,
            "criar_checkout_offer_one_time_router": 1,
            "criar_mercado_pago_webhook_router": 1,
            "app.include_router": 2,
            f"{activation_name}.close": 1,
        }
    )
    disabled = _scenario(lifespan, "disabled")
    yielded, close_at_yield = asyncio.run(_drive(disabled))
    assert yielded is None and close_at_yield == 0
    assert disabled.activation.close_calls == 0
    assert disabled.factory_calls == {"checkout": [], "webhook": []}
    assert disabled.included == []
    enabled = _scenario(lifespan, "enabled")
    yielded, close_at_yield = asyncio.run(_drive(enabled))
    assert yielded is None and close_at_yield == 0
    assert enabled.activation.close_calls == 1
    assert len(enabled.factory_calls["checkout"]) == 1
    assert len(enabled.factory_calls["webhook"]) == 1
    assert len(enabled.included) == 2
    assert enabled.included.count(enabled.checkout_router) == 1
    assert enabled.included.count(enabled.webhook_router) == 1
    invalid = _scenario(lifespan, "invalid")
    with pytest.raises(_BoundaryFailure) as captured:
        asyncio.run(_start(invalid))
    assert captured.value is invalid.configuration_failure
    assert invalid.included == [] and invalid.activation.close_calls == 0
    for stage in (
        "checkout_factory",
        "checkout_include",
        "webhook_factory",
        "webhook_include",
    ):
        failing = _scenario(lifespan, "enabled", fail_at=stage)
        with pytest.raises(_BoundaryFailure) as captured:
            asyncio.run(_start(failing))
        assert captured.value is failing.wiring_failure
        assert failing.activation.close_calls == 1
