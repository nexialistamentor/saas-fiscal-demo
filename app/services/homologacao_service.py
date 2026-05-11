"""
HomologacaoService — domínio regulatório soberano.

Responsabilidades:
- Criar fila de homologação para documentos com confiança intermédia
- Registar decisão do contador (aprovado/rejeitado) com parecer auditável
- Gerar assinatura lógica V1 (não repúdio básico)
- Garantir 1 homologação activa por documento em V1 (via service layer)

Princípio: assinatura é regra de domínio — gerada aqui, nunca no router.

AVISO ARQUITECTURAL V1:
    assinatura_logica = SHA-256 lógico (não criptográfico PKI).
    V2: ICP-Brasil, certificado e-CNPJ, cadeia PKI completa.
"""

import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import HomologacaoDocumental, PerfilContador


class HomologacaoError(Exception):
    def __init__(self, mensagem: str = "Erro no processo de homologação"):
        self.mensagem = mensagem
        super().__init__(mensagem)


class HomologacaoJaExisteError(HomologacaoError):
    def __init__(self):
        super().__init__("Documento já possui homologação activa pendente ou aprovada")


class ContadorNaoAprovadoError(HomologacaoError):
    def __init__(self):
        super().__init__("Contador não está aprovado para realizar homologações")


class HomologacaoNaoPendenteError(HomologacaoError):
    def __init__(self, status: str):
        super().__init__(f"Homologação não pode ser decidida — estado actual: {status}")


# ---------------------------------------------------------------------------
# Assinatura lógica V1
# ---------------------------------------------------------------------------
def _gerar_assinatura_logica(
    parecer_texto: str,
    contador_id: int,
    documento_ingerido_id: int,
    decidido_em: datetime,
) -> str:
    """
    SHA-256(parecer + contador_id + documento_id + timestamp).

    Não repúdio básico V1 — V2 usa ICP-Brasil.
    """
    payload = (
        f"{parecer_texto}"
        f"{contador_id}"
        f"{documento_ingerido_id}"
        f"{decidido_em.isoformat()}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------
def criar_fila_homologacao(
    db: Session,
    documento_ingerido_id: int,
    contador_id: int,
    tipo_decisao: str = "homologacao_documental",
) -> HomologacaoDocumental:
    """
    Cria entrada na fila de homologação para documento com confiança intermédia.

    V1: garante 1 homologação activa por documento via service layer.
    """
    # Validar contador aprovado
    contador = db.query(PerfilContador).filter(
        PerfilContador.id == contador_id
    ).first()

    if not contador or contador.status != "aprovado":
        raise ContadorNaoAprovadoError()

    # V1: 1 homologação activa por documento
    existente = db.query(HomologacaoDocumental).filter(
        HomologacaoDocumental.documento_ingerido_id == documento_ingerido_id,
        HomologacaoDocumental.status.in_(["pendente", "aprovado"]),
    ).first()

    if existente:
        raise HomologacaoJaExisteError()

    homologacao = HomologacaoDocumental(
        documento_ingerido_id=documento_ingerido_id,
        contador_id=contador_id,
        tipo_decisao=tipo_decisao,
        versao_parecer="1.0",
        status="pendente",
    )
    db.add(homologacao)
    db.flush()
    return homologacao


def registar_decisao(
    db: Session,
    homologacao_id: int,
    status_decisao: str,
    parecer_texto: str,
    contador_id: int,
) -> HomologacaoDocumental:
    """
    Regista decisão do contador (aprovado/rejeitado) com assinatura lógica.

    Só actua sobre homologações pendentes.
    """
    if status_decisao not in ("aprovado", "rejeitado"):
        raise HomologacaoError(f"Status inválido: {status_decisao}")

    homologacao = db.query(HomologacaoDocumental).filter(
        HomologacaoDocumental.id == homologacao_id,
        HomologacaoDocumental.contador_id == contador_id,
    ).first()

    if not homologacao:
        raise HomologacaoError("Homologação não encontrada para este contador")

    if homologacao.status != "pendente":
        raise HomologacaoNaoPendenteError(homologacao.status)

    decidido_em = datetime.utcnow()
    assinatura = _gerar_assinatura_logica(
        parecer_texto=parecer_texto,
        contador_id=contador_id,
        documento_ingerido_id=homologacao.documento_ingerido_id,
        decidido_em=decidido_em,
    )

    homologacao.status = status_decisao
    homologacao.parecer_texto = parecer_texto
    homologacao.assinatura_logica = assinatura
    homologacao.decidido_em = decidido_em

    db.flush()
    return homologacao


def obter_homologacoes_pendentes(
    db: Session,
    contador_id: int,
) -> list[HomologacaoDocumental]:
    """Devolve homologações pendentes atribuídas a um contador."""
    return (
        db.query(HomologacaoDocumental)
        .filter(
            HomologacaoDocumental.contador_id == contador_id,
            HomologacaoDocumental.status == "pendente",
        )
        .order_by(HomologacaoDocumental.criado_em.asc())
        .all()
    )
