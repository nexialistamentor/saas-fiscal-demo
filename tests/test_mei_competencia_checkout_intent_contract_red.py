from sqlalchemy import CheckConstraint, UniqueConstraint, event

from app import models


def test_mei_competencia_checkout_intent_is_vertical_and_provider_agnostic():
    assert hasattr(models, "MeiCompetenciaCheckoutIntent")

    model = models.MeiCompetenciaCheckoutIntent
    table = model.__table__

    assert table.name == "mei_competencia_checkout_intents"

    assert set(table.columns.keys()) == {
        "id",
        "checkout_idempotency_key",
        "user_id",
        "empresa_id",
        "competencia",
        "capability",
        "offer_code",
        "created_at",
    }

    assert "ordem_id" not in table.columns
    assert "grant_id" not in table.columns
    assert "payment_id" not in table.columns
    assert "provider_order_id" not in table.columns

    assert {fk.target_fullname for fk in table.c.user_id.foreign_keys} == {
        "usuarios.id"
    }
    assert {fk.target_fullname for fk in table.c.empresa_id.foreign_keys} == {
        "empresas.id"
    }

    uniques = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("checkout_idempotency_key",) in uniques


def test_mei_competencia_checkout_intent_freezes_valid_yyyymm_and_capability():
    table = models.MeiCompetenciaCheckoutIntent.__table__

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
    assert "capability = 'mei.das'" in checks


def test_mei_competencia_checkout_intent_is_append_only_in_orm():
    model = models.MeiCompetenciaCheckoutIntent

    guard = getattr(
        models,
        "_reject_mei_competencia_checkout_intent_mutation",
        None,
    )

    assert guard is not None
    assert event.contains(model, "before_update", guard)
    assert event.contains(model, "before_delete", guard)
