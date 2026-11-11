"""
enterprise_b03_item_reconciliation.py

Orquestrador fino do B03 (comparacao monetaria: XML vs calculo independente),
POR DOCUMENTO -- nao por item. Reescrito apos leitura real do corpo de
TaxConsistencyEngine.verificar_consistencia (2026-11-11): o contrato real
compara duas listas inteiras (itens do XML vs itens_calculados do motor)
de uma vez, por indice+NCM+CFOP, nao item a item.

Liga 3 modulos ja confirmados, SEM reimplementar nenhum:
  - app/services/fiscal_utils.py::resolver_aliquota_e_mva      (resolver_regra)
  - app/motor_fiscal.py::MotorFiscal                            (calculo puro)
  - app/services/tax_consistency/tax_consistency_engine.py::TaxConsistencyEngine
                                                                 (comparacao)

IMPORTANTE -- autoridade_fiscal e SEMPRE False no retorno de
verificar_consistencia, mesmo com coincidencia numerica perfeita (a lista
itens_calculados e fornecida externamente e podia ser forjada). B03 NUNCA
reinterpreta isto como prova legal -- o resultado e sempre um diagnostico
interno "sem autoridade", nunca uma certificacao.

Apenas verificar_consistencia esta implementado de facto; verificar_icms_st,
verificar_mva e verificar_base_st sao stubs (sempre NAO_AVALIADO) -- B03 nao
os chama.

Ver docs/B03_FASE2_DESENHO.md (a atualizar) e docs/B03_GOVERNANCE_LEVEL.md.

RESOLVIDO (2026-11-11): a entrada real NAO vem de xml_fiscal_adapter (esse
so devolve metadados do DOCUMENTO -- chave, CNPJs, protocolo -- nenhum dado
por item). A fonte real e app/xml_service.py::ler_xml_unico, cujo
dados['itens'] ja tem EXATAMENTE os campos que confrontar_documento_b03
espera (ncm, cfop, valor_produto, base_st, valor_st, st_observado_xml) --
so que como strings (nunca convertidas). confrontar_xml_b03() abaixo faz
essa ponte, reaproveitando _parse_float/_parse_data_emissao ja existentes
em xml_service.py (nao reimplementados aqui).
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

from app.services.fiscal_utils import resolver_aliquota_e_mva
from app.motor_fiscal import MotorFiscal
from app.services.tax_consistency.tax_consistency_engine import TaxConsistencyEngine
from app.xml_service import ler_xml_unico, _parse_float, _parse_data_emissao

SCHEMA = "SOLVERIS_ENTERPRISE_B03_ITEM_RECONCILIATION_V2"


def _money_hash(valor: Any) -> str:
    return hashlib.sha256(repr(valor).encode("utf-8")).hexdigest()


def _log_auditoria_leve(
    *, quem_rodou: str, hash_xml_entrada: str, hash_resultado: str,
    modulos_usados: list[str],
) -> dict:
    """Fase 1 (B03_GOVERNANCE_LEVEL.md): log de aplicacao simples, sem
    tabela append-only/trigger."""
    return {
        "quem_rodou": quem_rodou,
        "quando": datetime.now(timezone.utc).isoformat(),
        "hash_xml_entrada": hash_xml_entrada,
        "hash_resultado": hash_resultado,
        "modulos_usados": modulos_usados,
    }


def confrontar_documento_b03(
    *,
    db,
    chave_nfe: str,
    itens_xml: list[dict],
    uf_operacao: str,
    data_operacao: date,
    xml_bytes: bytes,
    quem_rodou: str = "sistema",
) -> dict:
    """
    Orquestra a comparacao de UM DOCUMENTO inteiro (todos os itens de uma vez,
    conforme o contrato real de verificar_consistencia).

    itens_xml: lista de dicts, um por item do XML, na ORDEM dos itens do
        documento (o indice 1-based e atribuido pela posicao na lista).
        Cada item precisa de, no minimo:
          {'ncm': str, 'cfop': str, 'st_observado_xml': bool,
           'valor_st': <num ou None>, 'base_st': <num ou None>,
           'valor_produto': <num>}  # valor_produto so para o calculo do motor
        Itens com st_observado_xml=False/ausente sao aceites pelo motor de
        consistencia mas ficam em 'motivos_pendentes', nunca em divergencia.

    Retorna dict com schema_version e:
      'estado': 'SEM_DIVERGENCIA' | 'DIVERGENCIA_ENCONTRADA' | 'NAO_AVALIADO'
      'autoridade_fiscal': sempre False (herdado do motor -- nunca prova legal)
      'resultado_bruto': o dict completo que o motor devolveu (proveniencia)
    """
    modulos_usados = [
        "app.services.fiscal_utils.resolver_aliquota_e_mva",
        "app.motor_fiscal.MotorFiscal",
        "app.services.tax_consistency.tax_consistency_engine.TaxConsistencyEngine",
    ]
    hash_xml_entrada = hashlib.sha256(xml_bytes).hexdigest()

    # Fail-closed: sem estes 3 campos nao ha como resolver regra nem montar
    # o resultado -- NUNCA prosseguir e deixar explodir mais tarde (ex.
    # data_operacao.isoformat() com None). Retorna NAO_AVALIADO com o motivo
    # exato, mesma filosofia de _bloqueio() em fiscal_utils.py.
    campos_ausentes = [
        nome for nome, valor in (
            ("chave_nfe", chave_nfe), ("uf_operacao", uf_operacao),
            ("data_operacao", data_operacao),
        ) if valor is None
    ]
    if campos_ausentes:
        resultado = {
            "schema_version": SCHEMA,
            "estado": "NAO_AVALIADO",
            "autoridade_fiscal": False,
            "motivo": f"CAMPOS_ESSENCIAIS_AUSENTES: {', '.join(campos_ausentes)}",
            "chave_nfe": chave_nfe,
            "uf_operacao": uf_operacao,
            "data_operacao": data_operacao.isoformat() if data_operacao else None,
        }
        resultado["_auditoria"] = _log_auditoria_leve(
            quem_rodou=quem_rodou, hash_xml_entrada=hash_xml_entrada,
            hash_resultado=_money_hash(resultado), modulos_usados=modulos_usados,
        )
        return resultado

    itens_calculados: list[dict] = []
    blocos_normativos: list[dict] = []  # auditoria paralela, fora do contrato do engine
    motor = MotorFiscal()

    for indice, item in enumerate(itens_xml, start=1):
        ncm = item["ncm"]
        cfop = item["cfop"]

        # --- resolver regra (ja existe, nao reimplementar) ---
        regra = resolver_aliquota_e_mva(db, uf_operacao, ncm, data_operacao)

        if not regra["calculo_autorizado"]:
            # Sem autoridade normativa: NAO inventar valor calculado. None e
            # tratado por _moeda() do engine como "nao comprovado" -- fica
            # em motivos_pendentes, nunca vira divergencia nem falso-sucesso.
            itens_calculados.append({
                "indice_item": indice,
                "ncm": ncm,
                "cfop": cfop,
                "valor_st_calculado": None,
                "base_st_calculada": None,
            })
            blocos_normativos.append({
                "indice_item": indice,
                "motivo_bloqueio": regra.get("motivo_bloqueio"),
                "aviso": regra.get("aviso"),
            })
            continue

        if item.get("valor_produto") is None:
            # Fail-closed: sem valor_produto valido nao se chama o motor
            # (nunca calcular com None/adivinhar) -- fica como bloqueio,
            # igual a quando falta autoridade normativa.
            itens_calculados.append({
                "indice_item": indice, "ncm": ncm, "cfop": cfop,
                "valor_st_calculado": None, "base_st_calculada": None,
            })
            blocos_normativos.append({
                "indice_item": indice,
                "motivo_bloqueio": "valor_produto_ausente_ou_invalido",
                "aviso": None,
            })
            continue

        # --- calcular independentemente (funcoes puras, ja existem) ---
        base_st = motor.calcular_base_st(item["valor_produto"], regra["mva"])
        icms_proprio = motor.calcular_icms_proprio(item["valor_produto"], regra["aliquota"])
        icms_st = motor.calcular_icms_st(base_st, regra["aliquota"], icms_proprio)

        itens_calculados.append({
            "indice_item": indice,
            "ncm": ncm,
            "cfop": cfop,
            "valor_st_calculado": icms_st,
            "base_st_calculada": base_st,
        })

    dados_xml = {"chave_nfe": chave_nfe, "itens": itens_xml}
    dados_motor = {"chave_nfe": chave_nfe, "itens_calculados": itens_calculados, "erro": None}

    # --- comparar (ja existe, nao reimplementar) ---
    engine = TaxConsistencyEngine()
    bruto = engine.verificar_consistencia(dados_xml, dados_motor)

    if bruto["estado"] == "NAO_AVALIADO":
        estado_b03 = "NAO_AVALIADO"
    elif bruto.get("divergencias"):
        estado_b03 = "DIVERGENCIA_ENCONTRADA"
    else:
        estado_b03 = "SEM_DIVERGENCIA"

    resultado = {
        "schema_version": SCHEMA,
        "estado": estado_b03,
        "autoridade_fiscal": False,  # NUNCA reinterpretar como prova legal
        "chave_nfe": chave_nfe,
        "uf_operacao": uf_operacao,
        "data_operacao": data_operacao.isoformat(),
        "blocos_normativos": blocos_normativos,
        "resultado_bruto": bruto,
    }
    resultado["_auditoria"] = _log_auditoria_leve(
        quem_rodou=quem_rodou,
        hash_xml_entrada=hash_xml_entrada,
        hash_resultado=_money_hash(resultado),
        modulos_usados=modulos_usados,
    )
    return resultado


def confrontar_xml_b03(*, db, xml_bytes: bytes, quem_rodou: str = "sistema") -> dict:
    """
    Ponto de entrada real (Fase 3): recebe XML bruto, parseia via
    ler_xml_unico (ja existe, nao reimplementar), converte os campos
    textuais para os tipos que confrontar_documento_b03 e MotorFiscal
    esperam (usando _parse_float/_parse_data_emissao ja existentes em
    xml_service.py), e delega a comparacao real.

    Erro de parsing do XML (ler_xml_unico pode levantar excecao -- nao
    engole silenciosamente, nunca prossegue com dados parciais como se
    fossem completos).
    """
    try:
        dados = ler_xml_unico(xml_bytes=xml_bytes)
    except Exception as exc:
        return {
            "schema_version": SCHEMA,
            "estado": "NAO_AVALIADO",
            "autoridade_fiscal": False,
            "motivo": f"ERRO_PARSE_XML: {exc}",
        }

    chave_nfe = dados.get("chave_nfe")
    uf_operacao = dados.get("uf_dest") or dados.get("uf_emit")
    data_operacao = _parse_data_emissao(dados.get("data_emissao"))

    itens_xml = []
    for item in dados.get("itens", []):
        item_convertido = dict(item)  # nao mutar o dict original de ler_xml_unico
        valor_produto_raw = item.get("valor_produto")
        item_convertido["valor_produto"] = (
            _parse_float(valor_produto_raw) if valor_produto_raw else None
        )
        itens_xml.append(item_convertido)

    return confrontar_documento_b03(
        db=db,
        chave_nfe=chave_nfe,
        itens_xml=itens_xml,
        uf_operacao=uf_operacao,
        data_operacao=data_operacao,
        xml_bytes=xml_bytes,
        quem_rodou=quem_rodou,
    )
