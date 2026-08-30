"""Composicao transacional do checkout duravel."""

from dataclasses import dataclass
from decimal import Decimal

from app.services.checkout_durable_ledger import CheckoutDurableLedger


_MENSAGEM_PUBLICA = "Nao foi possivel processar o checkout"


@dataclass(frozen=True, slots=True)
class OrdemCheckoutSnapshot:
    """Projecao imutavel da ordem, independente da sessao ORM."""

    id: int
    user_id: int
    empresa_id: int
    plano_id: int
    valor: Decimal
    moeda: str
    provider_order_id: str | None
    checkout_url: str | None


class CheckoutDurableCheckoutCompositionError(Exception):
    """Falha publica deliberadamente opaca do compositor."""

    def __init__(self) -> None:
        super().__init__(_MENSAGEM_PUBLICA)


class CheckoutDurableCheckoutComposer:
    """Coordena persistencia local e gateway em fases independentes."""

    def __init__(self, session_factory, catalogo, gateway) -> None:
        if (
            not callable(session_factory)
            or not callable(getattr(catalogo, "obter_plano", None))
            or not callable(getattr(gateway, "criar_cobranca", None))
        ):
            raise CheckoutDurableCheckoutCompositionError()
        self._session_factory = session_factory
        self._catalogo = catalogo
        self._gateway = gateway

    def iniciar_checkout(
        self,
        user_id,
        empresa_id,
        plano_id,
        preco,
        moeda,
        idempotency_key,
    ):
        del preco, moeda
        sessao_a = None
        try:
            plano = self._catalogo.obter_plano(plano_id)
            valor, moeda_canonica = self._dados_canonicos(plano, plano_id)

            sessao_a = self._abrir_sessao()
            ledger_a = CheckoutDurableLedger(sessao_a)
            ordem = ledger_a.criar_ou_obter_ordem(
                user_id=user_id,
                empresa_id=empresa_id,
                plano_id=plano_id,
                valor=valor,
                moeda=moeda_canonica,
                idempotency_key=idempotency_key,
            )
            snapshot_a = self._snapshot(ordem)
            sessao_a.commit()
            sessao_a.close()

            if (
                snapshot_a.provider_order_id is not None
                and snapshot_a.checkout_url
            ):
                return {
                    "ordem": snapshot_a,
                    "checkout_url": snapshot_a.checkout_url,
                }

            resposta = self._gateway.criar_cobranca(
                ordem_id=snapshot_a.id,
                user_id=snapshot_a.user_id,
                empresa_id=snapshot_a.empresa_id,
                plano_id=snapshot_a.plano_id,
                valor=snapshot_a.valor,
                moeda=snapshot_a.moeda,
                idempotency_key=idempotency_key,
            )
            provider_order_id, checkout_url = self._resposta_gateway(resposta)

            sessao_b = self._abrir_sessao()
            try:
                ordem_b = CheckoutDurableLedger(sessao_b).registrar_preferencia(
                    ordem_id=snapshot_a.id,
                    user_id=user_id,
                    empresa_id=empresa_id,
                    provider_order_id=provider_order_id,
                    checkout_url=checkout_url,
                )
                snapshot_b = self._snapshot(ordem_b)
                sessao_b.commit()
            except Exception:
                sessao_b.rollback()
                raise
            finally:
                sessao_b.close()
            return {
                "ordem": snapshot_b,
                "checkout_url": snapshot_b.checkout_url,
            }
        except Exception:
            if sessao_a is not None:
                try:
                    sessao_a.rollback()
                except Exception:
                    pass
                try:
                    sessao_a.close()
                except Exception:
                    pass
            raise CheckoutDurableCheckoutCompositionError() from None

    def _abrir_sessao(self):
        sessao = self._session_factory()
        if not callable(getattr(sessao, "commit", None)):
            try:
                sessao.close()
            except Exception:
                pass
            raise CheckoutDurableCheckoutCompositionError()
        return sessao

    @staticmethod
    def _snapshot(ordem):
        return OrdemCheckoutSnapshot(
            id=ordem.id,
            user_id=ordem.user_id,
            empresa_id=ordem.empresa_id,
            plano_id=ordem.plano_id,
            valor=ordem.valor,
            moeda=ordem.moeda,
            provider_order_id=ordem.provider_order_id,
            checkout_url=ordem.checkout_url,
        )

    @staticmethod
    def _dados_canonicos(plano, plano_id):
        if not isinstance(plano, dict) or plano.get("id") != plano_id:
            raise CheckoutDurableCheckoutCompositionError()
        valor = plano.get("preco")
        moeda = plano.get("moeda")
        if (
            not isinstance(valor, Decimal)
            or not valor.is_finite()
            or valor <= Decimal("0")
            or moeda != "BRL"
        ):
            raise CheckoutDurableCheckoutCompositionError()
        return valor, moeda

    @staticmethod
    def _resposta_gateway(resposta):
        if not isinstance(resposta, dict):
            raise CheckoutDurableCheckoutCompositionError()
        provider_order_id = resposta.get("provider_order_id")
        checkout_url = resposta.get("checkout_url")
        if (
            not isinstance(provider_order_id, str)
            or not provider_order_id
            or provider_order_id != provider_order_id.strip()
            or "\r" in provider_order_id
            or "\n" in provider_order_id
            or not isinstance(checkout_url, str)
            or not checkout_url.startswith("https://")
        ):
            raise CheckoutDurableCheckoutCompositionError()
        return provider_order_id, checkout_url


__all__ = [
    "CheckoutDurableCheckoutComposer",
    "CheckoutDurableCheckoutCompositionError",
    "OrdemCheckoutSnapshot",
]
