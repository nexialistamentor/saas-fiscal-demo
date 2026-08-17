import app.schemas.source_authority_schema as schema


def test_normative_dataset_binding_item_represents_dataset_without_constante_id():
    model = getattr(schema, "NormativeDatasetBindingItem", None)

    assert model is not None, (
        "schema normativo ainda nao representa datasets como artefato proprio"
    )

    item = model(
        dataset_id="MEI_ANEXO_XI_OCUPACOES_V1",
        fonte_id="CGSN-ANEXO-XI-001",
        versao_fonte="CGSN140-ANEXOXI-R182",
        vigencia_inicio="2025-10-01",
        vigencia_fim=None,
        jurisdicao_codigo="BR",
        risco="critico",
        invariantes=("INV_DATASET_NORMATIVO_001",),
    )

    assert item.dataset_id == "MEI_ANEXO_XI_OCUPACOES_V1"
    assert not hasattr(item, "constante_id")



def test_normative_binding_batch_accepts_dataset_binding_item():
    item = schema.NormativeDatasetBindingItem(
        dataset_id="MEI_ANEXO_XI_OCUPACOES_V1",
        fonte_id="CGSN-ANEXO-XI-001",
        versao_fonte="CGSN140-ANEXOXI-R182",
        vigencia_inicio="2025-10-01",
        vigencia_fim=None,
        jurisdicao_codigo="BR",
        risco="critico",
        invariantes=("INV_DATASET_NORMATIVO_001",),
    )

    contexto = schema.NormativeBindingContext(
        data_referencia="2026-08-17",
        jurisdicao_codigo="BR",
        uso_solicitado="diagnostico",
    )

    batch = schema.NormativeBindingBatchRequest(
        contexto=contexto,
        bindings=(item,),
    )

    assert batch.bindings == (item,)



def test_source_authority_guard_accepts_structurally_valid_dataset_binding(
    monkeypatch,
):
    import app.services.source_authority_guard as guard

    source = {
        "id": "CGSN-ANEXO-XI-001",
        "tipo": "normativa_oficial",
        "nome": "Anexo XI da Resolucao CGSN 140/2018",
        "pode_fundamentar_decisao": True,
        "pode_validar_fato_operacional": False,
        "pode_ser_usada_por_llm": False,
        "versao": "CGSN140-ANEXOXI-R182",
        "vigencia_inicio": "2025-10-01",
        "vigencia_fim": None,
        "jurisdicao": "BR",
        "risco_se_desatualizada": "critico",
        "hash_referencia": "a" * 64,
    }

    monkeypatch.setattr(
        guard,
        "_carregar_manifest",
        lambda: {source["id"]: source},
    )

    payload = {
        "contexto": {
            "data_referencia": "2026-08-17",
            "jurisdicao_codigo": "BR",
            "uso_solicitado": "diagnostico",
        },
        "bindings": [
            {
                "dataset_id": "MEI_ANEXO_XI_OCUPACOES_V1",
                "fonte_id": "CGSN-ANEXO-XI-001",
                "versao_fonte": "CGSN140-ANEXOXI-R182",
                "vigencia_inicio": "2025-10-01",
                "vigencia_fim": None,
                "jurisdicao_codigo": "BR",
                "risco": "critico",
                "invariantes": ["INV_DATASET_NORMATIVO_001"],
            }
        ],
    }

    result = guard.validar_bindings_normativos(payload)

    assert (
        result.status
        == schema.NormativeBindingStatus.valido_com_autoridade_decisoria
    )
    assert result.autorizado_fundamentar_decisao is True
    assert result.reasons == ()
    assert result.bindings_validados == 1



def test_source_authority_guard_rejects_binding_with_constant_and_dataset_targets(
    monkeypatch,
):
    import app.services.source_authority_guard as guard

    source = {
        "id": "CGSN-ANEXO-XI-001",
        "tipo": "normativa_oficial",
        "nome": "Anexo XI da Resolucao CGSN 140/2018",
        "pode_fundamentar_decisao": True,
        "pode_validar_fato_operacional": False,
        "pode_ser_usada_por_llm": False,
        "versao": "CGSN140-ANEXOXI-R182",
        "vigencia_inicio": "2025-10-01",
        "vigencia_fim": None,
        "jurisdicao": "BR",
        "risco_se_desatualizada": "critico",
        "hash_referencia": "a" * 64,
    }

    monkeypatch.setattr(
        guard,
        "_carregar_manifest",
        lambda: {source["id"]: source},
    )

    payload = {
        "contexto": {
            "data_referencia": "2026-08-17",
            "jurisdicao_codigo": "BR",
            "uso_solicitado": "diagnostico",
        },
        "bindings": [
            {
                "constante_id": "CONST_001",
                "dataset_id": "MEI_ANEXO_XI_OCUPACOES_V1",
                "fonte_id": "CGSN-ANEXO-XI-001",
                "versao_fonte": "CGSN140-ANEXOXI-R182",
                "vigencia_inicio": "2025-10-01",
                "vigencia_fim": None,
                "jurisdicao_codigo": "BR",
                "risco": "critico",
                "invariantes": ["INV_DATASET_NORMATIVO_001"],
            }
        ],
    }

    result = guard.validar_bindings_normativos(payload)

    assert result.status == schema.NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code.value, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        ("ALVO_NORMATIVO_AMBIGUO", 0, "constante_id|dataset_id"),
    ]
    assert result.bindings_validados == 0



def test_source_authority_guard_rejects_binding_without_normative_target(
    monkeypatch,
):
    import app.services.source_authority_guard as guard

    source = {
        "id": "CGSN-ANEXO-XI-001",
        "tipo": "normativa_oficial",
        "nome": "Anexo XI da Resolucao CGSN 140/2018",
        "pode_fundamentar_decisao": True,
        "pode_validar_fato_operacional": False,
        "pode_ser_usada_por_llm": False,
        "versao": "CGSN140-ANEXOXI-R182",
        "vigencia_inicio": "2025-10-01",
        "vigencia_fim": None,
        "jurisdicao": "BR",
        "risco_se_desatualizada": "critico",
        "hash_referencia": "a" * 64,
    }

    monkeypatch.setattr(
        guard,
        "_carregar_manifest",
        lambda: {source["id"]: source},
    )

    payload = {
        "contexto": {
            "data_referencia": "2026-08-17",
            "jurisdicao_codigo": "BR",
            "uso_solicitado": "diagnostico",
        },
        "bindings": [
            {
                "fonte_id": "CGSN-ANEXO-XI-001",
                "versao_fonte": "CGSN140-ANEXOXI-R182",
                "vigencia_inicio": "2025-10-01",
                "vigencia_fim": None,
                "jurisdicao_codigo": "BR",
                "risco": "critico",
                "invariantes": ["INV_DATASET_NORMATIVO_001"],
            }
        ],
    }

    result = guard.validar_bindings_normativos(payload)

    assert result.status == schema.NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code.value, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        ("ALVO_NORMATIVO_AUSENTE", 0, "constante_id|dataset_id"),
    ]
    assert result.bindings_validados == 0
