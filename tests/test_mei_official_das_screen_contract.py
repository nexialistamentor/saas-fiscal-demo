import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend-dashboard" / "src" / "App.jsx"


def test_mei_screen_consumes_official_das_hook_safely():
    app = APP.read_text(encoding="utf-8")
    violations = []

    legacy_copy = (
        "Dados para simulação MEI",
        "DAS Estimado Anual",
        "Imposto mensal estimado × 12",
    )
    present_legacy_copy = [text for text in legacy_copy if text in app]
    if present_legacy_copy:
        violations.append(
            "tela MEI ainda apresenta simulação/estimativa: "
            + ", ".join(present_legacy_copy)
        )

    if not re.search(
        r"(?:const|let)\s*\{[^}]*\bemitirDasOficial\b[^}]*\}\s*=\s*"
        r"(?:meiResult|useMeiDashboard\s*\()",
        app,
        re.DOTALL,
    ):
        violations.append("App.jsx não obtém emitirDasOficial de useMeiDashboard")

    handlers = list(
        re.finditer(
            r"(?:async\s+function|const|let)\s+([A-Za-z_$][\w$]*)(?:\s*=)?"
            r"(?P<body>.*?emitirDasOficial\s*\([^)]*\).*?)(?=\n\s*(?:async\s+function|"
            r"const|let)\s+[A-Za-z_$]|\n\s*(?:if|return)\s*\(|\Z)",
            app,
            re.DOTALL,
        )
    )
    explicit_handler = next(
        (
            match
            for match in handlers
            if re.search(
                rf"on(?:Click|Submit)\s*=\s*\{{(?:\([^}}]*\)\s*=>\s*)?"
                rf"{re.escape(match.group(1))}\b",
                app,
            )
        ),
        None,
    )
    if explicit_handler is None:
        violations.append(
            "emitirDasOficial deve ser chamado somente por handler ligado a ação explícita"
        )
        handler_body = ""
    else:
        handler_body = explicit_handler.group("body")

    calls = list(re.finditer(r"\bemitirDasOficial\s*\(", app))
    if calls and (explicit_handler is None or len(calls) != 1):
        violations.append("há emissão fora da única ação explícita do utilizador")

    validates_id = (
        re.search(r"Number\.isInteger\(\s*idPerfil\s*\)", handler_body)
        and re.search(r"idPerfil\s*(?:<=\s*0|>\s*0)|0\s*<\s*idPerfil", handler_body)
    )
    if not validates_id:
        violations.append("tela não bloqueia emissão sem idPerfil inteiro positivo")

    month_input = re.search(
        r"<input\b(?=[^>]*\btype\s*=\s*[\"']month[\"'])[^>]*"
        r"\bvalue\s*=\s*\{\s*([A-Za-z_$][\w$]*)\s*\}[^>]*>",
        app,
        re.DOTALL,
    )
    if month_input is None:
        violations.append("tela não exige competência escolhida em campo de mês")
    else:
        competencia = re.escape(month_input.group(1))
        converts_to_yyyymm = re.search(
            rf"{competencia}\s*\.\s*replace\(\s*[\"']-[\"']\s*,\s*[\"'][\"']\s*\)"
            rf"|{competencia}\s*\.\s*split\(\s*[\"']-[\"']\s*\)\s*\.\s*join\(\s*[\"'][\"']\s*\)",
            handler_body,
        )
        required_month = re.search(r"\brequired(?:\s*=\s*\{\s*true\s*\})?\b", month_input.group(0))
        if not required_month or not converts_to_yyyymm:
            violations.append(
                "competência deve ser obrigatória e convertida de YYYY-MM para YYYYMM antes do hook"
            )

    format_select = next(
        (
            match.group(0)
            for match in re.finditer(r"<select\b[\s\S]*?</select>", app)
            if "codigo_barras" in match.group(0) and "pdf" in match.group(0)
        ),
        "",
    )
    format_values = set(
        re.findall(r"<option\s+value\s*=\s*[\"']([^\"']+)[\"']", format_select)
    )
    if not format_select or format_values != {"pdf", "codigo_barras"}:
        violations.append("seletor de formato deve oferecer apenas pdf e codigo_barras")

    visible_states = {
        "emissão em curso": r"emitindo|emiss[aã]o em curso",
        "emitido": r"estado_oficial\s*===?\s*[\"']emitido[\"']",
        "não emitido": r"estado_oficial\s*===?\s*[\"']nao_emitido[\"']",
        "erro sanitizado": r"erro(?:Das|Emissao|Emissão|DAS)",
    }
    missing_states = [
        label for label, pattern in visible_states.items() if not re.search(pattern, app, re.IGNORECASE)
    ]
    if missing_states:
        violations.append("faltam estados visíveis distintos: " + ", ".join(missing_states))

    if not re.search(
        r"estado_oficial\s*===?\s*[\"']nao_emitido[\"'][\s\S]{0,600}"
        r"motivo_oficial",
        app,
    ):
        violations.append("nao_emitido não mostra o motivo normalizado")
    nao_emitido_branch = re.search(
        r"estado_oficial\s*===?\s*[\"']nao_emitido[\"'](?P<body>[\s\S]{0,600})",
        app,
    )
    if nao_emitido_branch and re.search(
        r"JSON\.stringify|Object\.(?:entries|values)|<pre\b|dados_oficiais|messages",
        nao_emitido_branch.group("body"),
    ):
        violations.append("nao_emitido expõe dados brutos além do motivo normalizado")

    pdf_flow = re.search(
        r"formato\w*\s*===?\s*[\"']pdf[\"'][\s\S]{0,1200}pdf_base64"
        r"[\s\S]{0,1200}(?:atob\s*\(|Blob\s*\()[\s\S]{0,1200}"
        r"(?:URL\.createObjectURL\s*\(|download\s*=)",
        app,
    )
    if not pdf_flow:
        violations.append(
            "resultado PDF deve ser convertido para download sem renderizar base64"
        )
    barcode_flow = re.search(
        r"formato\w*\s*===?\s*[\"']codigo_barras[\"'][\s\S]{0,1200}"
        r"codigo_barras\s*\.\s*map\s*\(",
        app,
    )
    if not barcode_flow:
        violations.append(
            "resultado codigo_barras deve apresentar somente os blocos escolhidos"
        )

    if handler_body:
        catch_body = re.search(r"catch\s*\([^)]*\)\s*\{(?P<body>[\s\S]*?)\}", handler_body)
        if (
            catch_body is None
            or re.search(r"\.message\b|JSON\.stringify", catch_body.group("body"))
            or not re.search(r"set[A-Za-z_$]*(?:Erro|Error)\s*\(\s*[\"']", catch_body.group("body"))
        ):
            violations.append("erro de emissão deve ser sanitizado antes de ficar visível")

    forbidden = {
        "dados_oficiais": r"\bdados_oficiais\b",
        "token": r"\b(?:access[_-]?token|consumer[_-]?key|consumer[_-]?secret)\b",
        "certificado": r"\bcertificado\b|\.pfx\b|\.pem\b",
        "credencial oficial": r"\b(?:client[_-]?secret|private[_-]?key|api[_-]?key)\b",
        "mensagem interna": r"\bmessages\b|mensagens?\s+internas?",
        "base64 renderizado": r"(?:src|href)\s*=\s*\{[^}]*pdf_base64|data:application/pdf;base64",
        "envelope oficial bruto": r"JSON\.stringify\s*\([^)]*(?:resultadoDas|respostaDas|dasOficial)",
    }
    exposed = [label for label, pattern in forbidden.items() if re.search(pattern, app, re.IGNORECASE)]
    if exposed:
        violations.append("App.jsx expõe material proibido: " + ", ".join(exposed))

    assert not violations, "\n".join(violations)
