"""Router HTTP minimo para webhooks do Mercado Pago."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import QueryParams
from starlette.requests import Request
from starlette.responses import Response

from app.services.mercado_pago_webhook_http import (
    MercadoPagoWebhookHttpNormalizationError,
    normalizar_mercado_pago_webhook_http,
)
from app.services.mercado_pago_webhook_orchestration import (
    MercadoPagoWebhookAuthenticationError,
    MercadoPagoWebhookOrchestrationError,
)


class MercadoPagoWebhookRouterConfigurationError(Exception):
    """Erro opaco de configuracao do router."""

    def __init__(self, *_args, **_kwargs):
        super().__init__("Configuracao invalida")


def criar_mercado_pago_webhook_router(*, orchestrator, max_body_bytes):
    """Cria o router com dependencias explicitamente injetadas."""

    try:
        processar = orchestrator.processar
    except Exception:
        raise MercadoPagoWebhookRouterConfigurationError() from None

    if (
        not callable(processar)
        or type(max_body_bytes) is not int
        or not 1 <= max_body_bytes <= 65_536
    ):
        raise MercadoPagoWebhookRouterConfigurationError()

    router = APIRouter()

    @router.post("/webhooks/mercado-pago")
    async def receber_webhook(request: Request):
        try:
            header_pairs = tuple(
                (name.decode("latin-1"), value.decode("latin-1"))
                for name, value in request.scope["headers"]
            )
            content_types = tuple(
                value
                for name, value in header_pairs
                if name.lower() == "content-type"
            )
            content_lengths = tuple(
                value
                for name, value in header_pairs
                if name.lower() == "content-length"
            )

            if len(content_types) != 1 or content_types[0] != "application/json":
                return Response(status_code=400)

            if len(content_lengths) > 1:
                return Response(status_code=400)
            if content_lengths:
                declared_length = content_lengths[0]
                if (
                    not declared_length.isascii()
                    or not declared_length.isdecimal()
                    or int(declared_length) > max_body_bytes
                ):
                    return Response(status_code=400)

            query_pairs = tuple(
                QueryParams(request.scope["query_string"]).multi_items()
            )
            payload = bytearray()
            async for chunk in request.stream():
                if len(payload) + len(chunk) > max_body_bytes:
                    return Response(status_code=400)
                payload.extend(chunk)

            try:
                evento, assinatura = normalizar_mercado_pago_webhook_http(
                    method=request.scope["method"],
                    content_type=content_types[0],
                    headers=header_pairs,
                    query_params=query_pairs,
                    body=bytes(payload),
                )
            except MercadoPagoWebhookHttpNormalizationError:
                return Response(status_code=400)

            try:
                await run_in_threadpool(processar, evento, assinatura)
            except MercadoPagoWebhookAuthenticationError:
                return Response(status_code=401)
            except MercadoPagoWebhookOrchestrationError:
                return Response(status_code=500)
            except Exception:
                return Response(status_code=500)

            return Response(status_code=200)
        except Exception:
            return Response(status_code=500)

    return router
