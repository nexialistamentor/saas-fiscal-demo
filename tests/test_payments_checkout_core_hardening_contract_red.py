"""Contrato RED de endurecimento do núcleo real de checkout."""

from decimal import Decimal

from app.services import checkout_core as checkout


class _Catalogo:
    def obter_plano(self, plano_id):
        return {"id": plano_id, "preco": Decimal("49.90"), "moeda": "BRL"}


class _Repositorio:
    def __init__(self):
        self.ordens = []
        self.pagamentos = []


class _Gateway:
    def __init__(self, provider_order_ids=None, erro=None):
        self.provider_order_ids = iter(provider_order_ids or [])
        self.erro = erro

    def criar_cobranca(self, **_dados):
        if self.erro is not None:
            raise self.erro
        return {"provider_order_id": next(self.provider_order_ids)}


class _Ativador:
    def __init__(self):
        self.ativacoes = []

    def ativar(self, **dados):
        self.ativacoes.append(dados)


class _VerificadorAutenticado:
    def verificar(self, _evento, _assinatura):
        return True


def _core(provider_order_ids=None, erro_gateway=None):
    repositorio = _Repositorio()
    ativador = _Ativador()
    core = checkout.CheckoutCore(
        catalogo=_Catalogo(),
        repositorio=repositorio,
        gateway=_Gateway(provider_order_ids, erro_gateway),
        ativador=ativador,
        verificador_webhook=_VerificadorAutenticado(),
    )
    return core, repositorio, ativador


def _checkout(core, sufixo):
    return core.iniciar_checkout(
        user_id=100 + sufixo,
        empresa_id=200 + sufixo,
        plano_id=7,
        idempotency_key=f"checkout-{sufixo}",
    )


def _exige_falha_fechada(operacao, descricao, violacoes):
    try:
        operacao()
    except checkout.CheckoutError:
        return
    violacoes.append(descricao)


def test_checkout_core_hardening_contract_red():
    violacoes = []

    core, repositorio, ativador = _core(
        erro_gateway=RuntimeError("gateway indisponível")
    )
    try:
        _checkout(core, 1)
    except RuntimeError:
        pass
    else:
        violacoes.append("a exceção do gateway não foi propagada")
    if repositorio.ordens or repositorio.pagamentos or ativador.ativacoes:
        violacoes.append("a falha do gateway deixou efeitos persistidos")

    core, repositorio, ativador = _core(["provider-repetido", "provider-repetido"])
    primeira_ordem = _checkout(core, 2)
    _exige_falha_fechada(
        lambda: _checkout(core, 3),
        "provider_order_id duplicado foi aceite",
        violacoes,
    )
    if repositorio.ordens != [primeira_ordem]:
        violacoes.append("a segunda ordem com provider_order_id duplicado foi persistida")
    if repositorio.pagamentos or ativador.ativacoes:
        violacoes.append("a colisão de provider_order_id gerou pagamento ou ativação")

    retorno = core.processar_retorno("provider-repetido", "paid")
    if retorno is not None:
        violacoes.append("processar_retorno expôs dados da ordem")

    core, repositorio, ativador = _core([])
    evento_desconhecido = {
        "event_id": "evento-desconhecido",
        "provider_order_id": "provider-inexistente",
        "status": "paid",
    }
    _exige_falha_fechada(
        lambda: core.processar_webhook(evento_desconhecido, "assinatura-válida"),
        "webhook autenticado para provider_order_id desconhecido não falhou fechado",
        violacoes,
    )
    if repositorio.pagamentos or ativador.ativacoes:
        violacoes.append("webhook desconhecido gerou pagamento ou ativação")

    for campo, valor_alterado in (
        ("provider_order_id", "provider-diferente"),
        ("status", "refunded"),
    ):
        core, repositorio, ativador = _core(["provider-original"])
        ordem = _checkout(core, 4)
        evento = {
            "event_id": "evento-reutilizado",
            "provider_order_id": "provider-original",
            "status": "paid",
        }
        core.processar_webhook(evento, "assinatura-válida")
        pagamentos_antes = list(repositorio.pagamentos)
        ativacoes_antes = list(ativador.ativacoes)
        evento_alterado = {**evento, campo: valor_alterado}
        _exige_falha_fechada(
            lambda evento_alterado=evento_alterado: core.processar_webhook(
                evento_alterado, "assinatura-válida"
            ),
            f"event_id reutilizado com {campo} diferente foi aceite",
            violacoes,
        )
        if repositorio.ordens != [ordem]:
            violacoes.append(f"reutilização com {campo} alterou as ordens")
        if repositorio.pagamentos != pagamentos_antes:
            violacoes.append(f"reutilização com {campo} alterou os pagamentos")
        if ativador.ativacoes != ativacoes_antes:
            violacoes.append(f"reutilização com {campo} gerou nova ativação")

    assert not violacoes, "\n" + "\n".join(f"- {item}" for item in violacoes)
