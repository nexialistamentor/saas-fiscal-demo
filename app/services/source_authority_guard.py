"""
SourceAuthorityGuard — B13-OPS-06.

Transforma data/fontes_tributarias_manifest.json em regra executável.

REGRAS:
- Determinístico e read-only.
- Não escreve no manifest.
- Não chama rede.
- Não chama LLM.
- Não altera DB.
- Não depende de runtime externo.

Sequência de verificação (ordem é lei):
1. fonte_id inexistente → bloqueia.
2. tipo=proibida_para_decisao → bloqueia qualquer uso fiscal/LLM.
3. uso=fundamentar_decisao + pode_fundamentar_decisao=false → bloqueia.
4. uso=fundamentar_decisao + tipo != normativa_oficial → bloqueia.
5. uso=validar_fato_operacional + pode_validar_fato_operacional=false → bloqueia.
6. uso=apoiar_explicacao_ux + tipo=operacional_oficial ou normativa_oficial → permitido (informativo apenas).
7. uso=contexto_llm + pode_ser_usada_por_llm=false → bloqueia.
8. Tudo OK → permite com evidência auditável.
"""
import json
from functools import lru_cache
from pathlib import Path

from app.schemas.source_authority_schema import SourceAuthorityRequest, SourceAuthorityResult

MANIFEST_PATH = Path("data/fontes_tributarias_manifest.json")


@lru_cache(maxsize=1)
def _carregar_manifest() -> dict:
    """Carrega manifest uma vez em memória. Read-only."""
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {fonte["id"]: fonte for fonte in data["fontes"]}


def _fonte_ou_none(fonte_id: str) -> dict | None:
    return _carregar_manifest().get(fonte_id)


def verificar(request: SourceAuthorityRequest) -> SourceAuthorityResult:
    """
    Verifica se o uso pretendido de uma fonte tributária é permitido.
    Determinístico. Sem efeitos secundários.
    """
    fonte = _fonte_ou_none(request.fonte_id)

    # 1. Fonte inexistente
    if fonte is None:
        return SourceAuthorityResult(
            permitido=False,
            fonte_id=request.fonte_id,
            uso_pretendido=request.uso_pretendido,
            motivo=f"Fonte '{request.fonte_id}' não existe no manifesto soberano.",
            acao="Verificar o id da fonte em data/fontes_tributarias_manifest.json.",
        )

    tipo = fonte["tipo"]
    nome = fonte["nome"]
    pode_fundamentar = fonte.get("pode_fundamentar_decisao", False)
    pode_validar = fonte.get("pode_validar_fato_operacional", False)
    pode_llm = fonte.get("pode_ser_usada_por_llm", False)

    def _base(permitido: bool, motivo: str, acao: str | None = None) -> SourceAuthorityResult:
        return SourceAuthorityResult(
            permitido=permitido,
            fonte_id=request.fonte_id,
            nome=nome,
            tipo=tipo,
            uso_pretendido=request.uso_pretendido,
            motivo=motivo,
            acao=acao,
            pode_fundamentar_decisao=pode_fundamentar,
            pode_validar_fato_operacional=pode_validar,
            pode_ser_usada_por_llm=pode_llm,
        )

    # 2. Proibida para qualquer uso fiscal/LLM
    if tipo == "proibida_para_decisao":
        return _base(
            False,
            f"Fonte '{request.fonte_id}' é vedação institucional — proibida para qualquer uso fiscal ou LLM.",
            "Não usar esta fonte. Consultar docs/FONTES_TRIBUTARIAS.md.",
        )

    # 3 + 4. Fundamentar decisão
    if request.uso_pretendido == "fundamentar_decisao":
        if tipo != "normativa_oficial":
            return _base(
                False,
                f"Fonte tipo '{tipo}' não pode fundamentar decisão fiscal. Apenas normativa_oficial pode.",
                "Usar esta fonte apenas para o seu escopo autorizado.",
            )
        if not pode_fundamentar:
            return _base(
                False,
                f"Fonte normativa '{request.fonte_id}' ainda não pode fundamentar decisão — sem hash_referencia ou internalização versionada.",
                "Internalizar, versionar e registar hash antes de usar como fundamento fiscal.",
            )
        return _base(
            True,
            "Fonte normativa oficial internalizada — pode fundamentar decisão fiscal.",
            "Usar apenas via motor determinístico versionado.",
        )

    # 5. Validar facto operacional
    if request.uso_pretendido == "validar_fato_operacional":
        if not pode_validar:
            return _base(
                False,
                f"Fonte '{request.fonte_id}' (tipo={tipo}) não está autorizada para validação de facto operacional.",
                "Verificar pode_validar_fato_operacional no manifesto.",
            )
        return _base(
            True,
            "Fonte autorizada para validação de facto operacional. Não fundamenta decisão fiscal.",
            "Usar apenas para validar cadastro, classificação ou situação — nunca para cálculo fiscal.",
        )

    # 6. Apoiar explicação UX
    if request.uso_pretendido == "apoiar_explicacao_ux":
        if tipo in ("informativa_oficial", "auxiliar_nao_normativa", "normativa_oficial", "operacional_oficial"):
            return _base(
                True,
                f"Fonte tipo '{tipo}' pode apoiar explicação UX/comunicacional.",
                "Usar apenas como apoio comunicacional. Nunca como fundamento de cálculo ou decisão.",
            )
        return _base(
            False,
            f"Fonte tipo '{tipo}' não autorizada para apoio UX.",
            None,
        )

    # 7. Contexto LLM
    if request.uso_pretendido == "contexto_llm":
        if not pode_llm:
            return _base(
                False,
                f"Fonte '{request.fonte_id}' (pode_ser_usada_por_llm=false) não pode ser enviada como contexto LLM.",
                "Não incluir esta fonte em prompts ou contextos enviados ao LLM.",
            )
        return _base(
            True,
            "Fonte permitida como contexto LLM supervisionado.",
            "Usar apenas como contexto informativo supervisionado. Não apresentar como autoridade fiscal final.",
        )

    # Fallback — uso não reconhecido
    return _base(
        False,
        f"Uso pretendido '{request.uso_pretendido}' não reconhecido.",
        None,
    )
