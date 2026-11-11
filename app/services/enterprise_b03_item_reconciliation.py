"""
enterprise_b03_item_reconciliation.py

Orquestrador fino do B03 (comparacao monetaria: XML vs valores declarados vs
calculo independente). NAO reimplementa resolucao de regra, calculo numerico
nem comparacao de consistencia -- liga 3 modulos ja confirmados:

  - app/services/fiscal_utils.py::resolver_aliquota_e_mva      (resolver_regra)
  - app/motor_fiscal.py::MotorFiscal                            (calculo puro)
  - app/services/tax_consistency/tax_consistency_engine.py::TaxConsistencyEngine
                                                                 (comparacao)

Padrao de orquestracao copiado de enterprise_g12_st_item_reconciliation.py
(dict + schema_version, nunca dataclass -- consistencia com o resto do
codigo real, nao com o plano teorico).

Ver docs/B03_FASE2_DESENHO.md para o desenho completo e
docs/B03_GOVERNANCE_LEVEL.md para o nivel de governanca (git+testes+log leve,
sem cadeia politica->ativacao->assinatura).
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

from app.services.fiscal_utils import resolver_aliquota_e_mva
from app.motor_fiscal import MotorFiscal
from app.services.tax_consistency.tax_consistency_engine import TaxConsistencyEngine

SCHEMA = "SOLVERIS_ENTERPRISE_B03_ITEM_RECONCILIATION_V1"


def _money_hash(valor: Any) -> str:
    """Hash estavel de um valor monetario/numerico para proveniencia."""
    return hashlib.sha256(repr(valor).encode("utf-8")).hexdigest()


def _log_auditoria_leve(
    *,
    quem_rodou: str,
    hash_xml_entrada: str,
    hash_resultado: str,
    modulos_usados: list[str],
) -> dict:
    """
    Fase 1 (B03_GOVERNANCE_LEVEL.md) decidiu log de aplicacao simples, SEM
    tabela append-only/trigger como no B02. Este dict e o registo; o caller
    decide onde persistir (ficheiro de log, tabela simples sem triggers).
    """
    return {
        "quem_rodou": quem_rodou,
        "quando": datetime.now(timezone.utc).isoformat(),
        "hash_xml_entrada": hash_xml_entrada,
        "hash_resultado": hash_resultado,
        "modulos_usados": modulos_usados,
    }


def confrontar_item_b03(
    *,
    db,
    xml_item: dict,
    uf_operacao: str,
    ncm: str,
    data_operacao: date,
    valor_produto: float,
    xml_bytes: bytes,
    quem_rodou: str = "sistema",
) -> dict:
    """
    Funcao de orquestracao do B03 para um unico item.

    xml_item: dict com os valores DECLARADOS no XML para este item
        (esperado: pelo menos 'base_st', 'icms_st' -- os nomes de campo
        devem bater com o que TaxConsistencyEngine.verificar_consistencia
        espera em dados_xml; A CONFIRMAR por leitura do corpo real antes de
        usar em producao -- ver nota no fim do ficheiro).

    Retorna dict com schema_version e um dos tres estados:
      - 'SEM_DIVERGENCIA'            (calculo autorizado, valores batem)
      - 'DIVERGENCIA_ENCONTRADA'     (calculo autorizado, valores NAO batem)
      - 'COBERTURA_NAO_COMPROVADA'   (sem autoridade normativa suficiente)
    """
    modulos_usados = [
        "app.services.fiscal_utils.resolver_aliquota_e_mva",
        "app.motor_fiscal.MotorFiscal",
    ]
    hash_xml_entrada = hashlib.sha256(xml_bytes).hexdigest()

    # --- Passo 1: resolver regra (ja existe, nao reimplementar) ---
    regra = resolver_aliquota_e_mva(db, uf_operacao, ncm, data_operacao)

    if not regra["calculo_autorizado"]:
        resultado = {
            "schema_version": SCHEMA,
            "estado": "COBERTURA_NAO_COMPROVADA",
            "motivo_bloqueio": regra.get("motivo_bloqueio"),
            "aviso": regra.get("aviso"),
            "uf": uf_operacao,
            "ncm": ncm,
            "data_operacao": data_operacao.isoformat(),
        }
        resultado["_auditoria"] = _log_auditoria_leve(
            quem_rodou=quem_rodou,
            hash_xml_entrada=hash_xml_entrada,
            hash_resultado=_money_hash(resultado),
            modulos_usados=modulos_usados,
        )
        return resultado

    # --- Passo 2: calcular independentemente (funcoes puras, ja existem) ---
    motor = MotorFiscal()
    base_st_calculado = motor.calcular_base_st(valor_produto, regra["mva"])
    icms_proprio_calculado = motor.calcular_icms_proprio(valor_produto, regra["aliquota"])
    icms_st_calculado = motor.calcular_icms_st(
        base_st_calculado, regra["aliquota"], icms_proprio_calculado
    )

    dados_motor = {
        "base_st": base_st_calculado,
        "icms_st": icms_st_calculado,
        "icms_proprio": icms_proprio_calculado,
        "aliquota": regra["aliquota"],
        "mva": regra["mva"],
    }

    # --- Passo 3: comparar (ja existe, nao reimplementar) ---
    # NOTA: assinatura confirmada (self, dados_xml, dados_motor); o FORMATO
    # EXATO do retorno de verificar_consistencia (bool? dict com chaves
    # especificas?) ainda NAO foi lido por inteiro -- este bloco assume um
    # dict com pelo menos uma chave booleana indicando consistencia, mas
    # ISTO E UMA SUPOSICAO A CONFIRMAR antes de usar em producao (ver nota
    # no fim do ficheiro). Nao mudar este comentario para "confirmado" sem
    # ler o corpo real primeiro.
    motor_engine = TaxConsistencyEngine()
    comparacao = motor_engine.verificar_consistencia(
        dados_xml=xml_item,
        dados_motor=dados_motor,
    )

    modulos_usados.append(
        "app.services.tax_consistency.tax_consistency_engine.TaxConsistencyEngine"
    )

    resultado = {
        "schema_version": SCHEMA,
        "estado": "DIVERGENCIA_ENCONTRADA" if _indica_divergencia(comparacao) else "SEM_DIVERGENCIA",
        "uf": uf_operacao,
        "ncm": ncm,
        "data_operacao": data_operacao.isoformat(),
        "valores_declarados": xml_item,
        "valores_calculados": dados_motor,
        "comparacao_bruta": comparacao,
        "fonte_legal": regra.get("fonte_legal"),
        "confianca": regra.get("confianca"),
    }
    resultado["_auditoria"] = _log_auditoria_leve(
        quem_rodou=quem_rodou,
        hash_xml_entrada=hash_xml_entrada,
        hash_resultado=_money_hash(resultado),
        modulos_usados=modulos_usados,
    )
    return resultado


def _indica_divergencia(comparacao: Any) -> bool:
    """
    PLACEHOLDER -- depende do formato real de retorno de
    TaxConsistencyEngine.verificar_consistencia, ainda nao lido por inteiro.
    NAO USAR EM PRODUCAO sem antes rodar:
        python tools/mostrar_corpo_funcao.py \
            --ficheiro app/services/tax_consistency/tax_consistency_engine.py \
            --funcao verificar_consistencia
    e corrigir esta funcao para o formato real (bool direto, dict com chave
    especifica, lista de inconsistencias, etc.).
    """
    if isinstance(comparacao, bool):
        return not comparacao
    if isinstance(comparacao, dict):
        return bool(
            comparacao.get("divergente")
            or comparacao.get("inconsistente")
            or (comparacao.get("consistente") is False)
        )
    raise NotImplementedError(
        "Formato de retorno de verificar_consistencia nao reconhecido -- "
        "ler o corpo real antes de prosseguir (ver docstring desta funcao)."
    )
