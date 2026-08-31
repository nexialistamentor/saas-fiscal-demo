"""Consulta segura do catalogo duravel de ofertas de checkout."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import CheckoutOffer


_MENSAGEM_PUBLICA = "Nao foi possivel consultar a oferta"
_CODIGO = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+", re.ASCII)
_CAPABILITY = re.compile(
    r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+", re.ASCII
)
_VERTICAIS = frozenset({"tax", "document"})
_MODELOS = frozenset({"monthly", "one_time", "negotiated"})
_SUJEITOS = frozenset({"cpf", "company", "institution"})


@dataclass(frozen=True)
class CheckoutOfferSnapshot:
    id: int
    codigo: str
    nome_publico: str
    vertical: str
    commercial_model: str
    subject_type: str
    estado: str
    moeda: str | None
    preco: Decimal | None
    billing_period: str | None
    usage_unit: str | None
    usage_limit: int | None
    contract_version: int
    criado_em: datetime
    atualizado_em: datetime
    capabilities: tuple[str, ...]
    checkout_mode: str


class CheckoutOfferCatalogError(Exception):
    """Erro publico deliberadamente opaco e sem dados persistidos."""

    def __init__(self) -> None:
        super().__init__(_MENSAGEM_PUBLICA)


class CheckoutOfferCatalog:
    def __init__(self, session_factory) -> None:
        if not callable(session_factory):
            raise CheckoutOfferCatalogError()
        self._session_factory = session_factory

    def listar_ofertas_publicadas(self):
        return self._consultar()

    def obter_oferta_publicada(self, codigo):
        self._validar_codigo_consulta(codigo)
        ofertas = self._consultar(codigo)
        if len(ofertas) != 1:
            raise CheckoutOfferCatalogError()
        return ofertas[0]

    def resolver_oferta_para_checkout(self, codigo):
        oferta = self.obter_oferta_publicada(codigo)
        if oferta.checkout_mode != "automatic":
            raise CheckoutOfferCatalogError()
        return oferta

    def _consultar(self, codigo=None):
        sessao = None
        try:
            sessao = self._session_factory()
            if not callable(getattr(sessao, "execute", None)):
                raise CheckoutOfferCatalogError()
            consulta = (
                select(CheckoutOffer)
                .options(selectinload(CheckoutOffer.capabilities))
                .where(CheckoutOffer.estado == "published")
                .order_by(CheckoutOffer.codigo)
            )
            if codigo is not None:
                consulta = consulta.where(CheckoutOffer.codigo == codigo)
            entidades = sessao.execute(consulta).scalars().all()
            return tuple(self._snapshot(entidade) for entidade in entidades)
        except CheckoutOfferCatalogError:
            raise
        except Exception:
            raise CheckoutOfferCatalogError() from None
        finally:
            if sessao is not None:
                try:
                    sessao.close()
                except Exception:
                    pass

    @staticmethod
    def _validar_codigo_consulta(codigo):
        if not isinstance(codigo, str) or _CODIGO.fullmatch(codigo) is None:
            raise CheckoutOfferCatalogError()

    @classmethod
    def _snapshot(cls, oferta):
        cls._inteiro_positivo(oferta.id)
        cls._validar_codigo_consulta(oferta.codigo)
        cls._texto(oferta.nome_publico, 255)
        if oferta.vertical not in _VERTICAIS:
            raise CheckoutOfferCatalogError()
        if oferta.commercial_model not in _MODELOS:
            raise CheckoutOfferCatalogError()
        if oferta.subject_type not in _SUJEITOS or oferta.estado != "published":
            raise CheckoutOfferCatalogError()
        cls._inteiro_positivo(oferta.contract_version)
        if type(oferta.criado_em) is not datetime or type(oferta.atualizado_em) is not datetime:
            raise CheckoutOfferCatalogError()

        capacidades = tuple(sorted(capability.codigo for capability in oferta.capabilities))
        if not capacidades or len(capacidades) != len(set(capacidades)):
            raise CheckoutOfferCatalogError()
        if any(not isinstance(item, str) or _CAPABILITY.fullmatch(item) is None for item in capacidades):
            raise CheckoutOfferCatalogError()

        cls._configuracao_comercial(oferta)
        return CheckoutOfferSnapshot(
            id=oferta.id,
            codigo=oferta.codigo,
            nome_publico=oferta.nome_publico,
            vertical=oferta.vertical,
            commercial_model=oferta.commercial_model,
            subject_type=oferta.subject_type,
            estado=oferta.estado,
            moeda=oferta.moeda,
            preco=oferta.preco,
            billing_period=oferta.billing_period,
            usage_unit=oferta.usage_unit,
            usage_limit=oferta.usage_limit,
            contract_version=oferta.contract_version,
            criado_em=oferta.criado_em,
            atualizado_em=oferta.atualizado_em,
            capabilities=capacidades,
            checkout_mode=("proposal" if oferta.commercial_model == "negotiated" else "automatic"),
        )

    @classmethod
    def _configuracao_comercial(cls, oferta):
        modelo = oferta.commercial_model
        if modelo == "negotiated":
            if any(
                valor is not None
                for valor in (
                    oferta.moeda,
                    oferta.preco,
                    oferta.billing_period,
                    oferta.usage_unit,
                    oferta.usage_limit,
                )
            ):
                raise CheckoutOfferCatalogError()
            return
        if oferta.moeda != "BRL":
            raise CheckoutOfferCatalogError()
        cls._preco(oferta.preco)
        if modelo == "monthly":
            if oferta.billing_period != "month" or oferta.usage_unit is not None or oferta.usage_limit is not None:
                raise CheckoutOfferCatalogError()
            return
        if oferta.billing_period is not None:
            raise CheckoutOfferCatalogError()
        cls._texto(oferta.usage_unit, 50)
        cls._inteiro_positivo(oferta.usage_limit)

    @staticmethod
    def _preco(valor):
        if (
            not isinstance(valor, Decimal)
            or not valor.is_finite()
            or valor <= Decimal("0")
            or valor != valor.quantize(Decimal("0.01"))
        ):
            raise CheckoutOfferCatalogError()

    @staticmethod
    def _inteiro_positivo(valor):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise CheckoutOfferCatalogError()

    @staticmethod
    def _texto(valor, limite):
        if (
            not isinstance(valor, str)
            or not valor
            or len(valor) > limite
            or valor != valor.strip()
            or "\r" in valor
            or "\n" in valor
        ):
            raise CheckoutOfferCatalogError()


def checkout_offer_snapshot(oferta):
    """Valida uma oferta ja carregada e devolve uma projecao desanexada."""
    try:
        return CheckoutOfferCatalog._snapshot(oferta)
    except CheckoutOfferCatalogError:
        raise
    except Exception:
        raise CheckoutOfferCatalogError() from None


__all__ = [
    "CheckoutOfferCatalog",
    "CheckoutOfferCatalogError",
    "CheckoutOfferSnapshot",
    "checkout_offer_snapshot",
]
