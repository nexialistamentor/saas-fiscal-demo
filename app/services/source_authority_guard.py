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
import re
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from app.schemas.source_authority_schema import (
    NormativeBindingReason,
    NormativeBindingReasonCode,
    NormativeBindingResult,
    NormativeBindingStatus,
    SourceAuthorityRequest,
    SourceAuthorityResult,
    _CONSTANTE_ID_PATTERN,
    _DATASET_ID_PATTERN,
    _FONTE_ID_PATTERN,
    _INVARIANTE_PATTERN,
    _JURISDICAO_PATTERN,
    _VERSAO_FONTE_PATTERN,
)

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




_REASON_PRECEDENCE = {
    code: index
    for index, code in enumerate(NormativeBindingReasonCode)
}


def _reason_sort_key(
    reason: NormativeBindingReason,
) -> tuple[int, int, str]:
    binding_index = (
        -1
        if reason.binding_index is None
        else reason.binding_index
    )
    field = "" if reason.field is None else reason.field

    return (
        _REASON_PRECEDENCE[reason.code],
        binding_index,
        field,
    )


def _identificador_valido(value: Any, pattern: re.Pattern[str]) -> bool:
    if not isinstance(value, str):
        return False
    if value != unicodedata.normalize("NFKC", value):
        return False
    if value != value.strip():
        return False
    if any(unicodedata.category(char).startswith("C") for char in value):
        return False
    return pattern.fullmatch(value) is not None


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None



def _alvos_normativos_autorizados(
    fonte: Mapping[str, Any],
) -> frozenset[tuple[str, str]] | None:
    raw = fonte.get("alvos_normativos_autorizados")

    if not isinstance(raw, list) or not raw:
        return None

    alvos: set[tuple[str, str]] = set()

    for item in raw:
        if not isinstance(item, Mapping):
            return None

        if set(item) != {"tipo", "id"}:
            return None

        tipo = item.get("tipo")
        alvo_id = item.get("id")

        if tipo == "constante":
            pattern = _CONSTANTE_ID_PATTERN
        elif tipo == "dataset":
            pattern = _DATASET_ID_PATTERN
        else:
            return None

        if not _identificador_valido(alvo_id, pattern):
            return None

        alvo = (tipo, alvo_id)

        if alvo in alvos:
            return None

        alvos.add(alvo)

    return frozenset(alvos)


_NORMATIVE_BINDING_COMMON_FIELDS = frozenset(
    {
        "fonte_id",
        "versao_fonte",
        "vigencia_inicio",
        "vigencia_fim",
        "jurisdicao_codigo",
        "risco",
        "invariantes",
    }
)

_NORMATIVE_BINDING_TARGET_FIELDS = frozenset(
    {
        "constante_id",
        "dataset_id",
    }
)

_NORMATIVE_BINDING_ITEM_FIELDS = (
    _NORMATIVE_BINDING_COMMON_FIELDS
    | _NORMATIVE_BINDING_TARGET_FIELDS
)


def validar_bindings_normativos(
    payload: Mapping[str, Any],
) -> NormativeBindingResult:
    """Valida bindings normativos de forma determinística e fail-closed."""
    bindings = payload.get("bindings")

    if isinstance(bindings, (list, tuple)):
        reasons_list = []

        for index, binding in enumerate(bindings):
            if not isinstance(binding, Mapping):
                continue

            for field in sorted(
                _NORMATIVE_BINDING_COMMON_FIELDS.difference(binding)
            ):
                reasons_list.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.CAMPO_OBRIGATORIO_AUSENTE,
                        binding_index=index,
                        field=field,
                    )
                )

            target_fields_present = [
                field
                for field in _NORMATIVE_BINDING_TARGET_FIELDS
                if field in binding
            ]

            if len(target_fields_present) == 0:
                reasons_list.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.ALVO_NORMATIVO_AUSENTE,
                        binding_index=index,
                        field="constante_id|dataset_id",
                    )
                )
            elif len(target_fields_present) > 1:
                reasons_list.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.ALVO_NORMATIVO_AMBIGUO,
                        binding_index=index,
                        field="constante_id|dataset_id",
                    )
                )

            for field in sorted(
                key
                for key in binding
                if isinstance(key, str)
                and key not in _NORMATIVE_BINDING_ITEM_FIELDS
            ):
                reasons_list.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.CAMPO_DESCONHECIDO,
                        binding_index=index,
                        field=field,
                    )
                )

            for field, pattern in (
                ("constante_id", _CONSTANTE_ID_PATTERN),
                ("dataset_id", _DATASET_ID_PATTERN),
                ("fonte_id", _FONTE_ID_PATTERN),
            ):
                if field in binding and not _identificador_valido(
                    binding[field],
                    pattern,
                ):
                    reasons_list.append(
                        NormativeBindingReason(
                            code=NormativeBindingReasonCode.IDENTIFICADOR_INVALIDO,
                            binding_index=index,
                            field=field,
                        )
                    )

            if (
                "versao_fonte" in binding
                and not _identificador_valido(
                    binding["versao_fonte"],
                    _VERSAO_FONTE_PATTERN,
                )
            ):
                reasons_list.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.VERSAO_INVALIDA,
                        binding_index=index,
                        field="versao_fonte",
                    )
                )

        jurisdiction_reasons = []
        contexto = payload.get("contexto")

        if (
            isinstance(contexto, Mapping)
            and "data_referencia" in contexto
            and _parse_iso_date(
                contexto["data_referencia"]
            ) is None
        ):
            reasons_list.append(
                NormativeBindingReason(
                    code=NormativeBindingReasonCode.CONTEXTO_INVALIDO,
                    binding_index=None,
                    field="data_referencia",
                )
            )

        if (
            isinstance(contexto, Mapping)
            and "uso_solicitado" in contexto
            and contexto["uso_solicitado"]
            not in (
                "diagnostico",
                "estimativa",
                "decisao_definitiva",
            )
        ):
            reasons_list.append(
                NormativeBindingReason(
                    code=NormativeBindingReasonCode.CONTEXTO_INVALIDO,
                    binding_index=None,
                    field="uso_solicitado",
                )
            )

        if (
            isinstance(contexto, Mapping)
            and "jurisdicao_codigo" in contexto
            and not _identificador_valido(
                contexto["jurisdicao_codigo"],
                _JURISDICAO_PATTERN,
            )
        ):
            jurisdiction_reasons.append(
                NormativeBindingReason(
                    code=NormativeBindingReasonCode.JURISDICAO_INVALIDA,
                    binding_index=None,
                    field="jurisdicao_codigo",
                )
            )

        for index, binding in enumerate(bindings):
            if (
                isinstance(binding, Mapping)
                and "jurisdicao_codigo" in binding
                and not _identificador_valido(
                    binding["jurisdicao_codigo"],
                    _JURISDICAO_PATTERN,
                )
            ):
                jurisdiction_reasons.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.JURISDICAO_INVALIDA,
                        binding_index=index,
                        field="jurisdicao_codigo",
                    )
                )

        reasons_list.extend(jurisdiction_reasons)

        for index, binding in enumerate(bindings):
            if (
                isinstance(binding, Mapping)
                and "risco" in binding
                and binding["risco"]
                not in ("alto", "baixo", "critico", "medio")
            ):
                reasons_list.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.RISCO_INVALIDO,
                        binding_index=index,
                        field="risco",
                    )
                )

        for index, binding in enumerate(bindings):
            if not isinstance(binding, Mapping):
                continue

            invariantes = binding.get("invariantes")

            if (
                "invariantes" in binding
                and (
                    not isinstance(invariantes, (list, tuple))
                    or not invariantes
                    or any(
                        not _identificador_valido(
                            invariante,
                            _INVARIANTE_PATTERN,
                        )
                        for invariante in invariantes
                    )
                    or len(set(invariantes)) != len(invariantes)
                    or tuple(invariantes) != tuple(sorted(invariantes))
                )
            ):
                reasons_list.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.INVARIANTES_INVALIDOS,
                        binding_index=index,
                        field="invariantes",
                    )
                )

        pairwise_structural_codes = {
            NormativeBindingReasonCode.CAMPO_OBRIGATORIO_AUSENTE,
            NormativeBindingReasonCode.CAMPO_DESCONHECIDO,
            NormativeBindingReasonCode.ALVO_NORMATIVO_AUSENTE,
            NormativeBindingReasonCode.ALVO_NORMATIVO_AMBIGUO,
            NormativeBindingReasonCode.IDENTIFICADOR_INVALIDO,
            NormativeBindingReasonCode.VERSAO_INVALIDA,
            NormativeBindingReasonCode.VIGENCIA_INVALIDA,
            NormativeBindingReasonCode.JURISDICAO_INVALIDA,
            NormativeBindingReasonCode.RISCO_INVALIDO,
            NormativeBindingReasonCode.INVARIANTES_INVALIDOS,
        }

        structurally_invalid_indexes = {
            reason.binding_index
            for reason in reasons_list
            if reason.binding_index is not None
            and reason.code in pairwise_structural_codes
        }

        def _has_binding_reason(
            binding_index: int,
            code: NormativeBindingReasonCode,
            field: str | None = None,
        ) -> bool:
            return any(
                reason.binding_index == binding_index
                and reason.code == code
                and (
                    field is None
                    or reason.field == field
                )
                for reason in reasons_list
            )

        for index, binding in enumerate(bindings):
            if (
                index in structurally_invalid_indexes
                or not isinstance(binding, Mapping)
            ):
                continue

            inicio = _parse_iso_date(
                binding.get("vigencia_inicio")
            )
            fim_raw = binding.get("vigencia_fim")
            fim = (
                None
                if fim_raw is None
                else _parse_iso_date(fim_raw)
            )

            if (
                inicio is None
                or (fim_raw is not None and fim is None)
                or (fim is not None and fim < inicio)
            ):
                continue

            previous_candidates = []

            for previous_index, previous in enumerate(
                bindings[:index]
            ):
                if (
                    previous_index in structurally_invalid_indexes
                    or not isinstance(previous, Mapping)
                ):
                    continue

                previous_inicio = _parse_iso_date(
                    previous.get("vigencia_inicio")
                )
                previous_fim_raw = previous.get("vigencia_fim")
                previous_fim = (
                    None
                    if previous_fim_raw is None
                    else _parse_iso_date(previous_fim_raw)
                )

                if (
                    previous_inicio is None
                    or (
                        previous_fim_raw is not None
                        and previous_fim is None
                    )
                    or (
                        previous_fim is not None
                        and previous_fim < previous_inicio
                    )
                ):
                    continue

                previous_candidates.append(
                    (
                        previous,
                        previous_inicio,
                        previous_fim,
                    )
                )

            if any(
                binding == previous
                for previous, _, _ in previous_candidates
            ):
                reasons_list.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.BINDING_DUPLICADO,
                        binding_index=index,
                        field="bindings",
                    )
                )
                continue

            for (
                previous,
                previous_inicio,
                previous_fim,
            ) in previous_candidates:
                binding_target = (
                    ("constante_id", binding.get("constante_id"))
                    if "constante_id" in binding
                    else ("dataset_id", binding.get("dataset_id"))
                )
                previous_target = (
                    ("constante_id", previous.get("constante_id"))
                    if "constante_id" in previous
                    else ("dataset_id", previous.get("dataset_id"))
                )

                mesma_chave = (
                    binding_target == previous_target
                    and binding.get("jurisdicao_codigo")
                    == previous.get("jurisdicao_codigo")
                )

                sobrepostos = (
                    (
                        previous_fim is None
                        or inicio <= previous_fim
                    )
                    and (
                        fim is None
                        or previous_inicio <= fim
                    )
                )

                if mesma_chave and sobrepostos:
                    reasons_list.append(
                        NormativeBindingReason(
                            code=NormativeBindingReasonCode.BINDINGS_CONFLITANTES,
                            binding_index=index,
                            field="bindings",
                        )
                    )
                    break

        jurisdiction_compatibility_reasons = []

        contexto_jurisdicao = (
            contexto.get("jurisdicao_codigo")
            if isinstance(contexto, Mapping)
            else None
        )

        if (
            isinstance(contexto_jurisdicao, str)
            and _identificador_valido(
                contexto_jurisdicao,
                _JURISDICAO_PATTERN,
            )
        ):
            for index, binding in enumerate(bindings):
                if (
                    index in structurally_invalid_indexes
                    or not isinstance(binding, Mapping)
                ):
                    continue

                binding_jurisdicao = binding.get("jurisdicao_codigo")

                if (
                    isinstance(binding_jurisdicao, str)
                    and binding_jurisdicao != contexto_jurisdicao
                ):
                    jurisdiction_compatibility_reasons.append(
                        NormativeBindingReason(
                            code=NormativeBindingReasonCode.JURISDICAO_INCOMPATIVEL,
                            binding_index=index,
                            field="jurisdicao_codigo",
                        )
                    )

        reasons_list.extend(jurisdiction_compatibility_reasons)

        missing_source_reasons = []

        for index, binding in enumerate(bindings):
            if (
                not isinstance(binding, Mapping)
                or _has_binding_reason(
                    index,
                    NormativeBindingReasonCode.IDENTIFICADOR_INVALIDO,
                    "fonte_id",
                )
            ):
                continue

            fonte_id = binding.get("fonte_id")

            if (
                isinstance(fonte_id, str)
                and _fonte_ou_none(fonte_id) is None
            ):
                missing_source_reasons.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.FONTE_INEXISTENTE,
                        binding_index=index,
                        field="fonte_id",
                    )
                )

        reasons_list.extend(missing_source_reasons)

        source_required_non_null_fields = (
            "id",
            "tipo",
            "nome",
            "pode_fundamentar_decisao",
            "pode_validar_fato_operacional",
            "pode_ser_usada_por_llm",
            "versao",
            "vigencia_inicio",
            "jurisdicao",
            "risco_se_desatualizada",
            "hash_referencia",
        )
        source_required_present_fields = (
            "vigencia_fim",
        )
        incomplete_source_reasons = []

        for index, binding in enumerate(bindings):
            if not isinstance(binding, Mapping):
                continue

            fonte_id = binding.get("fonte_id")
            fonte = (
                _fonte_ou_none(fonte_id)
                if isinstance(fonte_id, str)
                else None
            )

            if fonte is None:
                continue

            fonte_inicio = (
                _parse_iso_date(fonte.get("vigencia_inicio"))
                if isinstance(fonte, Mapping)
                else None
            )
            fonte_fim_raw = (
                fonte.get("vigencia_fim")
                if isinstance(fonte, Mapping)
                else None
            )
            fonte_fim = (
                None
                if fonte_fim_raw is None
                else _parse_iso_date(fonte_fim_raw)
            )

            fonte_temporal_invalida = (
                fonte_inicio is None
                or (
                    fonte_fim_raw is not None
                    and fonte_fim is None
                )
                or (
                    fonte_inicio is not None
                    and fonte_fim is not None
                    and fonte_fim < fonte_inicio
                )
            )

            fonte_incompleta = (
                not isinstance(fonte, Mapping)
                or any(
                    field not in fonte
                    or fonte[field] is None
                    for field in source_required_non_null_fields
                )
                or any(
                    field not in fonte
                    for field in source_required_present_fields
                )
                or fonte_temporal_invalida
                or (
                    fonte.get("pode_fundamentar_decisao") is True
                    and not _identificador_valido(
                        fonte.get("jurisdicao_codigo"),
                        _JURISDICAO_PATTERN,
                    )
                )
                or (
                    fonte.get("pode_fundamentar_decisao") is True
                    and _alvos_normativos_autorizados(fonte) is None
                )
            )

            if fonte_incompleta:
                incomplete_source_reasons.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.FONTE_INCOMPLETA,
                        binding_index=index,
                        field="fonte_id",
                    )
                )

        reasons_list.extend(incomplete_source_reasons)

        source_jurisdiction_reasons = []

        for index, binding in enumerate(bindings):
            if not isinstance(binding, Mapping):
                continue

            if _has_binding_reason(
                index,
                NormativeBindingReasonCode.JURISDICAO_INVALIDA,
                "jurisdicao_codigo",
            ):
                continue

            if _has_binding_reason(
                index,
                NormativeBindingReasonCode.FONTE_INCOMPLETA,
                "fonte_id",
            ):
                continue

            fonte_id = binding.get("fonte_id")
            fonte = (
                _fonte_ou_none(fonte_id)
                if isinstance(fonte_id, str)
                else None
            )

            if (
                not isinstance(fonte, Mapping)
                or fonte.get("pode_fundamentar_decisao") is not True
            ):
                continue

            fonte_jurisdicao = fonte.get("jurisdicao_codigo")
            binding_jurisdicao = binding.get("jurisdicao_codigo")

            if (
                isinstance(fonte_jurisdicao, str)
                and isinstance(binding_jurisdicao, str)
                and fonte_jurisdicao != binding_jurisdicao
            ):
                source_jurisdiction_reasons.append(
                    NormativeBindingReason(
                        code=(
                            NormativeBindingReasonCode
                            .JURISDICAO_INCOMPATIVEL
                        ),
                        binding_index=index,
                        field="jurisdicao_codigo",
                    )
                )

        reasons_list.extend(source_jurisdiction_reasons)

        source_scope_reasons = []

        for index, binding in enumerate(bindings):
            if not isinstance(binding, Mapping):
                continue

            if _has_binding_reason(
                index,
                NormativeBindingReasonCode.FONTE_INCOMPLETA,
                "fonte_id",
            ):
                continue

            fonte_id = binding.get("fonte_id")
            fonte = (
                _fonte_ou_none(fonte_id)
                if isinstance(fonte_id, str)
                else None
            )

            if (
                not isinstance(fonte, Mapping)
                or fonte.get("pode_fundamentar_decisao") is not True
            ):
                continue

            alvos_autorizados = _alvos_normativos_autorizados(fonte)

            if alvos_autorizados is None:
                continue

            target_fields_present = [
                field
                for field in _NORMATIVE_BINDING_TARGET_FIELDS
                if field in binding
            ]

            if len(target_fields_present) != 1:
                continue

            target_field = target_fields_present[0]
            target_id = binding.get(target_field)

            if target_field == "constante_id":
                target_type = "constante"
                pattern = _CONSTANTE_ID_PATTERN
            else:
                target_type = "dataset"
                pattern = _DATASET_ID_PATTERN

            if not _identificador_valido(target_id, pattern):
                continue

            if (target_type, target_id) not in alvos_autorizados:
                source_scope_reasons.append(
                    NormativeBindingReason(
                        code=(
                            NormativeBindingReasonCode
                            .ALVO_FORA_DO_ESCOPO_DA_FONTE
                        ),
                        binding_index=index,
                        field=target_field,
                    )
                )

        reasons_list.extend(source_scope_reasons)

        _source_version_reasons = []

        for index, binding in enumerate(bindings):
            if (
                not isinstance(binding, Mapping)
                or _has_binding_reason(
                    index,
                    NormativeBindingReasonCode.VERSAO_INVALIDA,
                    "versao_fonte",
                )
            ):
                continue

            fonte_id = binding.get("fonte_id")
            versao_binding = binding.get("versao_fonte")
            fonte = (
                _fonte_ou_none(fonte_id)
                if isinstance(fonte_id, str)
                else None
            )

            if (
                fonte is not None
                and fonte.get("versao") is not None
                and versao_binding != fonte["versao"]
            ):
                _source_version_reasons.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.VERSAO_FONTE_INCOMPATIVEL,
                        binding_index=index,
                        field="versao_fonte",
                    )
                )

        reasons_list.extend(_source_version_reasons)

        source_risk_reasons = []

        for index, binding in enumerate(bindings):
            if (
                not isinstance(binding, Mapping)
                or _has_binding_reason(
                    index,
                    NormativeBindingReasonCode.RISCO_INVALIDO,
                    "risco",
                )
            ):
                continue

            fonte_id = binding.get("fonte_id")
            fonte = (
                _fonte_ou_none(fonte_id)
                if isinstance(fonte_id, str)
                else None
            )

            risco_binding = binding.get("risco")
            risco_fonte = (
                fonte.get("risco_se_desatualizada")
                if isinstance(fonte, Mapping)
                else None
            )

            if (
                isinstance(risco_binding, str)
                and isinstance(risco_fonte, str)
                and risco_binding != risco_fonte
            ):
                source_risk_reasons.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.RISCO_FONTE_INCOMPATIVEL,
                        binding_index=index,
                        field="risco",
                    )
                )

        reasons_list.extend(source_risk_reasons)

        temporal_reasons = []

        for index, binding in enumerate(bindings):
            if not isinstance(binding, Mapping):
                continue

            inicio = _parse_iso_date(binding.get("vigencia_inicio"))
            fim_raw = binding.get("vigencia_fim")
            fim = None if fim_raw is None else _parse_iso_date(fim_raw)

            if inicio is not None and fim is not None and fim < inicio:
                temporal_reasons.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.VIGENCIA_INVALIDA,
                        binding_index=index,
                        field="vigencia_fim",
                    )
                )

        reasons_list.extend(temporal_reasons)

        source_validity_reasons = []

        # Pairwise duplicate/conflict reasons do not make a binding
        # ineligible for independently verifiable source compatibility.
        for index, binding in enumerate(bindings):
            if (
                not isinstance(binding, Mapping)
                or _has_binding_reason(
                    index,
                    NormativeBindingReasonCode.VIGENCIA_INVALIDA,
                )
                or _has_binding_reason(
                    index,
                    NormativeBindingReasonCode.FONTE_INCOMPLETA,
                    "fonte_id",
                )
            ):
                continue

            fonte_id = binding.get("fonte_id")
            fonte = (
                _fonte_ou_none(fonte_id)
                if isinstance(fonte_id, str)
                else None
            )

            if not isinstance(fonte, Mapping):
                continue

            binding_inicio = _parse_iso_date(
                binding.get("vigencia_inicio")
            )
            binding_fim_raw = binding.get("vigencia_fim")
            binding_fim = (
                None
                if binding_fim_raw is None
                else _parse_iso_date(binding_fim_raw)
            )

            fonte_inicio = _parse_iso_date(
                fonte.get("vigencia_inicio")
            )
            fonte_fim_raw = fonte.get("vigencia_fim")
            fonte_fim = (
                None
                if fonte_fim_raw is None
                else _parse_iso_date(fonte_fim_raw)
            )

            if (
                binding_inicio is not None
                and fonte_inicio is not None
                and binding_inicio < fonte_inicio
            ):
                source_validity_reasons.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.VIGENCIA_FONTE_INCOMPATIVEL,
                        binding_index=index,
                        field="vigencia_inicio",
                    )
                )

            if (
                "vigencia_fim" in binding
                and fonte_fim_raw is not None
                and fonte_fim is not None
                and (
                    binding_fim_raw is None
                    or (
                        binding_fim is not None
                        and binding_fim > fonte_fim
                    )
                )
            ):
                source_validity_reasons.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.VIGENCIA_FONTE_INCOMPATIVEL,
                        binding_index=index,
                        field="vigencia_fim",
                    )
                )

        reasons_list.extend(source_validity_reasons)

        contexto = payload.get("contexto")
        data_referencia = (
            _parse_iso_date(contexto.get("data_referencia"))
            if isinstance(contexto, Mapping)
            else None
        )

        todos_na_vigencia = (
            data_referencia is not None
            and bool(bindings)
        )

        if todos_na_vigencia:
            for binding in bindings:
                if not isinstance(binding, Mapping):
                    todos_na_vigencia = False
                    break

                inicio = _parse_iso_date(binding.get("vigencia_inicio"))
                fim_raw = binding.get("vigencia_fim")
                fim = None if fim_raw is None else _parse_iso_date(fim_raw)

                if (
                    inicio is None
                    or data_referencia < inicio
                    or (fim is not None and data_referencia > fim)
                ):
                    todos_na_vigencia = False
                    break

        outside_validity_reasons = []

        if data_referencia is not None:
            for index, binding in enumerate(bindings):
                if (
                    not isinstance(binding, Mapping)
                    or _has_binding_reason(
                        index,
                        NormativeBindingReasonCode.VIGENCIA_INVALIDA,
                    )
                    or _has_binding_reason(
                        index,
                        NormativeBindingReasonCode.BINDING_DUPLICADO,
                    )
                    or _has_binding_reason(
                        index,
                        NormativeBindingReasonCode.BINDINGS_CONFLITANTES,
                    )
                ):
                    continue

                inicio = _parse_iso_date(binding.get("vigencia_inicio"))
                fim_raw = binding.get("vigencia_fim")
                fim = None if fim_raw is None else _parse_iso_date(fim_raw)

                if inicio is None:
                    continue
                if fim_raw is not None and fim is None:
                    continue

                if (
                    data_referencia < inicio
                    or (fim is not None and data_referencia > fim)
                ):
                    outside_validity_reasons.append(
                        NormativeBindingReason(
                            code=NormativeBindingReasonCode.FORA_DA_VIGENCIA,
                            binding_index=index,
                            field="data_referencia",
                        )
                    )

        reasons_list.extend(outside_validity_reasons)

        if reasons_list:
            ordered_reasons = tuple(
                sorted(
                    reasons_list,
                    key=_reason_sort_key,
                )
            )

            return NormativeBindingResult(
                status=NormativeBindingStatus.invalido,
                autorizado_fundamentar_decisao=False,
                reasons=ordered_reasons,
                bindings_validados=0,
            )

        if todos_na_vigencia:
            authority_reasons = []

            for index, binding in enumerate(bindings):
                fonte_id = binding.get("fonte_id")
                autoridade = verificar(
                    SourceAuthorityRequest(
                        fonte_id=fonte_id,
                        uso_pretendido="fundamentar_decisao",
                    )
                )

                if not autoridade.permitido:
                    authority_reasons.append(
                        NormativeBindingReason(
                            code=NormativeBindingReasonCode.FONTE_NAO_AUTORIZADA,
                            binding_index=index,
                            field="fonte_id",
                        )
                    )

            if (
                authority_reasons
                and isinstance(contexto, Mapping)
                and contexto.get("uso_solicitado")
                == "decisao_definitiva"
            ):
                authority_reasons.append(
                    NormativeBindingReason(
                        code=NormativeBindingReasonCode.DECISAO_DEFINITIVA_BLOQUEADA,
                        binding_index=None,
                        field="uso_solicitado",
                    )
                )

            if authority_reasons:
                return NormativeBindingResult(
                    status=NormativeBindingStatus.valido_sem_autoridade_decisoria,
                    autorizado_fundamentar_decisao=False,
                    reasons=tuple(authority_reasons),
                    bindings_validados=len(bindings),
                )

            return NormativeBindingResult(
                status=NormativeBindingStatus.valido_com_autoridade_decisoria,
                autorizado_fundamentar_decisao=True,
                reasons=(),
                bindings_validados=len(bindings),
            )

    raise NotImplementedError("B13-OPS-12C-P0: comportamento ainda não implementado.")
