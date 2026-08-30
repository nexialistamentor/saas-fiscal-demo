"""Núcleo de checkout seguro e agnóstico ao provedor."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


class CheckoutError(Exception):
    """Erro público base do núcleo de checkout."""


class DadosCheckoutInvalidosError(CheckoutError):
    """Os dados necessários para o checkout não são seguros."""


class ChaveIdempotenciaReutilizadaError(CheckoutError):
    """A chave de idempotência já pertence a outro checkout."""


class OrdemNaoEncontradaError(CheckoutError):
    """A ordem solicitada não existe."""


class AcessoOrdemNegadoError(CheckoutError):
    """O utilizador não pode aceder à ordem solicitada."""


class WebhookNaoAutenticadoError(CheckoutError):
    """O evento não pôde ser autenticado."""


@dataclass
class OrdemCheckout:
    id: int
    user_id: int
    empresa_id: int
    plano_id: int
    valor: Decimal
    moeda: str
    provider_order_id: str
    status: str = "pending"
    idempotency_key: str = ""


@dataclass
class PagamentoCheckout:
    ordem_id: int
    event_id: str
    provider_order_id: str
    valor: Decimal
    moeda: str


class CheckoutCore:
    """Coordena checkout sem confiar em dados financeiros do cliente."""

    def __init__(
        self,
        catalogo: Any,
        repositorio: Any,
        gateway: Any,
        ativador: Any,
        verificador_webhook: Any,
    ) -> None:
        self.catalogo = catalogo
        self.repositorio = repositorio
        self.gateway = gateway
        self.ativador = ativador
        self.verificador_webhook = verificador_webhook
        self._eventos_processados: dict[str, tuple[str, str]] = {}

    def iniciar_checkout(
        self,
        user_id,
        empresa_id,
        plano_id,
        idempotency_key,
    ):
        self._validar_id_positivo(user_id)
        self._validar_id_positivo(empresa_id)
        self._validar_id_positivo(plano_id)
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise DadosCheckoutInvalidosError("Chave de idempotência inválida")

        existente = self._ordem_por_idempotencia(idempotency_key)
        if existente is not None:
            mesmos_dados = (
                existente.user_id == user_id
                and existente.empresa_id == empresa_id
                and existente.plano_id == plano_id
            )
            if not mesmos_dados:
                raise ChaveIdempotenciaReutilizadaError(
                    "Chave de idempotência já utilizada"
                )
            return existente

        plano = self.catalogo.obter_plano(plano_id)
        valor, moeda = self._dados_canonicos_seguros(plano, plano_id)
        ordem = OrdemCheckout(
            id=self._proximo_id_ordem(),
            user_id=user_id,
            empresa_id=empresa_id,
            plano_id=plano_id,
            valor=valor,
            moeda=moeda,
            provider_order_id="",
            idempotency_key=idempotency_key,
        )
        self.repositorio.ordens.append(ordem)
        try:
            resposta = self.gateway.criar_cobranca(
                ordem_id=ordem.id,
                user_id=user_id,
                empresa_id=empresa_id,
                plano_id=plano_id,
                valor=valor,
                moeda=moeda,
                idempotency_key=idempotency_key,
            )
            provider_order_id = (
                resposta.get("provider_order_id")
                if isinstance(resposta, dict)
                else None
            )
            if not isinstance(provider_order_id, str) or not provider_order_id.strip():
                raise DadosCheckoutInvalidosError("Resposta inválida do gateway")

            if self._ordem_por_provider_id(provider_order_id) is not None:
                raise DadosCheckoutInvalidosError(
                    "Identificador do provedor já utilizado"
                )
            ordem.provider_order_id = provider_order_id
        except Exception:
            for indice, ordem_persistida in enumerate(self.repositorio.ordens):
                if ordem_persistida is ordem:
                    del self.repositorio.ordens[indice]
                    break
            raise
        return ordem

    def consultar_ordem(self, ordem_id, user_id, empresa_id):
        self._validar_id_positivo(ordem_id)
        self._validar_id_positivo(user_id)
        self._validar_id_positivo(empresa_id)
        ordem = self._ordem_por_id(ordem_id)
        self._garantir_acesso(ordem, user_id, empresa_id)
        return ordem

    def cancelar_ordem(self, ordem_id, user_id, empresa_id):
        self._validar_id_positivo(ordem_id)
        self._validar_id_positivo(user_id)
        self._validar_id_positivo(empresa_id)
        ordem = self._ordem_por_id(ordem_id)
        self._garantir_acesso(ordem, user_id, empresa_id)
        if ordem.status == "paid":
            raise DadosCheckoutInvalidosError("Ordem não pode ser cancelada")
        self.gateway.cancelar_cobranca(provider_order_id=ordem.provider_order_id)
        ordem.status = "cancelled"
        return ordem

    def processar_retorno(self, provider_order_id, status):
        """Trata o retorno do browser apenas como informação não confiável."""
        return None

    def processar_webhook(self, evento, assinatura):
        try:
            autenticado = self.verificador_webhook.verificar(evento, assinatura)
        except Exception as exc:
            raise WebhookNaoAutenticadoError("Webhook não autenticado") from exc
        if autenticado is not True:
            raise WebhookNaoAutenticadoError("Webhook não autenticado")

        if not isinstance(evento, dict):
            raise WebhookNaoAutenticadoError("Webhook não autenticado")
        event_id = evento.get("event_id")
        provider_order_id = evento.get("provider_order_id")
        status = evento.get("status")
        if (
            not isinstance(event_id, str)
            or not event_id.strip()
            or not isinstance(provider_order_id, str)
            or not provider_order_id.strip()
            or not isinstance(status, str)
            or not status.strip()
        ):
            raise WebhookNaoAutenticadoError("Webhook não autenticado")

        dados_evento = (provider_order_id, status)
        evento_processado = self._eventos_processados.get(event_id)
        if evento_processado is not None:
            if evento_processado != dados_evento:
                raise DadosCheckoutInvalidosError(
                    "Evento reutilizado com dados diferentes"
                )
            return self._ordem_por_provider_id(provider_order_id)

        ordem = self._ordem_por_provider_id(provider_order_id)
        if ordem is None:
            raise OrdemNaoEncontradaError("Ordem não encontrada")
        if status != "paid":
            self._eventos_processados[event_id] = dados_evento
            return ordem
        if ordem.status == "paid":
            self._eventos_processados[event_id] = dados_evento
            return ordem

        pagamento = PagamentoCheckout(
            ordem_id=ordem.id,
            event_id=event_id,
            provider_order_id=ordem.provider_order_id,
            valor=ordem.valor,
            moeda=ordem.moeda,
        )
        self.repositorio.pagamentos.append(pagamento)
        ordem.status = "paid"
        self.ativador.ativar(
            user_id=ordem.user_id,
            empresa_id=ordem.empresa_id,
            plano_id=ordem.plano_id,
            ordem_id=ordem.id,
        )
        self._eventos_processados[event_id] = dados_evento
        return ordem

    @staticmethod
    def _validar_id_positivo(valor):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise DadosCheckoutInvalidosError("Identificador inválido")

    @staticmethod
    def _dados_canonicos_seguros(plano, plano_id):
        if not isinstance(plano, dict) or plano.get("id") != plano_id:
            raise DadosCheckoutInvalidosError("Plano canónico inválido")
        valor = plano.get("preco")
        moeda = plano.get("moeda")
        if (
            not isinstance(valor, Decimal)
            or not valor.is_finite()
            or valor <= Decimal("0")
        ):
            raise DadosCheckoutInvalidosError("Valor canónico inválido")
        if (
            not isinstance(moeda, str)
            or len(moeda) != 3
            or not moeda.isascii()
            or not moeda.isalpha()
            or moeda != moeda.upper()
        ):
            raise DadosCheckoutInvalidosError("Moeda canónica inválida")
        return valor, moeda

    def _proximo_id_ordem(self):
        ids = [ordem.id for ordem in self.repositorio.ordens]
        return max(ids, default=0) + 1

    def _ordem_por_idempotencia(self, idempotency_key):
        return next(
            (
                ordem
                for ordem in self.repositorio.ordens
                if ordem.idempotency_key == idempotency_key
            ),
            None,
        )

    def _ordem_por_id(self, ordem_id):
        ordem = next(
            (ordem for ordem in self.repositorio.ordens if ordem.id == ordem_id),
            None,
        )
        if ordem is None:
            raise OrdemNaoEncontradaError("Ordem não encontrada")
        return ordem

    def _ordem_por_provider_id(self, provider_order_id):
        return next(
            (
                ordem
                for ordem in self.repositorio.ordens
                if ordem.provider_order_id == provider_order_id
            ),
            None,
        )

    @staticmethod
    def _garantir_acesso(ordem, user_id, empresa_id):
        if ordem.user_id != user_id or ordem.empresa_id != empresa_id:
            raise AcessoOrdemNegadoError("Acesso à ordem negado")
