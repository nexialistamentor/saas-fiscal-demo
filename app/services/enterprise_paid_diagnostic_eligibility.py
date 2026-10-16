"""P1-02A — politica PURA de elegibilidade do diagnostico fiscal Enterprise.

O chamador DEVE validar antes o resultado persistido, o fingerprint e a
identidade da empresa. Esta funcao nao consulta BD, nao habilita pagamentos,
nao cria ofertas e NAO comprova creditos ou direitos fiscais.

Mantem-se distinta de tax_report_eligibility (oferta antiga de credito ST).
"""

from __future__ import annotations

import math
import re


_CHAVE_NFE = re.compile(r"[0-9]{44}\Z")
_UFS = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
    "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
    "RR", "SC", "SP", "SE", "TO",
})


def _lista_de_registos(valor: object) -> bool:
    """Listas vazias sao resultados negativos validos, nao prova de recuperacao."""
    return type(valor) is list and all(type(item) is dict for item in valor)


def _elegivel(resultado: object, empresa_id: object) -> bool:
    if type(empresa_id) is not int or empresa_id <= 0:
        return False
    if type(resultado) is not dict or type(resultado.get("empresa_id")) is not int:
        return False
    if resultado["empresa_id"] != empresa_id:
        return False

    documento = resultado.get("dados_fiscais")
    if type(documento) is not dict or documento.get("erro"):
        return False
    chave = documento.get("chave_nfe")
    if type(chave) is not str or _CHAVE_NFE.fullmatch(chave) is None:
        return False
    total = documento.get("valor_total_nota")
    if type(total) not in (int, float):
        return False
    if (type(total) is float and not math.isfinite(total)) or total < 0:
        return False
    if not any(documento.get(k) in _UFS for k in ("uf_emit", "uf_dest")
               if type(documento.get(k)) is str):
        return False

    # Mesmo uma consulta que nada encontra precisa de resultado documental
    # estruturado e de enriquecimento empresarial avaliado (pode ser vazio).
    insights = resultado.get("insights")
    if type(insights) is not dict or not _lista_de_registos(insights.get("documental")):
        return False
    if not _lista_de_registos(resultado.get("oportunidades")):
        return False
    if not _lista_de_registos(resultado.get("creditos_detectados")):
        return False
    if type(resultado.get("previsao_recuperacao")) is not dict:
        return False

    flags = resultado.get("context_flags")
    if type(flags) is not dict:
        return False
    for origem in ("documental", "empresarial"):
        estado = flags.get(origem)
        # Nao assumir que a ausencia de informacao significa completude.
        if type(estado) is not dict or estado.get("dados_incompletos") is not False:
            return False
    return True


def avaliar_elegibilidade_diagnostico_empresarial(
    resultado: object, *, empresa_id: int
) -> dict[str, bool]:
    """Projeta uma decisao informativa: nao concede checkout ou pagamento.

    `resultado` e o payload empresarial JA verificado por provenance.
    Nao reinterpreta credito ST estimado, nem importa o seu gate legado.
    """
    return {"eligible": _elegivel(resultado, empresa_id)}
