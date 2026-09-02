"""Contrato RED offline da fronteira sincrona do webhook Mercado Pago."""
import ast
import asyncio
import inspect
import sys
from importlib import import_module
import pytest
from starlette.requests import Request
VALID_BODY = b'{"boundary":"threadpool-contract"}'
INVALID_BODY = b"invalid-threadpool-contract"
class _ProcessarDouble:
    def __init__(self, harness):
        self.harness = harness
        self.calls = []
        self.error = None
        self.result = object()
    def __call__(self, *args):
        inside = self.harness.inside_threadpool
        self.calls.append((args, inside))
        self.harness.events.append(("processar", inside))
        if self.error is not None:
            raise self.error
        return self.result
class _OrchestratorDouble:
    def __init__(self, harness):
        self.processar = _ProcessarDouble(harness)
class _NormalizerDouble:
    def __init__(self, harness, error_type):
        self.harness = harness
        self.error_type = error_type
        self.evento = object()
        self.assinatura = object()
        self.calls = []
    def __call__(self, **kwargs):
        inside = self.harness.inside_threadpool
        self.calls.append((kwargs, inside))
        self.harness.events.append(("normalizar", inside))
        if kwargs["body"] == INVALID_BODY:
            raise self.error_type()
        return self.evento, self.assinatura
class _Harness:
    def __init__(self, normalization_error):
        self.inside_threadpool = False
        self.events = []
        self.boundary_calls = []
        self.normalizer = _NormalizerDouble(self, normalization_error)
        self.orchestrator = _OrchestratorDouble(self)
    async def run_in_threadpool(self, function, *args):
        self.boundary_calls.append((function, args))
        self.events.append(("threadpool_enter", None))
        self.inside_threadpool = True
        try:
            return function(*args)
        finally:
            self.inside_threadpool = False
            self.events.append(("threadpool_exit", None))
def _request(body, harness):
    delivered = False
    async def receive():
        nonlocal delivered
        assert not delivered
        delivered = True
        harness.events.append(("stream", harness.inside_threadpool))
        return {"type": "http.request", "body": body, "more_body": False}
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/webhooks/mercado-pago",
            "raw_path": b"/webhooks/mercado-pago",
            "query_string": b"",
            "root_path": "",
            "headers": (
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ),
            "server": ("thread-boundary.test", 443),
        },
        receive=receive,
    )
async def _exercise(route, harness, error_types):
    snapshots = {}
    async def invoke(label, body=VALID_BODY):
        harness.events = []
        response = await route.endpoint(_request(body, harness))
        snapshots[label] = tuple(harness.events)
        return response.status_code
    statuses = {"valid": await invoke("valid")}
    scheduled_before_invalid = len(harness.boundary_calls)
    statuses["invalid"] = await invoke("invalid", INVALID_BODY)
    invalid_scheduled = len(harness.boundary_calls) - scheduled_before_invalid
    for label, error in error_types.items():
        harness.orchestrator.processar.error = error
        statuses[label] = await invoke(label)
    harness.orchestrator.processar.error = None
    return statuses, invalid_scheduled, snapshots
def test_payments_mercado_pago_webhook_router_thread_boundary_contract_red():
    own_tree = ast.parse(inspect.getsource(sys.modules[__name__]))
    public_tests = [
        node.name
        for node in own_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    assert public_tests == [
        "test_payments_mercado_pago_webhook_router_thread_boundary_contract_red"
    ]
    router_module = import_module("app.routers.mercado_pago_webhook_router")
    http_module = import_module("app.services.mercado_pago_webhook_http")
    orchestration_module = import_module(
        "app.services.mercado_pago_webhook_orchestration"
    )
    concurrency_module = import_module("starlette.concurrency")
    factory = router_module.criar_mercado_pago_webhook_router
    signature = inspect.signature(factory)
    assert tuple(signature.parameters) == ("orchestrator", "max_body_bytes")
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    harness = _Harness(
        http_module.MercadoPagoWebhookHttpNormalizationError
    )
    real_response = router_module.Response
    def response_spy(*args, **kwargs):
        harness.events.append(("response", kwargs.get("status_code")))
        return real_response(*args, **kwargs)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            router_module,
            "normalizar_mercado_pago_webhook_http",
            harness.normalizer,
        )
        patch.setattr(concurrency_module, "run_in_threadpool",
                      harness.run_in_threadpool)
        patch.setattr(
            router_module,
            "run_in_threadpool",
            harness.run_in_threadpool,
            raising=False,
        )
        patch.setattr(router_module, "Response", response_spy)
        router = factory(
            orchestrator=harness.orchestrator,
            max_body_bytes=max(len(VALID_BODY), len(INVALID_BODY)),
        )
        assert len(router.routes) == 1
        route = router.routes[0]
        assert route.path == "/webhooks/mercado-pago"
        assert route.methods == {"POST"}
        assert inspect.iscoroutinefunction(route.endpoint)
        errors = {
            "authentication": orchestration_module.MercadoPagoWebhookAuthenticationError(),
            "orchestration": orchestration_module.MercadoPagoWebhookOrchestrationError(),
            "unexpected": RuntimeError("opaque-thread-boundary-error"),
        }
        statuses, invalid_scheduled, snapshots = asyncio.run(
            _exercise(route, harness, errors)
        )
    assert statuses == {
        "valid": 200,
        "invalid": 400,
        "authentication": 401,
        "orchestration": 500,
        "unexpected": 500,
    }
    assert invalid_scheduled == 0
    assert all(not inside for _call, inside in harness.normalizer.calls)
    assert all(
        not inside
        for events in snapshots.values()
        for name, inside in events
        if name == "stream"
    )
    assert all(events[-1][0] == "response" for events in snapshots.values())
    source = inspect.getsource(router_module)
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    imports = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    imported_roots = {
        alias.name.split(".")[0]
        for node in imports
        for alias in node.names
        if isinstance(node, ast.Import)
    }
    imported_roots.update(
        node.module.split(".")[0]
        for node in imports
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported_roots.isdisjoint(
        {"aiohttp", "concurrent", "httpx", "mercadopago", "os", "requests",
         "socket", "sqlalchemy", "urllib"}
    )
    forbidden_calls = {
        "create_task", "ensure_future", "get_event_loop", "new_event_loop",
        "run", "run_in_executor", "set_event_loop", "submit", "to_thread",
    }
    assert not any(
        (isinstance(call.func, ast.Name) and call.func.id in forbidden_calls)
        or (isinstance(call.func, ast.Attribute) and call.func.attr in forbidden_calls)
        for call in calls
    )
    lowered_source = source.lower()
    assert not any(
        fragment in lowered_source
        for fragment in (
            "access_token", "client_secret", "credentials", "create_engine",
            "environ", "getenv", "sessionmaker", "threadpoolexecutor",
        )
    )
    canonical_imports = [
        node
        for node in imports
        if isinstance(node, ast.ImportFrom)
        and node.module == "starlette.concurrency"
        and [(alias.name, alias.asname) for alias in node.names]
        == [("run_in_threadpool", None)]
    ]
    threadpool_calls = [
        call
        for call in calls
        if isinstance(call.func, ast.Name)
        and call.func.id == "run_in_threadpool"
    ]
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    static_boundary_ok = (
        len(canonical_imports) == 1
        and len(threadpool_calls) == 1
        and isinstance(parents.get(threadpool_calls[0]), ast.Await)
        and len(threadpool_calls[0].args) == 3
        and threadpool_calls[0].keywords == []
        and (
            isinstance(threadpool_calls[0].args[0], ast.Name)
            and threadpool_calls[0].args[0].id == "processar"
        )
        and not any(
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "processar"
            for call in calls
        )
    ) if threadpool_calls else False
    expected_args = (harness.normalizer.evento, harness.normalizer.assinatura)
    runtime_boundary_ok = (
        len(harness.boundary_calls) == 4
        and all(
            function is harness.orchestrator.processar
            and len(args) == 2
            and args[0] is expected_args[0]
            and args[1] is expected_args[1]
            for function, args in harness.boundary_calls
        )
        and all(inside for _args, inside in harness.orchestrator.processar.calls)
        and snapshots["valid"].index(("threadpool_exit", None))
        < snapshots["valid"].index(("response", 200))
    ) if harness.boundary_calls else False
    assert static_boundary_ok and runtime_boundary_ok, (
        "CAUSA RED exclusiva: orchestrator.processar ainda nao atravessa, de forma "
        "aguardada, starlette.concurrency.run_in_threadpool"
    )
