from sqlalchemy import UniqueConstraint

from app import models


def test_mei_competencia_authority_binding_is_vertical_and_provider_agnostic():
    assert hasattr(models, "MeiCompetenciaAuthorityBinding")

    model = models.MeiCompetenciaAuthorityBinding
    table = model.__table__

    assert table.name == "mei_competencia_authority_bindings"

    assert set(table.columns.keys()) == {
        "id",
        "ordem_id",
        "empresa_id",
        "competencia",
        "capability",
        "created_at",
    }

    assert "grant_id" not in table.columns
    assert "payment_id" not in table.columns
    assert "provider_order_id" not in table.columns
    assert "mercado_pago_id" not in table.columns

    ordem_fk = {fk.target_fullname for fk in table.c.ordem_id.foreign_keys}
    empresa_fk = {fk.target_fullname for fk in table.c.empresa_id.foreign_keys}

    assert ordem_fk == {"ordens_checkout.id"}
    assert empresa_fk == {"empresas.id"}

    uniques = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert (
        "empresa_id",
        "competencia",
        "capability",
    ) in uniques


def test_mei_competencia_authority_binding_rejeita_competencia_fora_de_yyyymm():
    from sqlalchemy import CheckConstraint

    table = models.MeiCompetenciaAuthorityBinding.__table__

    checks = " ".join(
        str(constraint.sqltext).lower()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )

    assert "length(competencia) = 6" in checks

    for posicao in range(1, 7):
        assert (
            f"substr(competencia, {posicao}, 1) between '0' and '9'"
            in checks
        )

    assert "substr(competencia, 5, 2) between '01' and '12'" in checks


def test_mei_competencia_authority_binding_is_append_only_in_orm():
    from sqlalchemy import event

    model = models.MeiCompetenciaAuthorityBinding

    guard = getattr(
        models,
        "_reject_mei_competencia_authority_binding_mutation",
        None,
    )

    assert guard is not None
    assert event.contains(model, "before_update", guard)
    assert event.contains(model, "before_delete", guard)
