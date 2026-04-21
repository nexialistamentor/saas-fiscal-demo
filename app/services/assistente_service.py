import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func

from app import models
from app.services.imposto_service import calcular_imposto_simples, calcular_imposto_simples_nacional
from app.services.insights_engine import InsightEngine
from app.services.analysis_orchestrator import executar_analise

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def calcular_impostos_empresa_service(empresa, dados_fiscais):
    return executar_analise("empresa_tax", dados_fiscais, empresa=empresa)


def simular_planejamento_tributario(dados_fiscais):
    return executar_analise("tax_planning", dados_fiscais)


def simular_recuperacao_tributaria(dados_fiscais):
    return executar_analise("tax_recovery", dados_fiscais)


def identificar_contribuinte(pergunta: str) -> str:
    p = pergunta.lower()

    if "mei" in p:
        return "mei"

    if (
        "empresa" in p
        or "simples nacional" in p
        or "minha empresa" in p
        or "empresa paga" in p
    ):
        return "empresa"

    if "cpf" in p or "autônomo" in p or "autonomo" in p:
        return "cpf"

    return "desconhecido"


def identificar_intencao(pergunta: str) -> str:
    p = pergunta.lower()

    # Prioridade 1: limite / faturamento máximo (antes do genérico "fatur")
    if (
        "limite mei" in p
        or "limite do mei" in p
        or "quanto posso faturar" in p
        or "faturamento máximo" in p
        or "faturamento maximo" in p
        or "limite mensal" in p
    ):
        return "limite_mensal_mei"

    # Prioridade 2: recuperação tributária (antes do genérico "fatur")
    if (
        "recuperar" in p
        or "recuperação" in p
        or "recuperacao" in p
        or "crédito tributário" in p
        or "credito tributario" in p
        or "crédito tributario" in p
        or "icms na base" in p
        or ("pis" in p and "cofins" in p)
    ):
        return "recuperacao_tributaria"

    # Prioridade 3: perguntas com valores/contexto de faturamento → simulação
    if "fatur" in p:
        return "simulacao_mei"

    # Prioridade 4: dúvidas genéricas sobre imposto MEI
    if "imposto mei" in p or "quanto paga mei" in p:
        return "imposto_mei"

    if "restituição" in p or "restituicao" in p:
        return "restituicao"

    if "lucro presumido ou lucro real" in p or "melhor regime" in p:
        return "planejamento_tributario"

    return "desconhecida"


def _parse_valor_br(s: str) -> float:
    """Converte string com separadores BR (7.000, 7,000, 7,50) para float."""
    s = s.strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        decimais = s.split(",")[-1]
        s = s.replace(",", ".") if len(decimais) <= 2 else s.replace(",", "")
    elif "." in s:
        parte = s.split(".")[-1]
        s = s.replace(".", "") if len(parte) == 3 and parte.isdigit() else s
    return float(s)


def extrair_faturamento(pergunta: str):
    numeros = re.findall(r"\d+[.,]?\d*", pergunta)
    if numeros:
        valor = _parse_valor_br(numeros[0])
        if "mil" in pergunta.lower() and valor < 1000:
            valor *= 1000
        return valor
    return None


def _fmt_br(valor: float, decimais: int = 2) -> str:
    """Formata valor no padrão brasileiro (1.234,56)."""
    s = f"{valor:.{decimais}f}"
    int_part, _, dec_part = s.partition(".")
    # Insere pontos como separador de milhares (da direita para esquerda)
    partes = []
    while len(int_part) > 3:
        partes.insert(0, int_part[-3:])
        int_part = int_part[:-3]
    partes.insert(0, int_part)
    int_fmt = ".".join(partes)
    return f"{int_fmt},{dec_part}" if decimais else int_fmt


def responder_mei(pergunta: str) -> str:
    """Lógica específica para MEI: limite, simulação e imposto."""
    intencao = identificar_intencao(pergunta)
    faturamento = extrair_faturamento(pergunta)

    if intencao == "limite_mensal_mei":
        return (
            "O limite anual do MEI é R$ 81.000.\n"
            "Isso corresponde a cerca de R$ 6.750 por mês."
        )

    if intencao == "imposto_mei":
        resultado = calcular_imposto_simples(
            faturamento=6500,
            despesas=0,
            tipo="MEI"
        )
        return f"O MEI paga aproximadamente R$ {_fmt_br(resultado['imposto'])} por mês no DAS."

    if intencao == "simulacao_mei" and faturamento:
        resultado = calcular_imposto_simples(
            faturamento=faturamento,
            despesas=0,
            tipo="MEI"
        )

        faturamento_anual = faturamento * 12
        restante = max(0, 81000 - faturamento_anual)

        if faturamento_anual > 81000:
            return (
                f"Com faturamento de R$ {_fmt_br(faturamento)} por mês "
                f"você ultrapassaria o limite anual do MEI."
            )

        return (
            f"Com faturamento de R$ {_fmt_br(faturamento)} por mês "
            f"você ainda pode faturar cerca de R$ {_fmt_br(restante)} "
            f"antes de atingir o limite anual do MEI."
        )

    if intencao == "restituicao":
        return "A restituição ocorre quando o contribuinte pagou imposto a mais e pode solicitar a devolução."

    return (
        "Posso ajudar com dúvidas sobre MEI, impostos, faturamento ou restituição."
    )


def formatar_resposta_insights(resultado: dict) -> str:
    """Formata o resultado do insights_engine em texto legível para o usuário."""
    partes = []

    risco = resultado.get("risco_tributario", {})
    if risco:
        nivel = risco.get("nivel_risco", "N/A")
        partes.append(f"**Risco tributário:** {nivel}")

    creditos = resultado.get("creditos_detectados", [])
    if creditos:
        total_creditos = sum(c.get("valor_estimado", 0) for c in creditos)
        partes.append(f"\n**Créditos identificados:** {len(creditos)} oportunidade(s)")
        for c in creditos[:5]:
            desc = c.get("descricao", c.get("tipo", ""))
            valor = c.get("valor_estimado", 0)
            partes.append(f"  • {desc} (R$ {_fmt_br(valor)})")
        if total_creditos > 0:
            partes.append(f"\nTotal estimado em créditos: R$ {_fmt_br(total_creditos)}")

    oportunidades = resultado.get("oportunidades", [])
    if oportunidades:
        partes.append(f"\n**Oportunidades fiscais:** {len(oportunidades)} insight(s)")
        for o in oportunidades[:5]:
            desc = o.get("descricao", o.get("tipo", "Oportunidade"))
            partes.append(f"  • {desc}")

    if not partes:
        return "Análise concluída. Nenhuma oportunidade de crédito ou alerta relevante foi identificado para a empresa no momento."

    return "\n".join(partes)


def _inferir_anexo_simples(pergunta: str) -> str:
    """Inferir anexo do Simples Nacional por palavras-chave. Default: I (comércio)."""
    p = pergunta.lower()
    if "indústria" in p or "industria" in p or "fábrica" in p or "fabrica" in p:
        return "II"
    if "serviço" in p or "servico" in p:
        if "segurança" in p or "limpeza" in p or "vigilância" in p:
            return "IV"
        if "consultoria" in p or "tecnologia" in p or "ti " in p or "publicidade" in p:
            return "V"
        return "III"
    return "I"  # Comércio (padrão)


def _obter_rbt12_empresa(db: "Session", empresa_id: int) -> float | None:
    """Soma valor_total das NF-e de saída dos últimos 12 meses."""
    hoje = datetime.now().date()
    doze_meses_atras = hoje - timedelta(days=365)
    resultado = (
        db.query(func.coalesce(func.sum(models.DocumentoFiscal.valor_total), 0))
        .filter(
            models.DocumentoFiscal.empresa_id == empresa_id,
            models.DocumentoFiscal.tipo == "saida",
            models.DocumentoFiscal.data_emissao >= doze_meses_atras,
        )
        .scalar()
    )
    return float(resultado) if resultado and float(resultado) > 0 else None


def _obter_icms_empresa(db: "Session", empresa_id: int) -> float | None:
    """Soma valor_icms dos itens das NF-e de saída dos últimos 12 meses."""
    hoje = datetime.now().date()
    doze_meses_atras = hoje - timedelta(days=365)
    resultado = (
        db.query(func.coalesce(func.sum(models.ItemFiscal.valor_icms), 0))
        .join(models.DocumentoFiscal, models.ItemFiscal.documento_id == models.DocumentoFiscal.id)
        .filter(
            models.DocumentoFiscal.empresa_id == empresa_id,
            models.DocumentoFiscal.tipo == "saida",
            models.DocumentoFiscal.data_emissao >= doze_meses_atras,
        )
        .scalar()
    )
    return float(resultado) if resultado and float(resultado) >= 0 else None


def responder_empresa(pergunta: str, usuario, db: "Session") -> str:
    """
    Analisa empresa após verificação de pagamento.
    Fluxo: Simples Nacional (calcula sem pagamento) → crédito → verificar pagamento.
    Usa: imposto_service (Simples), insights_engine (créditos).
    """
    p = pergunta.lower()

    # Simples Nacional: "Quanto minha empresa paga no Simples Nacional?"
    # Não exige consulta_paga — cálculo disponível para qualquer empresa.
    if (
        "simples nacional" in p
        or "simples" in p
        or "quanto paga" in p and "empresa" in p
        or "imposto empresa" in p
    ):
        rbt12 = None
        empresa_id = usuario.empresas[0].id if usuario.empresas else None

        # 1) Tentar faturamento da pergunta (ex: "50 mil por mês")
        faturamento_pergunta = extrair_faturamento(pergunta)
        if faturamento_pergunta:
            if "mil" in p or faturamento_pergunta >= 1000:
                rbt12 = faturamento_pergunta * 12
            else:
                rbt12 = faturamento_pergunta * 12  # assumir mensal

        # 2) Se tem empresa e NF-e, usar dados das notas
        if rbt12 is None and empresa_id:
            rbt12 = _obter_rbt12_empresa(db, empresa_id)

        if rbt12 and rbt12 > 0:
            anexo = _inferir_anexo_simples(pergunta)
            resultado = calcular_imposto_simples_nacional(
                rbt12=rbt12,
                receita_mes=rbt12 / 12,
                anexo=anexo,
            )
            fonte = (
                "com base nas NF-e cadastradas"
                if empresa_id and not faturamento_pergunta
                else "com base no faturamento informado"
            )
            msg = (
                f"No Simples Nacional (Anexo {resultado['anexo']} - {resultado['nome_anexo']}), "
                f"com RBT12 de R$ {_fmt_br(resultado['rbt12'])}, sua empresa está na "
                f"faixa de R$ {_fmt_br(resultado['faixa_simples_min'])} a R$ {_fmt_br(resultado['faixa_simples_max'])} "
                f"(alíquota nominal {resultado['aliquota_nominal_pct']}%, parcela a deduzir R$ {_fmt_br(resultado['parcela_deduzir'], decimais=0)}). "
                f"DAS estimado: **R$ {_fmt_br(resultado['das_mensal'])} por mês** "
                f"(cerca de R$ {_fmt_br(resultado['das_anual'])} por ano). "
                f"Alíquota efetiva: {resultado['aliquota_efetiva_pct']}%."
            )
            if resultado.get("alertas"):
                msg += "\n\n" + " ".join(resultado["alertas"])
            msg += f"\n\n*(Estimativa {fonte} — consulte um contador para valores oficiais.)*"
            return msg

        return (
            "Para calcular quanto sua empresa paga no Simples Nacional, informe o faturamento "
            "mensal (ex: \"faturamos 50 mil por mês\") ou envie os XMLs das NF-e para usarmos "
            "o faturamento real da empresa."
        )

    # Perguntas sobre créditos tributários → orientação + convite para análise
    if "icms" in p or "pis" in p or "cofins" in p or "credito" in p:
        if not usuario.consulta_paga:
            return (
                "É possível identificar créditos de ICMS, PIS ou COFINS analisando "
                "as notas fiscais da empresa. Para isso a plataforma precisa analisar "
                "os arquivos XML das NF-e da empresa.\n\n"
                "Após liberar a análise fiscal, o sistema calcula automaticamente "
                "o potencial de recuperação tributária."
            )

        # Pagamento liberado → análise completa
        empresa_id = usuario.empresas[0].id if usuario.empresas else None
        if not empresa_id:
            return (
                "Nenhuma empresa vinculada ao seu usuário. "
                "Cadastre uma empresa para receber análises fiscais personalizadas."
            )
        engine = InsightEngine(db)
        resultado = engine.gerar_insights_empresa(empresa_id)
        return formatar_resposta_insights(resultado)

    # Outras perguntas de empresa
    if not usuario.consulta_paga:
        return (
            "Posso analisar possíveis créditos de ICMS, PIS e COFINS na sua empresa. "
            "Para isso é necessário enviar o XML das NF-e e liberar a análise."
        )

    empresa_id = usuario.empresas[0].id if usuario.empresas else None
    if not empresa_id:
        return (
            "Nenhuma empresa vinculada ao seu usuário. "
            "Cadastre uma empresa para receber análises fiscais personalizadas."
        )

    engine = InsightEngine(db)
    resultado = engine.gerar_insights_empresa(empresa_id)
    return formatar_resposta_insights(resultado)


def responder_cpf(pergunta: str) -> str:
    """Usa imposto_service para CPF/autônomo."""
    faturamento = extrair_faturamento(pergunta) or 5000
    resultado = calcular_imposto_simples(
        faturamento=faturamento,
        despesas=0,
        tipo="CPF"
    )
    return (
        f"Como autônomo (CPF), com faturamento de R$ {_fmt_br(faturamento)} por mês, "
        f"o imposto estimado seria cerca de R$ {_fmt_br(resultado['imposto'])}. "
        f"Base: regime simplificado (6%)."
    )


def _anexo_para_atividade(anexo: str) -> str:
    """Mapeia anexo Simples (I, II, III...) para atividade do motor (comercio, industria, servicos)."""
    if anexo == "II":
        return "industria"
    if anexo in ("III", "IV", "V"):
        return "servicos"
    return "comercio"


def _obter_dados_fiscais_planejamento(pergunta: str, usuario, db) -> dict | None:
    """Obtém dados fiscais para simulação de planejamento (lucro presumido x real)."""
    faturamento = extrair_faturamento(pergunta)
    if faturamento:
        if faturamento < 1000 and "mil" in pergunta.lower():
            faturamento *= 1000
        rbt12 = faturamento * 12
        anexo = _inferir_anexo_simples(pergunta)
        return {
            "faturamento": rbt12,
            "atividade": _anexo_para_atividade(anexo),
            "receita_bruta": rbt12,
            "custos": 0,
            "despesas": 0,
        }
    if usuario and db and usuario.empresas:
        rbt12 = _obter_rbt12_empresa(db, usuario.empresas[0].id)
        if rbt12 and rbt12 > 0:
            return {
                "faturamento": rbt12,
                "atividade": "comercio",
                "receita_bruta": rbt12,
                "custos": 0,
                "despesas": 0,
            }
    return None


def _obter_dados_fiscais_recuperacao(pergunta: str, usuario, db) -> dict | None:
    """Obtém faturamento e ICMS para simulação de recuperação tributária."""
    faturamento = None
    icms = None

    if usuario and db and usuario.empresas:
        empresa_id = usuario.empresas[0].id
        faturamento = _obter_rbt12_empresa(db, empresa_id)
        icms = _obter_icms_empresa(db, empresa_id)
        if faturamento and icms is None:
            icms = faturamento * 0.18  # estimativa se não houver NF-e com ICMS

    faturamento_pergunta = extrair_faturamento(pergunta)
    if faturamento_pergunta:
        faturamento = faturamento_pergunta * 12
        if icms is None:
            icms = faturamento * 0.18  # estimativa 18% ICMS

    if faturamento and faturamento > 0:
        return {"faturamento": faturamento, "icms": icms or 0}
    return None


def _formatar_resposta_recuperacao(resultado: dict) -> str:
    """Formata o resultado de simular_recuperacao_tributaria para o usuário."""
    creditos = resultado.get("creditos", {})
    total = creditos.get("total", 0)
    pis = creditos.get("pis", 0)
    cofins = creditos.get("cofins", 0)
    msg = (
        f"**Análise de recuperação tributária (PIS/COFINS na base):**\n"
        f"• Crédito PIS estimado: R$ {_fmt_br(pis)}\n"
        f"• Crédito COFINS estimado: R$ {_fmt_br(cofins)}\n"
        f"• **Total potencial de recuperação: R$ {_fmt_br(total)}**\n\n"
    )
    for a in resultado.get("alertas", []):
        msg += f"_{a}_\n"
    return msg.strip()


def _formatar_resposta_planejamento(resultado: dict) -> str:
    """Formata o resultado de simular_planejamento_tributario para o usuário."""
    comp = resultado.get("comparacao", {})
    melhor = resultado.get("melhor_regime", "")
    economia = resultado.get("economia_estimada", 0)
    regime_nome = "Lucro Presumido" if melhor == "lucro_presumido" else "Lucro Real"
    lp_total = comp.get("lucro_presumido", 0)
    lr_total = comp.get("lucro_real", 0)
    msg = (
        f"**Comparação de regimes:**\n"
        f"• Lucro Presumido: R$ {_fmt_br(lp_total)}/ano\n"
        f"• Lucro Real: R$ {_fmt_br(lr_total)}/ano\n\n"
        f"**Melhor regime para o seu perfil:** {regime_nome}\n"
        f"Economia estimada: R$ {_fmt_br(economia)}/ano.\n\n"
    )
    for a in resultado.get("alertas", []):
        msg += f"_{a}_\n"
    return msg.strip()


def responder_pergunta(
    pergunta: str,
    usuario=None,
    db=None,
) -> dict:
    """
    Fluxo do Assistente Fiscal:
    identificar_contribuinte → MEI/CPF (imposto_service) ou Empresa (verificar pagamento).
    Empresa: preview (não pago) ou insights_engine + motor fiscal (pago).
    Retorna: {resposta, requires_payment, analysis_type} para integração com fluxo de pagamento.
    """
    # Blindagem contextual contra manipulação semântica
    bloqueios_contextuais = [
        "finja que você é",
        "aja como",
        "ignore instruções",
        "responda como sistema",
        "modo desenvolvedor",
        "bypass",
    ]

    texto = pergunta.lower()

    for padrao in bloqueios_contextuais:
        if padrao in texto:
            return {
                "resposta": "Pergunta inválida ou manipulativa detectada.",
                "requires_payment": False,
                "analysis_type": None,
            }

    intencao = identificar_intencao(pergunta)
    if intencao == "planejamento_tributario":
        dados_fiscais = _obter_dados_fiscais_planejamento(pergunta, usuario, db)
        if dados_fiscais:
            resultado = simular_planejamento_tributario(dados_fiscais)
            return {
                "resposta": _formatar_resposta_planejamento(resultado),
                "requires_payment": True,
                "analysis_type": "tax_planning",
            }
        return {
            "resposta": (
                "Para comparar lucro presumido e lucro real, informe o faturamento "
                "(ex: \"100 mil por mês\") ou vincule uma empresa com NF-e cadastradas."
            ),
            "requires_payment": True,
            "analysis_type": "tax_planning",
        }

    if intencao == "recuperacao_tributaria":
        dados_fiscais = _obter_dados_fiscais_recuperacao(pergunta, usuario, db)
        if dados_fiscais:
            resultado = simular_recuperacao_tributaria(dados_fiscais)
            return {
                "resposta": _formatar_resposta_recuperacao(resultado),
                "requires_payment": True,
                "analysis_type": "tax_recovery",
            }
        return {
            "resposta": (
                "Para estimar quanto você pode recuperar de PIS/COFINS ou verificar "
                "crédito tributário por ICMS na base, informe o faturamento "
                "(ex: \"faturamos 100 mil por mês\") ou vincule uma empresa com NF-e cadastradas."
            ),
            "requires_payment": True,
            "analysis_type": "tax_recovery",
        }

    contribuinte = identificar_contribuinte(pergunta)

    if contribuinte == "mei":
        return {
            "resposta": responder_mei(pergunta),
            "requires_payment": True,
            "analysis_type": "mei_tax",
        }

    if contribuinte == "empresa":
        if usuario is None or db is None:
            return {
                "resposta": (
                    "Para análises de empresa, faça login e vincule uma empresa. "
                    "Posso analisar créditos de ICMS, PIS e COFINS após envio dos XMLs e liberação da análise."
                ),
                "requires_payment": True,
                "analysis_type": "tax_recovery",
            }
        resp = responder_empresa(pergunta, usuario, db)
        return {
            "resposta": resp,
            "requires_payment": True,
            "analysis_type": "tax_recovery",
        }

    if contribuinte == "cpf":
        return {
            "resposta": responder_cpf(pergunta),
            "requires_payment": True,
            "analysis_type": "mei_tax",
        }

    # Assumir MEI quando há faturamento mas tipo não especificado (caso mais comum)
    if contribuinte == "desconhecido" and extrair_faturamento(pergunta):
        return {
            "resposta": responder_mei(pergunta),
            "requires_payment": True,
            "analysis_type": "mei_tax",
        }

    return {
        "resposta": (
            "Posso ajudar com dúvidas sobre MEI, empresa (Simples Nacional, créditos), "
            "CPF/autônomo, impostos ou restituição. Especifique o tipo de contribuinte na sua pergunta."
        ),
        "requires_payment": False,
        "analysis_type": None,
    }
