import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEI_HOOK = ROOT / "frontend-dashboard" / "src" / "hooks" / "useMeiDashboard.js"


def test_mei_frontend_uses_only_the_normalized_official_das_contract():
    hook = MEI_HOOK.read_text(encoding="utf-8")

    violations = []

    if "/imposto/calcular" in hook:
        violations.append("MEI ainda usa a rota legada /imposto/calcular")

    official_route = "/imposto/mei/${empresaId}/das"
    if official_route not in hook:
        violations.append(
            "emissão DAS não constrói POST para /imposto/mei/${empresaId}/das"
        )
    elif not re.search(
        rf"fetchAutenticado\([^)]*{re.escape(official_route)}[^)]*,\s*\{{"
        rf"(?:(?!\}}\s*\)).)*?method\s*:\s*['\"]POST['\"]",
        hook,
        re.DOTALL,
    ):
        violations.append("rota oficial DAS não é chamada por POST")

    receives_empresa_id = re.search(
        r"(?:function\s+\w+|(?:const|let)\s+\w+\s*=\s*(?:useCallback\(\s*)?"
        r"(?:async\s*)?)\([^)]*\bempresaId\b[^)]*\)",
        hook,
    )
    validates_integer = re.search(r"Number\.isInteger\(\s*empresaId\s*\)", hook)
    validates_positive = re.search(
        r"empresaId\s*<=\s*0|empresaId\s*>\s*0|0\s*<\s*empresaId", hook
    )
    if not receives_empresa_id:
        violations.append("função de emissão DAS não recebe empresaId")
    if not validates_integer or not validates_positive:
        violations.append(
            "emissão DAS não bloqueia empresaId ausente, nulo, não inteiro ou <= 0"
        )
    elif official_route in hook:
        validation_end = max(validates_integer.end(), validates_positive.end())
        if validation_end > hook.index(official_route):
            violations.append("empresaId é validado somente depois da chamada oficial")

    body_match = re.search(
        r"body\s*:\s*JSON\.stringify\(\s*\{(?P<body>.*?)\}\s*\)",
        hook,
        re.DOTALL,
    )
    if not body_match:
        violations.append("pedido DAS não envia periodo_apuracao e formato")
    else:
        body = body_match.group("body")
        body_keys = set(
            re.findall(r"(?:^|,)\s*([A-Za-z_$][\w$]*)\s*(?=[:,])", body)
        )
        if body_keys != {"periodo_apuracao", "formato"}:
            violations.append(
                "body DAS deve conter somente periodo_apuracao e formato; "
                f"encontrado: {', '.join(sorted(body_keys)) or 'nenhuma chave'}"
            )

    allowed_formats = all(
        re.search(rf"['\"]{value}['\"]", hook)
        for value in ("pdf", "codigo_barras")
    )
    restricts_format = re.search(
        r"(?:includes\(\s*formato\s*\)|formato\s*!==?\s*['\"](?:pdf|codigo_barras)['\"])",
        hook,
    )
    if not allowed_formats or not restricts_format:
        violations.append("formato DAS não está limitado a pdf ou codigo_barras")

    if not all(state in hook for state in ("emitido", "nao_emitido")):
        violations.append("hook não trata os estados normalizados emitido e nao_emitido")

    private_markers = {
        "dados_oficiais",
        "access-token",
        "consumer-secret",
        "certificado",
        ".pfx",
    }
    exposed = sorted(marker for marker in private_markers if marker in hook)
    if exposed:
        violations.append(
            "hook expõe envelope bruto ou material de credencial: "
            + ", ".join(exposed)
        )

    assert not violations, "\n".join(violations)
