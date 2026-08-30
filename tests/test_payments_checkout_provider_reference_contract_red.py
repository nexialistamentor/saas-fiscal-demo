"""Contrato RED da referência interna enviada ao gateway de pagamento."""

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
    def __init__(self, repositorio, erro=None):
        self.repositorio = repositorio
        self.erro = erro
        self.cobrancas = []
        self.ordens_presentes_na_chamada = []

    def criar_cobranca(self, **dados):
        self.cobrancas.append(dados)
        self.ordens_presentes_na_chamada.append(list(self.repositorio.ordens))
        if self.erro is not None:
            raise self.erro
        return {
            "provider_order_id": "provider-order-1",
            "checkout_url": "https://provider.invalid/checkout/1",
            "token": "provider-secret-token",
            "credencial": "provider-secret-credential",
            "payload": {"provider": "private"},
        }


class _Ativador:
    def __init__(self):
        self.ativacoes = []

    def ativar(self, **dados):
        self.ativacoes.append(dados)


class _VerificadorWebhook:
    def verificar(self, _evento, _assinatura):
        return True


def _core(erro_gateway=None):
    repositorio = _Repositorio()
    gateway = _Gateway(repositorio, erro_gateway)
    ativador = _Ativador()
    core = checkout.CheckoutCore(
        catalogo=_Catalogo(),
        repositorio=repositorio,
        gateway=gateway,
        ativador=ativador,
        verificador_webhook=_VerificadorWebhook(),
    )
    return core, repositorio, gateway, ativador


def test_checkout_provider_reference_contract_red():
    violacoes = []
    dados_checkout = {
        "user_id": 42,
        "empresa_id": 314,
        "plano_id": 7,
        "idempotency_key": "checkout-provider-reference-1",
    }
    dados_esperados_gateway = {
        **dados_checkout,
        "valor": Decimal("49.90"),
        "moeda": "BRL",
    }

    core, repositorio, gateway, ativador = _core()
    ordem = core.iniciar_checkout(**dados_checkout)
    cobranca = gateway.cobrancas[0]
    ordens_na_chamada = gateway.ordens_presentes_na_chamada[0]

    if len(ordens_na_chamada) != 1:
        violacoes.append("a ordem interna não existia antes da chamada ao gateway")
    else:
        ordem_provisoria = ordens_na_chamada[0]
        if not isinstance(ordem_provisoria.id, int) or ordem_provisoria.id <= 0:
            violacoes.append("a ordem provisória não tinha id inteiro positivo")
        if cobranca.get("ordem_id") != ordem_provisoria.id:
            violacoes.append("o gateway não recebeu o id da ordem provisória")

    ordem_id_gateway = cobranca.get("ordem_id")
    if not isinstance(ordem_id_gateway, int) or isinstance(ordem_id_gateway, bool):
        violacoes.append("ordem_id enviado ao gateway não é inteiro")
    elif ordem_id_gateway <= 0:
        violacoes.append("ordem_id enviado ao gateway não é positivo")
    if ordem_id_gateway != ordem.id:
        violacoes.append("ordem_id enviado ao gateway difere da ordem devolvida")

    for campo, valor_esperado in dados_esperados_gateway.items():
        if cobranca.get(campo) != valor_esperado:
            violacoes.append(f"{campo} incorreto na chamada ao gateway")

    for campo_sensivel in ("checkout_url", "token", "credencial", "payload"):
        if hasattr(ordem, campo_sensivel):
            violacoes.append(f"a ordem devolvida expôs {campo_sensivel}")

    erro_gateway = RuntimeError("gateway indisponível")
    core, repositorio, gateway, ativador = _core(erro_gateway)
    try:
        core.iniciar_checkout(
            user_id=43,
            empresa_id=315,
            plano_id=7,
            idempotency_key="checkout-provider-reference-failure",
        )
    except RuntimeError as exc:
        if exc is not erro_gateway:
            violacoes.append("a falha original do gateway não foi preservada")
    else:
        violacoes.append("a falha do gateway não foi propagada")

    ordens_na_falha = gateway.ordens_presentes_na_chamada[0]
    if len(ordens_na_falha) != 1:
        violacoes.append("a ordem provisória não existia durante a chamada que falhou")
    if repositorio.ordens:
        violacoes.append("a falha do gateway deixou ordem provisória")
    if repositorio.pagamentos:
        violacoes.append("a falha do gateway deixou pagamento")
    if ativador.ativacoes:
        violacoes.append("a falha do gateway deixou ativação")

    assert not violacoes, "\n" + "\n".join(f"- {item}" for item in violacoes)
