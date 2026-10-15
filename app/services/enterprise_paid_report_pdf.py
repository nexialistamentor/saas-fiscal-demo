"""P1-01: PDF da aquisicao Enterprise; so utiliza snapshot validado.

Nao consulta banco, LLM, normativa, documentos actuais ou autorizacao de pagamento.
Nao transforma estimativas em direito de credito nem exibe provenance.
"""
from __future__ import annotations

from io import BytesIO
import math
import re

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


_MARGEM = 48
_LARGURA, _ALTURA = A4
_LIMITE = _LARGURA - 2 * _MARGEM


class EnterprisePaidReportFormatError(ValueError):
    """Dados empresariais adquiridos inconsistentes ou impossiveis de publicar."""


def _texto(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    result = re.sub(r"\s+", " ", value).strip()
    if len(result) > 3000:
        raise EnterprisePaidReportFormatError("P101_CAMPO_TEXTO_EXCESSIVO")
    return result or None


def _valor_estimado(value: object) -> str | None:
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
        return None
    if abs(value) > 10**14:
        return None
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _diagnosticos(value: object, *, origem: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EnterprisePaidReportFormatError(f"P101_{origem}_INVALIDO")
    if len(value) > 10000:
        raise EnterprisePaidReportFormatError("P101_LISTA_EXCESSIVA")
    if any(type(item) is not dict for item in value):
        raise EnterprisePaidReportFormatError(f"P101_{origem}_ITEM_INVALIDO")
    return value


def render_enterprise_acquired_pdf(*, snapshot: dict, empresa_id: int, report_id: int, fingerprint: str) -> BytesIO:
    """Projeta somente campos comerciais seleccionados do snapshot adquirido.

    A entrada ja passou pela validacao do fingerprint na fronteira de aquisicao.
    `insights.empresarial` e deliberadamente omitido: lista bruta nao auditada.
    """
    if type(snapshot) is not dict or type(empresa_id) is not int or type(report_id) is not int:
        raise EnterprisePaidReportFormatError("P101_IDENTIDADE_INVALIDA")
    if type(snapshot.get("empresa_id")) is not int or snapshot["empresa_id"] != empresa_id:
        raise EnterprisePaidReportFormatError("P101_EMPRESA_DIVERGENTE")
    if type(fingerprint) is not str or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise EnterprisePaidReportFormatError("P101_FINGERPRINT_INVALIDO")

    insights = snapshot.get("insights")
    if type(insights) is not dict or "documental" not in insights:
        raise EnterprisePaidReportFormatError("P101_INSIGHTS_ESTRUTURA_INVALIDA")
    documental = _diagnosticos(insights.get("documental"), origem="DOCUMENTAL")
    oportunidades = _diagnosticos(snapshot.get("oportunidades"), origem="OPORTUNIDADES")
    creditos = _diagnosticos(snapshot.get("creditos_detectados"), origem="CREDITOS")

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    y = _ALTURA - _MARGEM
    pagina = 1

    def rodape() -> None:
        pdf.setFont("Helvetica", 7)
        pdf.drawString(_MARGEM, 24, f"Empresa {empresa_id} | Relatorio {report_id} | SHA256 {fingerprint[:16]}... | Pag. {pagina}")

    def nova_pagina() -> None:
        nonlocal y, pagina
        rodape()
        pdf.showPage()
        pagina += 1
        y = _ALTURA - _MARGEM

    def espaco(altura: float) -> None:
        nonlocal y
        if y - altura < 52:
            nova_pagina()
        y -= altura

    def linha(message: str, *, font: str = "Helvetica", size: int = 9, indent: int = 0, gap: int = 4) -> None:
        nonlocal y
        clean = _texto(message)
        if clean is None:
            return
        max_width = _LIMITE - indent
        words = clean.split(" ")
        current = ""

        def escreve(texto: str) -> None:
            nonlocal y
            if y - 13 < 52:
                nova_pagina()
            pdf.setFont(font, size)
            pdf.drawString(_MARGEM + indent, y, texto)
            y -= 13

        for word in words:
            # Evita linhas fora da pagina quando houver tokens longos sem espacos.
            portions = []
            while word and stringWidth(word, font, size) > max_width:
                cut = len(word)
                while cut > 1 and stringWidth(word[:cut], font, size) > max_width:
                    cut -= 1
                portions.append(word[:cut])
                word = word[cut:]
            portions.append(word)
            for i, part in enumerate(portions):
                candidate = f"{current} {part}".strip()
                if current and stringWidth(candidate, font, size) > max_width:
                    escreve(current)
                    current = part
                else:
                    current = candidate
                if i < len(portions) - 1:
                    escreve(current)
                    current = ""
        if current:
            escreve(current)
        espaco(gap)

    def titulo(section: str) -> None:
        espaco(8)
        linha(section, font="Helvetica-Bold", size=12, gap=8)

    def grupo(items: list[dict], heading: str) -> None:
        titulo(heading)
        if not items:
            linha("Nenhum diagnostico disponivel neste grupo.", indent=9)
            return
        for i, item in enumerate(items, 1):
            tipo = _texto(item.get("tipo")) or "DIAGNOSTICO_SEM_TIPO"
            linha(f"{i}. {tipo}", font="Helvetica-Bold", indent=8)
            if _texto(item.get("ncm")):
                linha(f"NCM: {item['ncm']}", indent=16)
            description = _texto(item.get("descricao"))
            if description:
                linha(f"Descricao: {description}", indent=16)
            recommendation = _texto(item.get("recomendacao"))
            if recommendation:
                linha(f"Recomendacao: {recommendation}", indent=16)
            estimate = _valor_estimado(item.get("valor_estimado"))
            if estimate is not None:
                linha(f"Valor informado como estimativa: {estimate} (nao comprova credito recuperavel)", indent=16)
            else:
                linha("Valor: indisponivel / nao comprovado", indent=16)
            espaco(7)

    linha("SOLVERIS - Diagnostico Fiscal Empresarial", font="Helvetica-Bold", size=15, gap=12)
    linha(f"Empresa ID: {empresa_id} | Relatorio adquirido: {report_id}")
    linha("Dados extraidos de um snapshot adquirido e verificado por fingerprint.")

    flags = snapshot.get("context_flags")
    if flags is not None and type(flags) is not dict:
        raise EnterprisePaidReportFormatError("P101_FLAGS_INVALIDAS")
    flags = flags or {}
    doc_flags = flags.get("documental")
    emp_flags = flags.get("empresarial")
    if doc_flags is not None and type(doc_flags) is not dict:
        raise EnterprisePaidReportFormatError("P101_FLAGS_DOCUMENTAIS_INVALIDAS")
    if emp_flags is not None and type(emp_flags) is not dict:
        raise EnterprisePaidReportFormatError("P101_FLAGS_EMPRESARIAIS_INVALIDAS")
    doc_flags, emp_flags = doc_flags or {}, emp_flags or {}
    titulo("Cobertura e limites da analise")
    if doc_flags.get("dados_incompletos") is True or emp_flags.get("dados_incompletos") is True:
        linha("Aviso: dados incompletos; resultados dependem da evidencia disponivel.")
    elif not doc_flags and not emp_flags:
        linha("Cobertura documental indisponivel: nao afirmar analise completa.")
    else:
        linha("Estado de cobertura conforme indicadores do snapshot; nao constitui auditoria oficial.")
    if doc_flags.get("usa_estimativa") is True or emp_flags.get("usa_estimativa") is True:
        linha("Aviso: inclui estimativas; nao constitui comprovacao de credito ou pagamento duplicado.")

    risk = snapshot.get("risco_tributario")
    if type(risk) is dict:
        nivel = _texto(risk.get("nivel_risco"))
        if nivel:
            linha(f"Indicador interno de risco tributario: {nivel}; sujeito a revisao documental.")

    grupo(documental, "1. Evidencias e observacoes documentais")
    grupo(oportunidades, "2. Oportunidades e distorcoes empresariais")
    grupo(creditos, "3. Creditos estimados (NAO confirmados)")
    titulo("Limites e orientacoes")
    linha("A identificacao de ICMS-ST ou diferencas em notas nao prova, por si so, direito de restituicao.")
    linha("Confirmar UF, NCM, data, regime, normativa aplicavel, escrituracao e recolhimentos com profissional habilitado.")
    linha("Nenhum campo foi recalculado; valores e descricoes provem apenas do snapshot adquirido.")
    rodape()
    pdf.save()
    buffer.seek(0)
    return buffer
