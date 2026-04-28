from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _quebrar_texto(c, texto: str, x: float, y: float, largura_max: float) -> float:
    """Quebra texto longo em linhas e desenha. Retorna o y final."""
    palavras = texto.split()
    linhas = []
    linha_atual = ""
    for p in palavras:
        test = linha_atual + " " + p if linha_atual else p
        if c.stringWidth(test) <= largura_max:
            linha_atual = test
        else:
            if linha_atual:
                linhas.append(linha_atual)
            linha_atual = p
    if linha_atual:
        linhas.append(linha_atual)
    for l in linhas:
        c.drawString(x, y, l)
        y -= 14
    return y


def gerar_pdf_imposto(resultado: dict) -> BytesIO:
    """
    Gera PDF com cálculo detalhado de imposto para MEI/CPF.
    Inclui: cálculo completo, orientação de pagamento, resumo fiscal, insight.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    margem = 50
    largura = w - 2 * margem
    y = h - 50

    # --- Cabeçalho ---
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margem, y, "Relatório de Cálculo de Imposto")
    y -= 35

    c.setFont("Helvetica", 10)
    tipo = resultado.get("tipo", "N/A")
    c.drawString(margem, y, f"Tipo: {tipo}")
    y -= 20

    # --- Cálculo completo ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margem, y, "1. CÁLCULO COMPLETO")
    y -= 25

    c.setFont("Helvetica", 10)
    fat = resultado.get("faturamento", 0)
    desp = resultado.get("despesas", 0)
    base = resultado.get("base_calculo", 0)
    imposto = resultado.get("imposto", 0)
    aliquota = resultado.get("aliquota_info", "")

    c.drawString(margem + 20, y, f"Faturamento mensal: R$ {fat:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    y -= 18
    c.drawString(margem + 20, y, f"Despesas dedutíveis: R$ {desp:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    y -= 18
    c.drawString(margem + 20, y, f"Base de cálculo: R$ {base:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    y -= 18
    c.drawString(margem + 20, y, f"Regra aplicada: {aliquota}")
    y -= 18
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margem + 20, y, f"IMPOSTO ESTIMADO: R$ {imposto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    y -= 30

    # --- Orientação de pagamento ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margem, y, "2. ORIENTAÇÃO DE PAGAMENTO")
    y -= 25

    c.setFont("Helvetica", 10)
    if tipo == "MEI":
        ano_ref = resultado.get("ano_atual", "N/A")
        imposto_fmt = f"{imposto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        texto_pag = (
            "• DAS (Documento de Arrecadação do Simples Nacional): pago mensalmente até o dia 20. "
            "Acesse portal do Simples Nacional ou aplicativo MEI. "
            f"Valor para comércio/indústria (regras vigentes em {ano_ref}): R$ {imposto_fmt}."
        )
    else:
        texto_pag = (
            "• Como autônomo (CPF): utilize o carnê-leão ou guias de IR. "
            "Para rendimentos até o teto do Simples, consulte o DARF ou guia de recolhimento. "
            "Consulte um contador para enquadramento ideal."
        )
    y = _quebrar_texto(c, texto_pag, margem + 20, y, largura - 20)
    y -= 20

    # --- Resumo fiscal ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margem, y, "3. RESUMO FISCAL")
    y -= 25

    c.setFont("Helvetica", 10)
    fat_anual = fat * 12
    imposto_anual = imposto * 12
    c.drawString(margem + 20, y, f"Faturamento anual projetado: R$ {fat_anual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    y -= 18
    c.drawString(margem + 20, y, f"Imposto anual projetado: R$ {imposto_anual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    y -= 25

    # Alertas
    alertas = resultado.get("alertas", [])
    if alertas:
        c.drawString(margem + 20, y, "Alertas:")
        y -= 18
        for a in alertas:
            y = _quebrar_texto(c, f"⚠ {a}", margem + 30, y, largura - 30)
            y -= 4
        y -= 10

    # --- Insight estratégico ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margem, y, "4. INSIGHT ESTRATÉGICO")
    y -= 25

    c.setFont("Helvetica", 10)
    insight = (
        "Este relatório foi gerado em segundos pela nossa plataforma. "
        "Milhões de pessoas buscam 'quanto MEI paga de imposto' e 'quanto pagar de imposto autônomo' — "
        "aqui você tem a resposta com cálculo detalhado e orientação de pagamento. "
        "Guarde este PDF para sua declaração ou planejamento fiscal."
    )
    y = _quebrar_texto(c, insight, margem + 20, y, largura - 20)
    y -= 30

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(margem, 40, "Gerado por SaaS Fiscal Inteligente • Consulte um contador para decisões oficiais.")
    c.save()
    buffer.seek(0)
    return buffer


def gerar_pdf_relatorio(relatorio: dict) -> BytesIO:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    y = 800

    c.drawString(100, y, "Relatório Tributário")
    y -= 40

    c.drawString(100, y, f"Empresa ID: {relatorio.get('empresa_id')}")
    y -= 30

    valor = relatorio.get("potencial_recuperacao", {}).get("valor_estimado", 0)
    c.drawString(100, y, f"Potencial de recuperação: R$ {valor}")
    y -= 30

    dec = relatorio.get("decomposicao_impacto") or {}
    if dec:
        vr = dec.get("valor_recuperavel_real")
        ve = dec.get("valor_estimado")
        na = dec.get("normalizacoes_aplicadas")
        c.drawString(100, y, f"Recuperável (base documental): R$ {vr}")
        y -= 20
        c.drawString(100, y, f"Componente estimado: R$ {ve}")
        y -= 20
        if na is not None:
            c.drawString(100, y, f"Normalizações aplicadas: {na}")
            y -= 24

    flags = relatorio.get("context_flags") or {}
    if flags:
        c.setFont("Helvetica-Oblique", 9)
        avisos = []
        if flags.get("dados_incompletos"):
            avisos.append("dados parcialmente completos")
        if flags.get("usa_estimativa"):
            avisos.append("inclui estimativas")
        if flags.get("base_presumida"):
            avisos.append("base presumida aplicável")
        if flags.get("valores_normalizados"):
            avisos.append("valores exibidos em escala normalizada")
        if avisos:
            c.drawString(100, y, "Rastreabilidade: " + "; ".join(avisos))
            y -= 28
        c.setFont("Helvetica", 10)

    score = relatorio.get("score_global")
    c.drawString(100, y, f"Score tributário: {score}")
    y -= 40

    c.drawString(100, y, "Principais oportunidades:")
    y -= 20

    for insight in relatorio.get("insights", []):
        c.drawString(120, y, f"- {insight}")
        y -= 20

    c.save()
    buffer.seek(0)

    return buffer


def gerar_pdf_memorial(contexto: dict) -> BytesIO:
    """
    Gera o Memorial de Cálculo L2 — documento auditável com embasamento legal.

    Entrada: contexto de coletar_contexto_memorial()
    """
    from datetime import datetime

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    margem = 50
    largura = w - 2 * margem

    rel = contexto.get("relatorio", {})
    ts_geracao = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    rel_id = rel.get("id")
    fp = (rel.get("fingerprint") or "").strip()
    sha_rodape = f"SHA: {fp[:16]}..." if fp else "SHA: —"

    def desenhar_rodape_memorial():
        linha_rodape = f"ID: {rel_id} | {ts_geracao} | {sha_rodape}"
        c.saveState()
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#808080"))
        c.drawString(margem, 32, linha_rodape)
        c.restoreState()

    def nova_pagina():
        desenhar_rodape_memorial()
        c.showPage()
        return h - 50

    def linha(y, espaco=14):
        return y - espaco

    insights = contexto.get("insights", [])
    alertas = contexto.get("alertas", [])
    referencias = contexto.get("referencias_legais", [])
    ref_map = {r["codigo"]: r for r in referencias}

    y = h - 50

    # === CABEÇALHO ===
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margem, y, "MEMORIAL DE CÁLCULO TRIBUTÁRIO")
    y = linha(y, 25)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margem, y, "Plataforma de Inteligência Tributária Soberana L2")
    y = linha(y, 20)
    c.setFont("Helvetica", 9)
    c.drawString(
        margem,
        y,
        f"Relatório ID: {rel.get('id')} | Empresa ID: {rel.get('empresa_id')} | Gerado: {ts_geracao}",
    )
    y = linha(y, 18)
    c.drawString(
        margem,
        y,
        f"Tipo de análise: {rel.get('analysis_type')} | Status: {rel.get('status')} | Score: {rel.get('score_resultante')}",
    )
    y = linha(y, 25)

    # === SECÇÃO 1 — RESUMO EXECUTIVO ===
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margem, y, "1. RESUMO EXECUTIVO")
    y = linha(y, 20)
    c.setFont("Helvetica", 10)
    total_recuperavel = sum(
        float(i.get("valor_estimado") or 0) for i in insights if i.get("impacto") in ("alto", "medio")
    )
    total_alertas_criticos = len([a for a in alertas if a.get("nivel") == "critico"])
    c.drawString(
        margem + 20,
        y,
        f"Total recuperável estimado: R$ {total_recuperavel:,.2f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", "."),
    )
    y = linha(y)
    c.drawString(
        margem + 20,
        y,
        f"Total de insights: {len(insights)} | Alertas críticos: {total_alertas_criticos}",
    )
    y = linha(y, 25)

    # === SECÇÃO 2 — CÁLCULOS E FUNDAMENTOS LEGAIS ===
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margem, y, "2. CÁLCULOS E FUNDAMENTOS LEGAIS")
    y = linha(y, 20)

    for i, insight in enumerate(insights, 1):
        if y < 120:
            y = nova_pagina()
        tipo = insight.get("tipo", "INSIGHT_GENERICO")
        valor = float(insight.get("valor_estimado") or 0)
        ref = ref_map.get(tipo)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(margem + 10, y, f"{i}. {tipo}")
        y = linha(y)
        c.setFont("Helvetica", 9)
        if insight.get("descricao"):
            y = _quebrar_texto(c, f"Descrição: {insight['descricao']}", margem + 20, y, largura - 20)
        c.drawString(
            margem + 20,
            y,
            f"Valor estimado: R$ {valor:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
            + f" | Impacto: {insight.get('impacto', 'N/A')}",
        )
        y = linha(y)
        if ref:
            c.setFont("Helvetica-Oblique", 9)
            y = _quebrar_texto(c, f"Fundamento: {ref['fundamento']}", margem + 20, y, largura - 20)
            if ref.get("fonte_url"):
                y = _quebrar_texto(c, f"Fonte: {ref['fonte_url']}", margem + 20, y, largura - 20)
        else:
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(margem + 20, y, "Fundamento: base normativa em actualização.")
            y = linha(y)
        c.setFont("Helvetica", 9)
        y = linha(y, 8)

    # === SECÇÃO 3 — ALERTAS ===
    if alertas:
        if y < 150:
            y = nova_pagina()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margem, y, "3. ALERTAS DO SISTEMA")
        y = linha(y, 20)
        for a in alertas:
            if y < 80:
                y = nova_pagina()
            c.setFont("Helvetica-Bold", 9)
            c.drawString(margem + 10, y, f"[{a.get('nivel','').upper()}] {a.get('tipo')}")
            y = linha(y)
            c.setFont("Helvetica", 9)
            if a.get("descricao"):
                y = _quebrar_texto(c, a["descricao"], margem + 20, y, largura - 20)
            y = linha(y, 6)

    # === DISCLAIMER ===
    if y < 80:
        y = nova_pagina()
    y = 88
    c.setFont("Helvetica-Oblique", 8)
    disclaimer = (
        "Este Memorial de Cálculo é um relatório de inteligência fiscal computacional para fins de auditoria interna. "
        "Não substitui declaração acessória assinada por profissional habilitado (CRC). "
        "Plataforma Soberana L2 — Motor Fiscal Soberano."
    )
    y = _quebrar_texto(c, disclaimer, margem, y, largura)

    desenhar_rodape_memorial()
    c.save()
    buffer.seek(0)
    return buffer
