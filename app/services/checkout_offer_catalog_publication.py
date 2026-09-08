"""Autoridade transacional de publicacao do catalogo de checkout."""

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import CheckoutOffer, CheckoutOfferCapability
from app.services import checkout_offer_catalog as _catalog_contract


_MENSAGEM_PUBLICA = "Nao foi possivel publicar a oferta"


class CheckoutOfferCatalogPublicationError(Exception):
    """Erro de dominio deliberadamente opaco."""

    def __init__(self) -> None:
        super().__init__(_MENSAGEM_PUBLICA)


class CheckoutOfferCatalogPublicationAuthority:
    def __init__(self, session_factory) -> None:
        if not callable(session_factory):
            raise CheckoutOfferCatalogPublicationError()
        self._session_factory = session_factory

    def publicar_oferta(
        self,
        *,
        codigo,
        nome_publico,
        vertical,
        commercial_model,
        subject_type,
        moeda,
        preco,
        billing_period,
        usage_unit,
        usage_limit,
        capabilities,
    ):
        sessao = None
        try:
            sessao = self._abrir_sessao()
            capacidades = self._validar_termos(
                codigo=codigo,
                nome_publico=nome_publico,
                vertical=vertical,
                commercial_model=commercial_model,
                subject_type=subject_type,
                moeda=moeda,
                preco=preco,
                billing_period=billing_period,
                usage_unit=usage_unit,
                usage_limit=usage_limit,
                capabilities=capabilities,
            )

            existente = sessao.scalar(
                select(CheckoutOffer.id).where(CheckoutOffer.codigo == codigo)
            )
            if existente is not None:
                raise CheckoutOfferCatalogPublicationError()

            agora = datetime.utcnow()
            oferta = CheckoutOffer(
                codigo=codigo,
                nome_publico=nome_publico,
                vertical=vertical,
                commercial_model=commercial_model,
                subject_type=subject_type,
                estado="published",
                moeda=moeda,
                preco=preco,
                billing_period=billing_period,
                usage_unit=usage_unit,
                usage_limit=usage_limit,
                contract_version=1,
                criado_em=agora,
                atualizado_em=agora,
                capabilities=[
                    CheckoutOfferCapability(codigo=capacidade)
                    for capacidade in capacidades
                ],
            )
            sessao.add(oferta)
            sessao.flush()
            resultado = _catalog_contract.checkout_offer_snapshot(oferta)
            sessao.commit()
            return resultado
        except Exception:
            self._rollback(sessao)
            raise CheckoutOfferCatalogPublicationError() from None
        finally:
            self._fechar(sessao)

    def revisar_oferta(
        self,
        *,
        codigo,
        expected_contract_version,
        nome_publico,
        vertical,
        commercial_model,
        subject_type,
        moeda,
        preco,
        billing_period,
        usage_unit,
        usage_limit,
        capabilities,
    ):
        sessao = None
        try:
            sessao = self._abrir_sessao()
            self._inteiro_positivo(expected_contract_version)
            capacidades = self._validar_termos(
                codigo=codigo,
                nome_publico=nome_publico,
                vertical=vertical,
                commercial_model=commercial_model,
                subject_type=subject_type,
                moeda=moeda,
                preco=preco,
                billing_period=billing_period,
                usage_unit=usage_unit,
                usage_limit=usage_limit,
                capabilities=capabilities,
            )

            oferta = sessao.scalar(
                select(CheckoutOffer)
                .options(selectinload(CheckoutOffer.capabilities))
                .where(CheckoutOffer.codigo == codigo)
                .with_for_update()
            )
            if oferta is None:
                raise CheckoutOfferCatalogPublicationError()
            self._inteiro_positivo(oferta.contract_version)
            if oferta.contract_version != expected_contract_version:
                raise CheckoutOfferCatalogPublicationError()

            oferta.nome_publico = nome_publico
            oferta.vertical = vertical
            oferta.commercial_model = commercial_model
            oferta.subject_type = subject_type
            oferta.estado = "published"
            oferta.moeda = moeda
            oferta.preco = preco
            oferta.billing_period = billing_period
            oferta.usage_unit = usage_unit
            oferta.usage_limit = usage_limit
            oferta.contract_version = expected_contract_version + 1
            oferta.atualizado_em = datetime.utcnow()

            capacidades_atuais = {
                capability.codigo: capability
                for capability in oferta.capabilities
            }
            codigos_novos = set(capacidades)
            for codigo_atual, capability in capacidades_atuais.items():
                if codigo_atual not in codigos_novos:
                    sessao.delete(capability)

            sessao.flush()
            sessao.expire(oferta, ["capabilities"])
            codigos_preservados = {
                capability.codigo for capability in oferta.capabilities
            }
            for capacidade in capacidades:
                if capacidade not in codigos_preservados:
                    oferta.capabilities.append(
                        CheckoutOfferCapability(codigo=capacidade)
                    )

            sessao.flush()
            resultado = _catalog_contract.checkout_offer_snapshot(oferta)
            sessao.commit()
            return resultado
        except Exception:
            self._rollback(sessao)
            raise CheckoutOfferCatalogPublicationError() from None
        finally:
            self._fechar(sessao)

    def _abrir_sessao(self):
        sessao = self._session_factory()
        metodos = ("add", "commit", "flush", "rollback", "close", "scalar")
        if any(not callable(getattr(sessao, metodo, None)) for metodo in metodos):
            raise CheckoutOfferCatalogPublicationError()
        return sessao

    @classmethod
    def _validar_termos(
        cls,
        *,
        codigo,
        nome_publico,
        vertical,
        commercial_model,
        subject_type,
        moeda,
        preco,
        billing_period,
        usage_unit,
        usage_limit,
        capabilities,
    ):
        _catalog_contract.CheckoutOfferCatalog._validar_codigo_consulta(codigo)
        _catalog_contract.CheckoutOfferCatalog._texto(codigo, 120)
        _catalog_contract.CheckoutOfferCatalog._texto(nome_publico, 255)
        if vertical not in _catalog_contract._VERTICAIS:
            raise CheckoutOfferCatalogPublicationError()
        if commercial_model not in _catalog_contract._MODELOS:
            raise CheckoutOfferCatalogPublicationError()
        if subject_type not in _catalog_contract._SUJEITOS:
            raise CheckoutOfferCatalogPublicationError()

        configuracao = SimpleNamespace(
            commercial_model=commercial_model,
            moeda=moeda,
            preco=preco,
            billing_period=billing_period,
            usage_unit=usage_unit,
            usage_limit=usage_limit,
        )
        _catalog_contract.CheckoutOfferCatalog._configuracao_comercial(
            configuracao
        )

        if isinstance(capabilities, (str, bytes)):
            raise CheckoutOfferCatalogPublicationError()
        try:
            capacidades = tuple(capabilities)
        except TypeError:
            raise CheckoutOfferCatalogPublicationError() from None
        if not capacidades or len(capacidades) != len(set(capacidades)):
            raise CheckoutOfferCatalogPublicationError()
        if any(
            not isinstance(capacidade, str)
            or len(capacidade) > 120
            or _catalog_contract._CAPABILITY.fullmatch(capacidade) is None
            for capacidade in capacidades
        ):
            raise CheckoutOfferCatalogPublicationError()
        return tuple(sorted(capacidades))

    @staticmethod
    def _inteiro_positivo(valor):
        try:
            _catalog_contract.CheckoutOfferCatalog._inteiro_positivo(valor)
        except Exception:
            raise CheckoutOfferCatalogPublicationError() from None

    @staticmethod
    def _rollback(sessao):
        if sessao is not None:
            try:
                sessao.rollback()
            except Exception:
                pass

    @staticmethod
    def _fechar(sessao):
        if sessao is not None:
            try:
                sessao.close()
            except Exception:
                pass


__all__ = [
    "CheckoutOfferCatalogPublicationAuthority",
    "CheckoutOfferCatalogPublicationError",
]
