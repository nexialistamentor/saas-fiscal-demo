"""
Controle de limites e uso da plataforma (Billing / Usage).

Verifica limites antes de executar análise e registra uso após conclusão.
Necessário para monetização, controle de abuso e definição de planos SaaS.
"""

from datetime import datetime

from app.models import UsoPlataforma


class LimiteAnalisesAtingidoError(Exception):
    """Exceção quando o limite de análises do mês foi atingido."""

    def __init__(self, msg: str = "Limite de análises atingido."):
        super().__init__(msg)


def verificar_limite_analises(db, empresa_id: int | None, limite: int = 100) -> None:
    """
    Verifica se a empresa ainda está dentro do limite de análises do mês.
    Se empresa_id for None, não aplica verificação.
    Raises Exception se limite atingido.
    """
    if empresa_id is None:
        return

    agora = datetime.utcnow()
    uso = (
        db.query(UsoPlataforma)
        .filter(
            UsoPlataforma.empresa_id == empresa_id,
            UsoPlataforma.mes == agora.month,
            UsoPlataforma.ano == agora.year,
        )
        .first()
    )

    if uso and uso.analises_mes >= limite:
        raise LimiteAnalisesAtingidoError(
            f"Limite de análises atingido ({limite}/mês). "
            "Faça upgrade do plano para continuar."
        )


def _obter_ou_criar_uso(db, empresa_id: int) -> UsoPlataforma:
    """Obtém ou cria registro de uso do mês atual para a empresa."""
    agora = datetime.utcnow()
    uso = (
        db.query(UsoPlataforma)
        .filter(
            UsoPlataforma.empresa_id == empresa_id,
            UsoPlataforma.mes == agora.month,
            UsoPlataforma.ano == agora.year,
        )
        .first()
    )
    if not uso:
        uso = UsoPlataforma(
            empresa_id=empresa_id,
            analises_mes=0,
            xmls_processados=0,
            mes=agora.month,
            ano=agora.year,
        )
        db.add(uso)
        db.flush()
    return uso


def incrementar_uso_analise(db, empresa_id: int | None, xmls: int = 1) -> None:
    """
    Incrementa contadores de uso após conclusão de análise.
    empresa_id=None: não registra uso.
    xmls: quantidade de XMLs processados na análise (default 1).
    """
    if empresa_id is None:
        return

    uso = _obter_ou_criar_uso(db, empresa_id)
    uso.analises_mes += 1
    uso.xmls_processados += xmls
    db.commit()
