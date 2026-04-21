from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO


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
