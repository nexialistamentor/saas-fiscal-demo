"""UX1: isolamento empresarial; funções/condições reais executadas em Node.

Sem browser, rede, compra ou alteração do frontend. Os controlos de montagem
MEI observam os guards JSX existentes; não equivalem a smoke autenticado.
"""
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")


def _block(source, start):
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise AssertionError("Bloco JS incompleto")


def _function(name):
    start = APP.index(f"async function {name}(")
    body = APP.index("{", APP.index(")", start))
    return APP[start:body] + _block(APP, body)


def _expression(name):
    return re.search(rf"const\s+{name}\s*=\s*([\s\S]*?);?\n\n", APP).group(1).strip()


def _render_guard(class_name):
    match = re.search(
        rf'\{{([^{{}}]+?)&&\s*\(\s*<div\s+className="{re.escape(class_name)}"', APP
    )
    assert match, f"Guard JSX não localizado: {class_name}"
    return match.group(1).strip()


def _run(profile, code, *, acquired=False, eligible=False):
    # Contexto residual empresarial deliberadamente válido, mesmo no MEI.
    setup = f'''
const tipoPerfil = {json.dumps(profile)};
const idPerfil = 21;
const empresaId = 21;
const API_BASE = 'https://api.invalid';
const isOpeningMei = false;
const resultadoXML = {{relatorio_id: 501, request_fingerprint: 'a'.repeat(64),
    tax_report_eligibility: {{eligible: {json.dumps(eligible)}}}}};
const taxReportRecoveredCheckoutUrl = null;
const taxReportRecoveredIdempotencyKey = null;
const taxReportRecoveredPaid = false;
const taxReportRecoveryResolvedEmpresaId = 21;
const taxReportAcquisitionId = {701 if acquired else 'null'};
const taxReportAcquisitionEmpresaId = {21 if acquired else 'null'};
const taxReportCheckoutProcessing = false;
const calls = [];
const updates = [];
const window = {{location: {{href: '', search: '?mp_return=success'}}}};
const crypto = {{randomUUID: () => 'same-key'}};
const getToken = () => 'fixture-token';
const storageContext = JSON.stringify({{empresa_id: 21, relatorio_id: 501,
    request_fingerprint: 'a'.repeat(64)}});
const sessionStorage = {{getItem: key => {{calls.push(['storage-read', key]); return storageContext;}},
    setItem: (...args) => calls.push(['storage-write', ...args]), removeItem: () => {{}}}};
const fetch = async (url, options) => {{
    calls.push(['fetch', url, options]);
    return {{ok: true, status: 200, json: async () => url.includes('checkout-recovery')
        ? {{estado:'pending', relatorio_id:501, request_fingerprint:'a'.repeat(64),
            checkout_idempotency_key:'same-key', checkout_url:null}}
        : url.includes('acquisitions') ? {{acquisition_id:701}}
        : {{checkout_url:'https://checkout.invalid/fixture'}}}};
}};
const persistirTaxReportCheckoutIntent = async args => calls.push(['intent', args]);
'''
    setters = set(re.findall(r"\bset[A-Z]\w+", code))
    setup += "\n".join(
        f"const {name} = value => updates.push([{json.dumps(name)}, value]);" for name in setters
    )
    script = setup + "\n(async () => {\n" + code + "\n})().catch(e => {console.error(e); process.exit(1)});"
    run = subprocess.run(["node", "--input-type=module", "-e", script],
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@pytest.mark.parametrize("profile", ["mei", "cpf", None], ids=["mei", "cpf", "ausente"])
def test_paywall_elegibilidade_nao_empresa_falha_fechado(profile):
    actual = _run(profile, f"console.log(JSON.stringify(Boolean({_expression('taxReportPurchasable')}))); ")
    assert actual is False, "CROSS_VERTICAL_PURCHASABLE"


@pytest.mark.parametrize("profile", ["mei", "cpf", None], ids=["mei", "cpf", "ausente"])
def test_checkout_nao_empresa_nao_prepara_intencao_nem_checkout(profile):
    actual = _run(profile, _function('iniciarCheckout') +
                  "\nawait iniciarCheckout({preventDefault(){}}); console.log(JSON.stringify(calls));")
    assert actual == [], "CROSS_VERTICAL_CHECKOUT"


@pytest.mark.parametrize("profile", ["mei", "cpf", None], ids=["mei", "cpf", "ausente"])
def test_recovery_nao_empresa_nao_le_contexto_nem_chama_endpoint(profile):
    actual = _run(profile, _function('recuperarTaxReportCheckoutDoServidor') +
                  "\nawait recuperarTaxReportCheckoutDoServidor(21); console.log(JSON.stringify(calls));")
    assert actual == [], "CROSS_VERTICAL_RECOVERY_STORAGE"


@pytest.mark.parametrize("profile", ["mei", "cpf", None], ids=["mei", "cpf", "ausente"])
def test_acquisition_nao_empresa_nao_consume_storage_nem_compra(profile):
    actual = _run(profile, _function('retomarAquisicaoTaxReport') +
                  "\nawait retomarAquisicaoTaxReport(); console.log(JSON.stringify(calls));")
    assert actual == [], "CROSS_VERTICAL_ACQUISITION_STORAGE"


@pytest.mark.parametrize("profile", ["mei", "cpf", None], ids=["mei", "cpf", "ausente"])
def test_paywall_visual_nao_empresa_ausente_com_resultado_residual(profile):
    code = f"const taxReportPurchasable = ({_expression('taxReportPurchasable')});\n"
    code += f"console.log(JSON.stringify(Boolean({_render_guard('bloqueio-relatorio')})));"
    assert _run(profile, code) is False, "CROSS_VERTICAL_PAYWALL"


@pytest.mark.parametrize("profile", ["mei", "cpf", None], ids=["mei", "cpf", "ausente"])
def test_relatorio_adquirido_nao_empresa_ausente_com_aquisicao_residual(profile):
    code = f"console.log(JSON.stringify(Boolean({_render_guard('bloqueio-relatorio liberado')})));"
    assert _run(profile, code, acquired=True) is False, "CROSS_VERTICAL_ACQUIRED_PDF"


def test_troca_para_nao_empresa_limpa_estados_transitorios_empresariais():
    expected = {
        'setResultadoXML': None, 'setTaxReportRecoveredCheckoutUrl': None,
        'setTaxReportRecoveredIdempotencyKey': None, 'setTaxReportRecoveredPaid': False,
        'setTaxReportRecoveryResolvedEmpresaId': None, 'setTaxReportAcquisitionId': None,
        'setTaxReportAcquisitionEmpresaId': None, 'setCheckoutErro': None,
        'setCheckoutLoading': False,
    }
    effects = []
    for match in re.finditer(r'useEffect\(\(\)\s*=>\s*\{', APP):
        body = _block(APP, APP.index('{', match.start()))
        suffix = APP[match.start() + len(match.group(0)) - 1 + len(body):]
        deps = re.match(r'\s*,\s*\[([^\]]*)\]', suffix)
        if deps and 'tipoPerfil' in deps.group(1) and all(name in body for name in expected):
            effects.append(body)
    assert effects, "CROSS_VERTICAL_STATE_BLEED: nenhum efeito limpa o conjunto de estados ao trocar perfil"
    for profile in ['mei', 'cpf', None]:
        updates = _run(profile, '\n'.join(effects) + '\nconsole.log(JSON.stringify(updates));')
        assert all([name, value] in updates for name, value in expected.items()), 'CROSS_VERTICAL_STATE_BLEED'


def test_empresa_permanece_autorizada_pela_fronteira_vertical():
    # Autoriza a vertical, não a compra: a aquisição depende da resposta backend.
    calls = _run('empresa', _function('retomarAquisicaoTaxReport') +
                 '\nawait retomarAquisicaoTaxReport(); console.log(JSON.stringify(calls));')
    assert any(call[0] == 'fetch' and
               call[1].endswith('/relatorio/empresas/21/acquisitions') for call in calls)


def test_empresa_prepara_intencao_e_checkout_mesma_chave_e_oferta():
    calls = _run('empresa', _function('iniciarCheckout') +
                 '\nawait iniciarCheckout({preventDefault(){}}); console.log(JSON.stringify(calls));',
                 eligible=True)
    assert calls[0][0] == 'intent'
    checkout = next(call for call in calls if call[0] == 'fetch')
    assert checkout[1].endswith('/checkout/one-time')
    assert calls[0][1]['idempotencyKey'] == checkout[2]['headers']['Idempotency-Key']
    assert json.loads(checkout[2]['body']) == {'empresa_id':21,'offer_code':'tax-report-one-time-company'}


def test_empresa_recovery_continua_consultando_endpoint():
    calls = _run('empresa', _function('recuperarTaxReportCheckoutDoServidor') +
                 '\nawait recuperarTaxReportCheckoutDoServidor(21); console.log(JSON.stringify(calls));')
    assert any(c[0] == 'fetch' and c[1].endswith('/relatorio/empresas/21/checkout-recovery') for c in calls)


def test_empresa_retoma_acquisition_e_apresenta_relatorio_adquirido():
    calls = _run('empresa', _function('retomarAquisicaoTaxReport') +
                 '\nawait retomarAquisicaoTaxReport(); console.log(JSON.stringify(calls));')
    assert any(c[0] == 'fetch' and c[1].endswith('/relatorio/empresas/21/acquisitions') for c in calls)
    code = f"console.log(JSON.stringify(Boolean({_render_guard('bloqueio-relatorio liberado')})));"
    assert _run('empresa', code, acquired=True) is True
    assert '<RelatorioPDFButton' in APP


def test_mei_checkout_competencia_e_das_permanecem_separados():
    assert 'useMeiCompetenciaCheckout' in APP
    assert 'await checkoutMei.iniciar()' in APP
    assert 'await emitirDasOficial(idPerfil, periodoApuracao, formatoDas)' in APP
    assert 'tipoPerfil === "mei"' in APP[APP.index('const checkoutMei ='):APP.index('const compraDasAutorizada')]
    service = (ROOT / 'frontend-dashboard/src/services/meiCompetenciaCheckout.js').read_text()
    assert 'tax-report-one-time-company' not in service
    assert '/checkout/one-time' in service


@pytest.mark.parametrize('component', ['MeiHistoricoAlertas','MeiAssistente','MeiReceitasInformadas'])
def test_componentes_mei_permanecem_guardados_por_perfil_mei(component):
    location = APP.index('<' + component)
    guard = APP[APP.rfind('{usuario &&', 0, location):location]
    assert 'tipoPerfil === "mei"' in guard
    assert 'status_empresa === "ativa"' in guard


def test_mei_publico_conferencia_e_upload_autorizado_permanecem():
    assert 'const isMeiPublicJourney = /^\\/mei\\/?$/.test(window.location.pathname)' in APP
    assert '{isExistingMei && (\n          <MeiConferenciaDocumental' in APP
    upload = APP[APP.index('{tipoPerfil !== "cpf" && podeUploadXML && ('):]
    upload = upload[:upload.index('</section>')]
    assert 'multiple' in upload and 'enviarXML(Array.from(e.target.files ?? []))' in upload
    assert 'isExistingMei' in upload
