"""F8 — contrato HTTP soberano para GET /relatorio/{relatorio_id}."""

import copy
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.sql import operators

from app.database import get_db
from app.main import app
from app.models import Empresa, RelatorioAnalise, User
from app.security import get_usuario_atual


_events = []


class _ObservedEntity(SimpleNamespace):
    _observed_reads = {
        "relatorio": {"user_id", "pago"},
        "usuario": {"id", "consulta_paga"},
    }

    def __getattribute__(self, name):
        value = super().__getattribute__(name)
        kind = super().__getattribute__("_kind")
        if name in type(self)._observed_reads.get(kind, set()):
            _events.append(("read", kind, name))
        return value


class _QueryFake:
    def __init__(self, db, model, entities):
        self._db = db
        self.model = model
        self._entities = entities
        self.criteria = []
        self.filter_called = False
        self.first_called = False

    def filter(self, *criteria, **_kwargs):
        self.filter_called = True
        self.criteria.extend(criteria)
        _events.append(("filter", self.model))
        return self

    def first(self):
        self.first_called = True
        _events.append(("first", self.model))
        if self._entities is None or not self.criteria:
            return None
        for entity in self._entities:
            if all(self._matches(entity, criterion) for criterion in self.criteria):
                return entity
        return None

    @staticmethod
    def _matches(entity, criterion):
        left = getattr(criterion, "left", None)
        right = getattr(criterion, "right", None)
        column_name = getattr(left, "key", None)
        if (
            getattr(criterion, "operator", None) is not operators.eq
            or column_name is None
            or not hasattr(right, "value")
            or not hasattr(entity, column_name)
        ):
            return False
        return getattr(entity, column_name) == right.value


class _DBFake:
    def __init__(self, *, relatorios, empresas):
        self._collections = {
            RelatorioAnalise: list(relatorios),
            Empresa: list(empresas),
        }
        self.queries = []

    @property
    def query_count(self):
        return len(self.queries)

    @property
    def query_models(self):
        return [query.model for query in self.queries]

    @property
    def criteria_by_query(self):
        return [list(query.criteria) for query in self.queries]

    def query(self, model, *_args, **_kwargs):
        _events.append(("query", model))
        query = _QueryFake(self, model, self._collections.get(model))
        self.queries.append(query)
        return query

    def _reject_mutation(self, *_args, **_kwargs):
        raise AssertionError("A rota GET não pode executar mutações")

    add = _reject_mutation
    delete = _reject_mutation
    flush = _reject_mutation
    commit = _reject_mutation
    rollback = _reject_mutation
    execute = _reject_mutation
    bulk_save_objects = _reject_mutation


_db_state = None


def _override_db(*, relatorios=(), empresas=()):
    def _inner():
        global _db_state
        _db_state = _DBFake(relatorios=relatorios, empresas=empresas)
        yield _db_state

    return _inner


def _mock_user(user_id=1, consulta_paga=False):
    return _ObservedEntity(
        _kind="usuario",
        id=user_id,
        consulta_paga=consulta_paga,
    )


def _make_rel(
    *,
    user_id=1,
    empresa_id=10,
    pago=True,
    resultado_json=None,
):
    return _ObservedEntity(
        _kind="relatorio",
        id=1,
        user_id=user_id,
        empresa_id=empresa_id,
        status="ok",
        analysis_type="empresa_tax",
        score_resultante=85.0,
        total_alertas=2,
        pago=pago,
        created_at=datetime(2026, 1, 15, 10, 0, 0),
        resultado_json={} if resultado_json is None else resultado_json,
    )


def _make_empresa(*, empresa_id=10, user_id=1):
    return SimpleNamespace(id=empresa_id, user_id=user_id)


def _request(*, relatorios=(), empresas=(), usuario=None, real_auth=False):
    global _db_state
    _db_state = None
    _events.clear()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = _override_db(
        relatorios=relatorios,
        empresas=empresas,
    )
    if not real_auth:
        app.dependency_overrides[get_usuario_atual] = lambda: usuario
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.get("/relatorio/1")
    finally:
        app.dependency_overrides.clear()


def _assert_query(query, model, expected_values):
    assert query.model is model
    assert query.filter_called is True
    assert query.first_called is True
    assert len(query.criteria) == len(expected_values)
    assert [criterion.left.key for criterion in query.criteria] == list(expected_values)
    assert [criterion.right.value for criterion in query.criteria] == list(
        expected_values.values()
    )


def _assert_relatorio_query(relatorio_id=1):
    assert _db_state is not None
    assert _db_state.query_count >= 1
    _assert_query(_db_state.queries[0], RelatorioAnalise, {"id": relatorio_id})


def _assert_read_order(*models):
    assert _db_state.query_models == list(models)
    database_events = [event for event in _events if event[0] != "read"]
    assert database_events == [
        event
        for model in models
        for event in (("query", model), ("filter", model), ("first", model))
    ]


def _financial_reads():
    return [
        event
        for event in _events
        if event in {
            ("read", "relatorio", "pago"),
            ("read", "usuario", "consulta_paga"),
        }
    ]


def _assert_payment_after_direct_authorization():
    first_payment = min(
        index
        for index, event in enumerate(_events)
        if event in _financial_reads()
    )
    assert _events.index(("read", "relatorio", "user_id")) < first_payment
    assert _events.index(("read", "usuario", "id")) < first_payment


def _assert_payment_after_empresa_authorization():
    first_payment = min(
        index
        for index, event in enumerate(_events)
        if event in _financial_reads()
    )
    assert _events.index(("first", Empresa)) < first_payment


def _success_payload(*, pago, extras=None):
    return {
        **(extras or {}),
        "relatorio_id": 1,
        "empresa_id": 10,
        "status": "ok",
        "analysis_type": "empresa_tax",
        "score_resultante": 85.0,
        "total_alertas": 2,
        "pago": pago,
        "criado_em": "2026-01-15T10:00:00",
    }


def test_fake_separa_modelos_avalia_igualdade_e_falha_fechado():
    rel = _make_rel()
    empresa = _make_empresa()
    db = _DBFake(relatorios=[rel], empresas=[empresa])

    assert db.query(RelatorioAnalise).filter(RelatorioAnalise.id == 1).first() is rel
    assert db.query(Empresa).filter(
        Empresa.id == 10,
        Empresa.user_id == 1,
    ).first() is empresa
    assert db.query(RelatorioAnalise).filter(RelatorioAnalise.id == 999).first() is None
    assert db.query(User).filter(User.id == 1).first() is None
    assert db.query(RelatorioAnalise).filter(RelatorioAnalise.id > 0).first() is None
    assert db.query(RelatorioAnalise).filter(object()).first() is None


def test_f8_1_sem_token_retorna_401_sem_consultar_relatorio():
    response = _request(real_auth=True)

    assert response.status_code == 401
    assert _db_state is not None
    assert RelatorioAnalise not in _db_state.query_models


def test_f8_2_relatorio_inexistente_retorna_404():
    response = _request(usuario=_mock_user())

    assert response.status_code == 404
    assert response.json() == {"detail": "Relatório não encontrado"}
    _assert_relatorio_query()
    _assert_read_order(RelatorioAnalise)


def test_f8_3_proprietario_com_pagamento_individual_retorna_payload_completo():
    rel = _make_rel(
        pago=True,
        resultado_json={"oportunidades": [{"ncm": "12345678"}]},
    )
    before = copy.deepcopy(vars(rel))

    response = _request(relatorios=[rel], usuario=_mock_user(consulta_paga=False))

    assert response.status_code == 200
    assert response.json() == _success_payload(
        pago=True,
        extras={"oportunidades": [{"ncm": "12345678"}]},
    )
    assert vars(rel) == before
    assert hasattr(rel, "created_at")
    assert not hasattr(rel, "criado_em")
    _assert_relatorio_query()
    _assert_read_order(RelatorioAnalise)
    assert _financial_reads()
    _assert_payment_after_direct_authorization()


def test_f8_4_proprietario_com_entitlement_legado_retorna_pago_real_do_relatorio():
    rel = _make_rel(pago=False)

    response = _request(relatorios=[rel], usuario=_mock_user(consulta_paga=True))

    assert response.status_code == 200
    assert response.json() == _success_payload(pago=False)
    _assert_relatorio_query()
    _assert_read_order(RelatorioAnalise)
    assert _financial_reads()
    _assert_payment_after_direct_authorization()


def test_f8_5_pagamento_ausente_retorna_402_sem_mutacao():
    rel = _make_rel(pago=False)
    before = copy.deepcopy(vars(rel))

    response = _request(
        relatorios=[rel],
        usuario=_mock_user(consulta_paga=False),
    )

    assert response.status_code == 402
    assert response.json() == {"detail": "Pagamento necessário"}
    assert vars(rel) == before
    _assert_relatorio_query()
    _assert_read_order(RelatorioAnalise)
    assert _financial_reads()
    _assert_payment_after_direct_authorization()


def test_f8_6_vinculo_empresarial_legitimo_retorna_200():
    rel = _make_rel(user_id=99, pago=True)
    empresa = _make_empresa(user_id=1)
    rel_before = copy.deepcopy(vars(rel))
    empresa_before = copy.deepcopy(vars(empresa))

    response = _request(
        relatorios=[rel],
        empresas=[empresa],
        usuario=_mock_user(user_id=1),
    )

    assert response.status_code == 200
    assert response.json() == _success_payload(pago=True)
    assert vars(rel) == rel_before
    assert vars(empresa) == empresa_before
    _assert_relatorio_query()
    assert _db_state.query_count == 2
    _assert_query(_db_state.queries[1], Empresa, {"id": 10, "user_id": 1})
    _assert_read_order(RelatorioAnalise, Empresa)
    assert _financial_reads()
    _assert_payment_after_empresa_authorization()


def test_f8_7_empresa_de_outro_utilizador_retorna_403_apos_autorizacao():
    rel = _make_rel(user_id=99, pago=True)
    empresa = _make_empresa(user_id=88)
    rel_before = copy.deepcopy(vars(rel))
    empresa_before = copy.deepcopy(vars(empresa))

    response = _request(
        relatorios=[rel],
        empresas=[empresa],
        usuario=_mock_user(user_id=1, consulta_paga=False),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Acesso negado: empresa não pertence ao usuário"
    }
    assert vars(rel) == rel_before
    assert vars(empresa) == empresa_before
    _assert_relatorio_query()
    assert _db_state.query_count == 2
    _assert_query(_db_state.queries[1], Empresa, {"id": 10, "user_id": 1})
    _assert_read_order(RelatorioAnalise, Empresa)
    assert _financial_reads() == []


def test_f8_8_relatorio_alheio_sem_empresa_retorna_403():
    rel = _make_rel(user_id=99, empresa_id=None, pago=True)
    before = copy.deepcopy(vars(rel))

    response = _request(
        relatorios=[rel],
        usuario=_mock_user(user_id=1, consulta_paga=False),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Acesso negado ao relatório"}
    assert vars(rel) == before
    _assert_relatorio_query()
    _assert_read_order(RelatorioAnalise)
    assert _financial_reads() == []


def test_f8_9_created_at_do_modelo_e_exposto_como_criado_em():
    rel = _make_rel(pago=True)

    response = _request(
        relatorios=[rel],
        usuario=_mock_user(user_id=1, consulta_paga=True),
    )

    assert hasattr(rel, "created_at")
    assert not hasattr(rel, "criado_em")
    assert response.status_code == 200
    assert response.json() == _success_payload(pago=True)
    _assert_relatorio_query()
    _assert_read_order(RelatorioAnalise)
    assert _financial_reads()
    _assert_payment_after_direct_authorization()
