"""
Serviço central de registro de execução de análise.

Conecta Motor Fiscal, Engines, Agentes e Score ao container relatorios_analise.
Cada execução vira um registro completo auditável.
"""

import logging
import time
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.models import Empresa, RelatorioAnalise, AlertaFiscal, DocumentoFiscal
from app.services.analysis_orchestrator import executar_analise_xml
from app.services.resultado_empresarial_service import compor_resultado_empresarial
from app.xml_service import DuplicataFiscalError, processar_e_persistir_xml
from app.services.score_global_tributario_service import calcular_score_global_tributario
from app.services.usage_service import verificar_limite_analises, incrementar_uso_analise
from app.services.resultado_provenance_service import (
    fingerprint_resultado_json,
    selar_resultado_nao_mei,
)

from app.services.enterprise_xml_evidence_binding import (
    construir_vinculo_documento_relatorio,
)

logger = logging.getLogger(__name__)


def criar_registro_analise(
    db,
    user_id: int,
    analysis_type: str,
    empresa_id: int | None = None,
    xml_chave: str | None = None,
) -> RelatorioAnalise:
    """Cria registro inicial de análise (status=processando)."""
    rel = RelatorioAnalise(
        user_id=user_id,
        empresa_id=empresa_id,
        analysis_type=analysis_type,
        xml_chave=xml_chave,
        status="processando",
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


def finalizar_registro_analise(
    db,
    relatorio_id: int,
    *,
    status: str = "ok",
    tempo_execucao: float | None = None,
    total_alertas: int | None = None,
    score_resultante: float | None = None,
    resultado_json: dict | None = None,
):
    """Atualiza registro com resultado final da execução."""
    rel = db.query(RelatorioAnalise).filter(RelatorioAnalise.id == relatorio_id).first()
    if not rel:
        return
    if status == "cancelado":
        rel.status = "cancelado"
    else:
        rel.status = status
    if tempo_execucao is not None:
        rel.tempo_execucao = tempo_execucao
    if total_alertas is not None:
        rel.total_alertas = total_alertas
    if score_resultante is not None:
        rel.score_resultante = score_resultante
    if resultado_json is not None:
        rel.resultado_json = resultado_json
        rel.fingerprint = fingerprint_resultado_json(resultado_json)
    db.commit()


def contar_alertas_empresa(db, empresa_id: int, relatorio_id: int | None = None) -> int:
    """Conta alertas da empresa (opcionalmente vinculados ao relatório)."""
    q = db.query(AlertaFiscal).filter(AlertaFiscal.empresa_id == empresa_id)
    if relatorio_id is not None:
        q = q.filter(AlertaFiscal.relatorio_analise_id == relatorio_id)
    return q.count()


def executar_e_registrar_analise_xml(
    db,
    xml_bytes: bytes,
    user_id: int,
    empresa_id: int | None = None,
    limite_analises: int = 100,
) -> tuple[RelatorioAnalise, dict]:
    """
    Executa análise de XML e persiste em relatorios_analise.
    Motor fiscal grava execução, score grava resultado final.
    Verifica limite de uso antes e registra uso após conclusão.
    Retorna (RelatorioAnalise, resultado).
    """
    verificar_limite_analises(db, empresa_id, limite=limite_analises)

    inicio = time.perf_counter()
    resultado = executar_analise_xml(xml_bytes)
    documento_fiscal = None  # So a entidade documental ORM efetivamente persistida.

    if empresa_id and not resultado.get("dados_fiscais", {}).get("erro"):
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if empresa and empresa.user_id:
            class _UsuarioProxy:
                def __init__(self, user_id):
                    self.id = user_id

            usuario_proxy = _UsuarioProxy(empresa.user_id)
            try:
                documento_resultado = processar_e_persistir_xml(
                    db=db,
                    usuario_atual=usuario_proxy,
                    empresa=empresa,
                    xml_bytes=xml_bytes,
                )
                if (
                    type(documento_resultado) is tuple
                    and len(documento_resultado) == 3
                    and isinstance(documento_resultado[0], DocumentoFiscal)
                ):
                    documento_fiscal = documento_resultado[0]
            except DuplicataFiscalError as duplicata:
                # Uma chave NF-e igual nao prova bytes XML iguais.
                # So ignorar duplicacao quando o documento ja persistido
                # foi encontrado pelo SHA-256 dos bytes recebidos.
                from hashlib import sha256

                if duplicata.conteudo_sha256 != sha256(xml_bytes).hexdigest():
                    raise
                if (
                    type(duplicata.documento_id) is int
                    and duplicata.documento_id > 0
                    and callable(getattr(db, "get", None))
                ):
                    documento_existente = db.get(DocumentoFiscal, duplicata.documento_id)
                    if isinstance(documento_existente, DocumentoFiscal):
                        documento_fiscal = documento_existente
                logger.info(
                    "persistencia_xml_ignorada_duplicata empresa_id=%s",
                    empresa_id,
                )

    tempo = round(time.perf_counter() - inicio, 4)

    xml_chave = None
    if resultado.get("dados_fiscais") and not resultado["dados_fiscais"].get("erro"):
        xml_chave = resultado["dados_fiscais"].get("chave_nfe")

    if empresa_id and xml_chave:
        rel_existente = (
            db.query(RelatorioAnalise)
            .filter(
                RelatorioAnalise.empresa_id == empresa_id,
                RelatorioAnalise.analysis_type == "xml_analise",
                RelatorioAnalise.xml_chave == xml_chave,
            )
            .order_by(RelatorioAnalise.id.desc())
            .first()
        )
        if rel_existente:
            return rel_existente, {
                "status": "duplicado",
                "relatorio_id": rel_existente.id,
                "xml_chave": xml_chave,
            }

    try:
        rel = criar_registro_analise(
            db, user_id, "xml_analise", empresa_id=empresa_id, xml_chave=xml_chave
        )
    except IntegrityError:
        db.rollback()
        if empresa_id and xml_chave:
            rel_existente = (
                db.query(RelatorioAnalise)
                .filter(
                    RelatorioAnalise.empresa_id == empresa_id,
                    RelatorioAnalise.analysis_type == "xml_analise",
                    RelatorioAnalise.xml_chave == xml_chave,
                )
                .order_by(RelatorioAnalise.id.desc())
                .first()
            )
            if rel_existente:
                return rel_existente, {
                    "status": "duplicado",
                    "relatorio_id": rel_existente.id,
                    "xml_chave": xml_chave,
                }
        raise

    resultado_insights = None
    if empresa_id:
        try:
            from app.services.insights_engine import InsightEngine

            engine = InsightEngine(db)
            resultado_insights = engine.gerar_insights_empresa(
                empresa_id=empresa_id,
                relatorio_analise_id=rel.id,
            )
        except Exception:
            logger.exception(
                "Falha ao gerar insights (InsightEngine): empresa_id=%s relatorio_analise_id=%s",
                empresa_id,
                rel.id,
            )

    score_resultante = None
    if empresa_id:
        try:
            score_dict = calcular_score_global_tributario(db, empresa_id)
            s = score_dict.get("score_global_tributario")
            if s is not None:
                score_resultante = round(float(s), 2)
        except Exception:
            logger.exception(
                "Falha ao calcular score global: empresa_id=%s",
                empresa_id,
            )

    total_alertas = contar_alertas_empresa(db, empresa_id) if empresa_id else 0

    if empresa_id:
        resultado_final = compor_resultado_empresarial(empresa_id, resultado, resultado_insights)
        producer_id = "app.services.resultado_empresarial_service.compor_resultado_empresarial"
        if documento_fiscal is not None:
            if "_enterprise_xml_evidence" in resultado_final:
                raise ValueError("P103B_XML_EVIDENCE_KEY_ALREADY_PRESENT")
            resultado_final["_enterprise_xml_evidence"] = construir_vinculo_documento_relatorio(
                xml_bytes,
                empresa_id=empresa_id,
                relatorio_id=rel.id,
                documento=documento_fiscal,
                xml_chave=xml_chave,
            )
    else:
        resultado_final = resultado
        producer_id = "app.services.analysis_orchestrator.executar_analise_xml"

    resultado_persistido = selar_resultado_nao_mei(
        resultado_final,
        producer_id=producer_id,
    )

    finalizar_registro_analise(
        db,
        rel.id,
        status="erro" if resultado.get("dados_fiscais", {}).get("erro") else "ok",
        tempo_execucao=tempo,
        total_alertas=total_alertas,
        score_resultante=score_resultante,
        resultado_json=resultado_persistido,
    )
    incrementar_uso_analise(db, empresa_id)
    db.refresh(rel)
    return rel, resultado_final

def executar_circuito_enterprise_01(
    db, *, xml_bytes: bytes, authenticated_user_id: int, empresa_id: int,
    candidatos_normativos: list[dict] | None = None,
    pdfs_por_url: dict | None = None,
    evidencias_por_item: dict | None = None,
    referencias_adr020: list[dict] | None = None,
    referencias_temporais: list[dict] | None = None,
    referencias_cobertura: list[dict] | None = None,
) -> dict:
    """Ligacao opt-in de verificadores CANONICOS, estritamente sintetica.

    Utiliza o escritor empresarial ja existente e somente os resultados reais
    dos gates upstream. Nunca promove calculos L2 a autoridade juridica ou venda.
    Requer SQLAlchemy SQLite em memoria: nao opera em bases reais ou ficheiros.
    """
    import hashlib
    import hmac
    from datetime import datetime
    from defusedxml import ElementTree as ET

    from app.services.resultado_provenance_service import verificar_resultado_persistido
    from app.services.enterprise_integral_projection import projetar_diagnostico_integral_i0
    from app.services.enterprise_i2_documentary_bridge import projetar_diagnostico_integral_i2
    from app.services.enterprise_g13_subject_st_bridge import projetar_confronto_st_sujeito_g13
    from app.services.enterprise_g14_operational_normative_scope import cotejar_enquadramento_normativo_operacao_g14
    from app.services.enterprise_g17_publication_coverage_checkpoint import cotejar_cobertura_publicacao_g17
    from tools.enterprise_g113_temporal_mva_evidence import selecionar_mva_temporal_g113_c3
    from tools.enterprise_g113_c4_fiscal_item_bridge import cotejar_item_evidencia_calculo_g113_c4
    from tools.enterprise_g113_c5_parameter_trace import cotejar_rastro_parametros_g113_c5
    from tools.enterprise_g113_c6_l2_record_provenance import cotejar_registo_l2_g113_c6
    from tools.enterprise_g113_c7_diagnostic_dossier import preparar_dossie_investigativo_g113_c7

    def stop(code):
        raise ValueError("B01_" + code)

    def blocked(value, stage):
        if type(value) is not dict:
            stop(stage + "_CONTRATO_INVALIDO")
        for key in ("autoridade_fiscal", "credito_confirmado", "checkout_autorizado", "usavel_comercialmente"):
            if key in value and value[key] is not False:
                stop(stage + "_AUTORIDADE_INDEVIDA")

    if (db is None or type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= 2 * 1024 * 1024
            or type(authenticated_user_id) is not int or authenticated_user_id <= 0
            or type(empresa_id) is not int or empresa_id <= 0):
        stop("ENTRADA_INVALIDA")
    # Bloqueio de ambiente ANTES de executar qualquer escrita/call externa.
    try:
        bind = db.get_bind()
        url = bind.url
        memory_only = (bind.dialect.name == "sqlite" and url.database in (None, ":memory:"))
    except Exception:
        memory_only = False
    if not memory_only:
        stop("APENAS_SQLITE_EM_MEMORIA")

    if candidatos_normativos is not None and type(candidatos_normativos) is not list:
        stop("CANDIDATOS_INVALIDOS")
    if pdfs_por_url is not None and type(pdfs_por_url) is not dict:
        stop("PDFS_INVALIDOS")
    if evidencias_por_item is not None and type(evidencias_por_item) is not dict:
        stop("EVIDENCIAS_INVALIDAS")
    if any(ref is not None and type(ref) is not list for ref in
           (referencias_adr020, referencias_temporais, referencias_cobertura)):
        stop("REFERENCIAS_ADR020_INVALIDAS")

    # Verificar emissao e operacao ANTES da escrita; C3 usa esta data EXATA.
    try:
        root = ET.fromstring(xml_bytes, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        ns = {"n": "http://www.portalfiscal.inf.br/nfe"}
        infs = root.findall(".//n:infNFe", ns)
        if len(infs) != 1:
            stop("INFNFE_CARDINALIDADE_INVALIDA")
        emission = infs[0].findtext("n:ide/n:dhEmi", namespaces=ns)
        moment = datetime.fromisoformat(emission)
        if moment.utcoffset() is None:
            stop("EMISSAO_SEM_FUSO")
        date = moment.date().isoformat()
        if (infs[0].findtext("n:ide/n:tpNF", namespaces=ns) != "1"
                or infs[0].findtext("n:ide/n:mod", namespaces=ns) != "55"):
            stop("OPERACAO_NAO_APLICAVEL")
    except ValueError as exc:
        if str(exc).startswith("B01_"):
            raise
        raise ValueError("B01_XML_INVALIDO") from exc
    except Exception as exc:
        raise ValueError("B01_XML_INVALIDO") from exc

    empresa = db.get(Empresa, empresa_id)
    if (empresa is None or empresa.id != empresa_id or empresa.user_id != authenticated_user_id
            or getattr(empresa, "optante_mei", None) is True
            or getattr(empresa, "regime_tributario", None) not in ("real", "presumido")):
        stop("SUJEITO_NAO_AUTORIZADO")
    # Preflight sujeito/documento: falhar ANTES de qualquer commit da analise.
    inf = infs[0]
    emitter = inf.findtext("n:emit/n:CNPJ", namespaces=ns)
    nfe_key = inf.get("Id")
    if (type(emitter) is not str or emitter != getattr(empresa, "cnpj", None)
            or type(nfe_key) is not str or not nfe_key.startswith("NFe")
            or len(nfe_key) != 47 or not nfe_key[3:].isascii()
            or not nfe_key[3:].isdecimal()):
        stop("XML_SUJEITO_OU_CHAVE_DIVERGENTE")

    # ESCRITOR UNICO existente. Nao altera sua funcao nem seus contratos.
    rel, retorno = executar_e_registrar_analise_xml(db, xml_bytes, authenticated_user_id, empresa_id)
    if (type(retorno) is not dict or retorno.get("status") == "duplicado"
            or getattr(rel, "id", 0) < 1
            or getattr(rel, "status", None) != "ok"
            or getattr(rel, "user_id", None) != authenticated_user_id
            or getattr(rel, "empresa_id", None) != empresa_id
            or getattr(rel, "analysis_type", None) != "xml_analise"):
        stop("RELATORIO_NAO_ELEGIVEL")
    persisted = verificar_resultado_persistido(rel)
    if persisted.get("empresa_id") != empresa_id:
        stop("RESULTADO_OUTRA_EMPRESA")

    args = dict(db=db, authenticated_user_id=authenticated_user_id,
                empresa_id=empresa_id, relatorio_id=rel.id, xml_bytes=xml_bytes)
    i2 = projetar_diagnostico_integral_i2(**args)
    g13 = projetar_confronto_st_sujeito_g13(**args)
    g14 = cotejar_enquadramento_normativo_operacao_g14(**args, candidatos_normativos=candidatos_normativos)
    # Invoca realmente ADR-020 (G17->G16->G15); na falta de referencias,
    # os gates retornam lacunas sem promover normatividade.
    g17 = cotejar_cobertura_publicacao_g17(
        **args, candidatos_normativos=candidatos_normativos,
        referencias_adr020=referencias_adr020,
        referencias_temporais=referencias_temporais,
        referencias_cobertura=referencias_cobertura,
    )
    i0 = projetar_diagnostico_integral_i0(resultado=persisted, empresa_id=empresa_id)
    sha = hashlib.sha256(xml_bytes).hexdigest()
    doc = i2.get("documental_i2") if type(i2) is dict else None
    if (type(doc) is not dict or doc.get("relatorio_id") != rel.id
            or not all(type(x) is dict for x in (g13, g14, g17, i0))
            or not all(type(x.get("xml_sha256")) is str and hmac.compare_digest(x["xml_sha256"], sha)
                       for x in (doc, g13, g14, g17))
            or not all(x.get("empresa_id") == empresa_id and x.get("relatorio_id") == rel.id
                       and x.get("documento_id") == doc.get("documento_id") for x in (g13, g14, g17))
            or g14.get("itens_total") != g13.get("itens_total")
            or type(g14.get("itens")) is not list
            or g14.get("itens_total") != len(g14["itens"])
            or i0.get("empresa_id") != empresa_id
            or i0.get("uso") != "INTERNO_NAO_PUBLICAVEL"
            or i0.get("diagnostico_empresarial_completo") is not False
            or i0.get("comprovacao_normativa") is not False):
        stop("CADEIA_DOCUMENTO_IDENTIDADE_DIVERGENTE")
    for name, value in (("I2", i2), ("G13", g13), ("G14", g14), ("G17", g17), ("I0", i0)):
        blocked(value, name)

    # Compatibilidade de contrato NEGATIVA e restrita ao B01:
    # G1 historico publica autoridade_fiscal/credito_confirmado/checkout_autorizado
    # todos False, mas C4 exige tambem usavel_comercialmente=False explicito.
    # Projeta apenas essa NEGACAO, deduzida do G12 e G13 ja verificados.
    # Nao altera G1/G12/G13 originais, nao cria pares, valores, nem fonte.
    from copy import deepcopy
    c4_subject = g13
    original_g12 = g13.get("confronto_condicional_g12")
    original_g1 = original_g12.get("confronto_g1") if type(original_g12) is dict else None
    if (type(original_g1) is dict
            and original_g1.get("estado") in
                ("COMPARACAO_NUMERICA_SEM_AUTORIDADE", "PARCIAL_SEM_AUTORIDADE")
            and "usavel_comercialmente" not in original_g1):
        if (g13.get("usavel_comercialmente") is not False
                or original_g12.get("usavel_comercialmente") is not False
                or any(original_g1.get(k) is not False for k in
                       ("autoridade_fiscal", "credito_confirmado", "checkout_autorizado"))):
            stop("G1_NEGACOES_UPSTREAM_NAO_COMPROVADAS")
        c4_subject = deepcopy(g13)
        c4_subject["confronto_condicional_g12"]["confronto_g1"]["usavel_comercialmente"] = False

    manifests = evidencias_por_item or {}
    if any(type(k) is not int or not 1 <= k <= len(g14["itens"]) for k in manifests):
        stop("MANIFESTO_ITEM_INVALIDO")
    itens = []
    for index, candidate in enumerate(g14["itens"], 1):
        if (type(candidate) is not dict or candidate.get("indice_item") != index
                or candidate.get("competencia_declarada") != date[:7]):
            stop("G14_ITEM_INVALIDO")
        item = dict(indice_item=index, estado="ABSTENCAO",
                    motivo="EVIDENCIA_C3_INEXISTENTE", dossie=None)
        if candidate.get("estado") != "COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST":
            item["motivo"] = "G14_SEM_CANDIDATO_ESTRUTURAL"
        elif index not in manifests:
            pass
        else:
            if pdfs_por_url is None or type(manifests[index]) is not list or not manifests[index]:
                stop("EVIDENCIA_C3_MALFORMADA")
            c3 = selecionar_mva_temporal_g113_c3(
                pdfs_por_url=pdfs_por_url,
                item=dict(indice_item=index, uf=candidate["uf_operacao"],
                          ncm=candidate["ncm"], cest=candidate["cest_observado"]),
                data_operacao=date, evidencias=manifests[index],
            )
            blocked(c3, "C3")
            if c3.get("estado") != "CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE":
                item["motivo"] = "C3_" + str(c3.get("motivo", "ABSTENCAO"))
            else:
                c4 = cotejar_item_evidencia_calculo_g113_c4(
                    xml_bytes=xml_bytes, authenticated_user_id=authenticated_user_id,
                    empresa_id=empresa_id, relatorio_id=rel.id, indice_item=index,
                    g13_result=c4_subject, g14_result=g14, c3_result=c3,
                )
                blocked(c4, "C4")
                if c4.get("estado") != "CONFRONTO_NUMERICO_E_MVA_CANDIDATA_SEM_PONTE_CAUSAL":
                    item["motivo"] = "C4_" + str(c4.get("estado"))
                else:
                    c5 = cotejar_rastro_parametros_g113_c5(
                        c4_result=c4, c3_result=c3, g13_result=c4_subject,
                        g14_item=candidate, indice_item=index,
                    )
                    blocked(c5, "C5")
                    if c5.get("parametros_motor_cotejados") is not True:
                        item["motivo"] = "C5_" + str(c5.get("estado"))
                    else:
                        c6 = cotejar_registo_l2_g113_c6(
                            c4_result=c4, c5_result=c5, g13_result=c4_subject, indice_item=index,
                        )
                        blocked(c6, "C6")
                        if c6.get("estado") != "REGISTO_L2_IDENTIFICADO_SEM_UNICIDADE_OU_ADR020":
                            item["motivo"] = "C6_" + str(c6.get("estado"))
                        else:
                            # Compatibilidade NEGATIVA e estrita C4 -> C7:
                            # C4 transporta pares G1 previamente validados mas
                            # omite prova_normativa=False. C7 exige esse False.
                            # Conferir as identidades e montantes originais, antes
                            # de copiar APENAS a negacao de prova do G1 real.
                            # C4 original, G1, G12, C5 e C6 ficam intactos.
                            from decimal import Decimal, InvalidOperation
                            from copy import deepcopy
                            if (type(original_g1) is not dict
                                    or type(original_g1.get("comparacoes")) is not list
                                    or type(c4.get("comparacao_g1")) is not dict
                                    or set(c4["comparacao_g1"]) != {"BASE_ST", "ICMS_ST"}):
                                stop("C7_G1_PARES_INDISPONIVEIS")
                            upstream = [v for v in original_g1["comparacoes"]
                                        if type(v) is dict and v.get("indice_item") == index]
                            if (len(upstream) != 2
                                    or {v.get("tipo") for v in upstream} != {"BASE_ST", "ICMS_ST"}):
                                stop("C7_G1_PARES_AMBIGUOS")
                            originals = {v["tipo"]: v for v in upstream}
                            c7_c4 = deepcopy(c4)
                            for kind in ("BASE_ST", "ICMS_ST"):
                                real = originals[kind]
                                pair = c7_c4["comparacao_g1"].get(kind)
                                if (type(pair) is not dict
                                        or real.get("prova_normativa") is not False
                                        or real.get("divergencia_numerica") != pair.get("divergencia_numerica")
                                        or type(real.get("divergencia_numerica")) is not bool
                                        or ("prova_normativa" in pair
                                            and pair["prova_normativa"] is not False)):
                                    stop("C7_G1_NEGACAO_OU_DIVERGENCIA_INVALIDA")
                                try:
                                    equal = (
                                        Decimal(str(real["valor_xml"])) == Decimal(str(pair["valor_xml"]))
                                        and Decimal(str(real["valor_motor"]))
                                        == Decimal(str(pair["valor_motor_g12"]))
                                    )
                                except (KeyError, InvalidOperation, ValueError, TypeError):
                                    equal = False
                                if not equal:
                                    stop("C7_G1_MONTANTES_DIVERGENTES")
                                pair["prova_normativa"] = False
                            c7 = preparar_dossie_investigativo_g113_c7(
                                c3_result=c3, c4_result=c7_c4, c5_result=c5,
                                c6_result=c6, indice_item=index,
                            )
                            blocked(c7, "C7")
                            if c7.get("estado") != "DOSSIER_INTERNO_NAO_PUBLICAVEL":
                                stop("C7_ESTADO_INVALIDO")
                            item.update(estado="DOSSIER_INTERNO_NAO_PUBLICAVEL",
                                        motivo="C3_C7_EXECUTADOS_SEM_AUTORIDADE", dossie=c7)
        itens.append(item)
    if type(i0.get("cobertura")) is not list or len(i0["cobertura"]) != 52:
        stop("CATALOGO_INTEGRAL_DIVERGENTE")
    return {
        "schema_version": "SOLVERIS_ENTERPRISE_B01_SYNTHETIC_V1",
        "uso": "INTERNO_NAO_PUBLICAVEL", "empresa_id": empresa_id,
        "authenticated_user_id": authenticated_user_id,
        "relatorio_id": rel.id, "documento_id": doc["documento_id"],
        "xml_sha256": sha, "resultado_fingerprint": rel.fingerprint,
        "i0": i0, "i2": i2, "g13": g13, "g14": g14,
        "adr020_g17": g17, "itens": itens,
        "compatibilidade_g1_apenas_negacao_comercial": c4_subject is not g13,
        "autoridade_fiscal": False, "credito_confirmado": False,
        "checkout_autorizado": False, "usavel_comercialmente": False,
        "diagnostico_empresarial_completo": False,
    }
