"""UX2.3 TEST-ONLY: decisão backend consumida sem autoridade fiscal no browser.

Executa funções, expressões e guards JSX reais em Node com fetch/timers/storage
locais. Não monta React nem equivale a smoke de browser. Nenhuma rede/compra.
Os três estados visuais são observados pelos guards de diagnóstico e paywall,
sem impor nomes, texto, CSS ou design novo.
"""
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
ABSENT = "__projection_absent__"
FAIL_CLOSED = [
    ("ausente", ABSENT), ("null", None), ("objeto-vazio", {}),
    ("numero", {"eligible": 1}), ("string", {"eligible": "true"}),
    ("valor-null", {"eligible": None}), ("false", {"eligible": False}),
]


def _block(start):
    depth = 0
    for i in range(start, len(APP)):
        if APP[i] == "{": depth += 1
        elif APP[i] == "}":
            depth -= 1
            if depth == 0: return APP[start:i + 1]
    raise AssertionError("JS_BLOCK_NOT_FOUND")


def _function(name):
    start = APP.index(f"async function {name}(")
    body = APP.index("{", APP.index(")", start))
    return APP[start:body] + _block(body)


def _expression(name):
    match = re.search(rf"const\s+{name}\s*=\s*([\s\S]*?);?\n\n", APP)
    assert match, "JS_EXPRESSION_NOT_FOUND: " + name
    return match.group(1).strip()


def _guard(class_name):
    match = re.search(rf'\{{([^{{}}]+?)&&\s*\(\s*<div\s+className="{re.escape(class_name)}"', APP)
    assert match, "JSX_GUARD_NOT_FOUND: " + class_name
    return match.group(1).strip()


def _diagnostic_guard():
    match = re.search(r'\{([^{}]+?)&&\s*\(\s*<div[^>]*>\s*<h3>Análise concluída</h3>', APP)
    assert match, "DIAGNOSTIC_GUARD_NOT_FOUND"
    return match.group(1).strip()


def _report(projection=ABSENT, **changes):
    result = {"relatorio_id": 501, "request_fingerprint": "a" * 64, "tem_resultado": True}
    if projection != ABSENT: result["tax_report_eligibility"] = projection
    result.update(changes)
    return result


def _node(code):
    script = "(async () => {\n" + code + "\n})().catch(e => { console.error(e); process.exit(1); });"
    run = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=False)
    assert run.returncode == 0, "NODE_HARNESS_ERROR: " + run.stderr
    return json.loads(run.stdout)


def _state(profile, result, *, checkout=False):
    function = _function("iniciarCheckout") if checkout else ""
    code = f'''
const tipoPerfil = {json.dumps(profile)};
const resultadoXML = {json.dumps(result)};
const idPerfil = 21;
const API_BASE = 'https://api.invalid';
const data = {{consulta_paga:false, restituicao_st:999999, impacto_financeiro:999999}};
const taxReportAcquisitionId = null;
const taxReportAcquisitionEmpresaId = null;
const taxReportCheckoutProcessing = false;
const taxReportRecoveryResolvedEmpresaId = 21;
const taxReportRecoveredCheckoutUrl = null;
const taxReportRecoveredIdempotencyKey = null;
const calls = [];
const updates = [];
const window = {{location:{{href:''}}}};
const crypto = {{randomUUID:()=> 'fixture-key'}};
const getToken = ()=> 'fixture-token';
const sessionStorage = {{setItem:(...args)=>calls.push(['storage',...args])}};
const persistirTaxReportCheckoutIntent = async args=>calls.push(['intent',args]);
const fetch = async (url,options)=>{{calls.push(['fetch',url,options]);return {{ok:true,json:async()=>({{checkout_url:'https://checkout.invalid'}})}};}};
const taxReportPurchasable = ({_expression('taxReportPurchasable')});
'''
    for name in sorted(set(re.findall(r"\bset[A-Z]\w+", function))):
        code += f"const {name} = value=>updates.push([{json.dumps(name)},value]);\n"
    code += function
    if checkout: code += "\nawait iniciarCheckout({preventDefault(){}});\n"
    code += f'''\nconsole.log(JSON.stringify({{
      purchasable:taxReportPurchasable,
      diagnostic:Boolean({_diagnostic_guard()}),
      paywall:Boolean({_guard('bloqueio-relatorio')}),
      acquired:Boolean({_guard('bloqueio-relatorio liberado')}),
      calls,updates,paid:data.consulta_paga,acquisitionId:taxReportAcquisitionId
    }}));'''
    return _node(code)


def _upload(mode, projection):
    function = _function("enviarXML")
    report = _report(projection)
    code = f'''
const idPerfil = 21;
const API_BASE = 'https://api.invalid';
const getToken = ()=> 'fixture-token';
const backend = {json.dumps(report)};
const mode = {json.dumps(mode)};
const writes = [];
const calls = [];
let resultadoXML = null;
class FormData {{append(){{}}}}
const setResultadoXML = value=>{{resultadoXML=typeof value==='function'?value(resultadoXML):value;writes.push(['setResultadoXML',resultadoXML]);}};
const refetch = ()=>calls.push(['refetch']);
const setTimeout = ()=>0;
const setInterval = fn=>{{queueMicrotask(fn);return 1;}};
const clearInterval = ()=>{{}};
const fetch = async (url,options)=>{{
 calls.push([url,options?.method || 'GET']);
 return {{json:async()=>url.includes('/analise/status/')
   ? {{status:'finished',result:backend}}
   : mode==='sync' ? {{status:'finished',result:backend}} : {{job_id:'fixture-job'}}}};
}};
'''
    # Novos setters são observados; não podem fabricar pagamento/aquisição.
    for name in sorted(set(re.findall(r"\bset[A-Z]\w+", function)) - {"setResultadoXML", "setInterval", "setTimeout"}):
        code += f"const {name}=value=>writes.push([{json.dumps(name)},value]);\n"
    code += function + "\nawait enviarXML([{}]); console.log(JSON.stringify({state:resultadoXML,calls,writes,backend}));"
    return _node(code)


@pytest.mark.parametrize("mode", ["sync", "polling"])
@pytest.mark.parametrize("eligible", [False, True])
def test_resultado_xml_preserva_projecao_backend_por_caminho(mode, eligible):
    actual = _upload(mode, {"eligible": eligible})
    state = actual["state"]
    assert state["relatorio_id"] == 501
    assert state["request_fingerprint"] == "a" * 64
    assert state["tem_resultado"] is True
    assert "tax_report_eligibility" in state, mode.upper() + "_ELIGIBILITY_DISCARDED"
    assert state["tax_report_eligibility"] == {"eligible": eligible}
    assert actual["backend"]["tax_report_eligibility"] == {"eligible": eligible}
    assert len(actual["calls"]) == (1 if mode == "sync" else 2)
    assert all(write[0] == "setResultadoXML" for write in actual["writes"]), "UPLOAD_MUST_NOT_GRANT_PAYMENT_AUTHORITY"


@pytest.mark.parametrize("name,projection", FAIL_CLOSED, ids=[v[0] for v in FAIL_CLOSED])
def test_empresa_elegibilidade_ausente_ou_nao_boolean_true_falha_fechado(name, projection):
    actual = _state("empresa", _report(projection))
    assert actual["purchasable"] is False, "BACKEND_ELIGIBILITY_REQUIRED: " + name
    assert actual["paywall"] is False, "INELIGIBLE_PURCHASE_CTA"
    assert actual["diagnostic"] is True, "TECHNICAL_DIAGNOSIS_MUST_REMAIN_AVAILABLE"


def test_empresa_elegivel_pode_apresentar_jornada_sem_conceder_relatorio():
    actual = _state("empresa", _report({"eligible": True}))
    assert actual["purchasable"] is True
    assert actual["diagnostic"] is True
    assert actual["paywall"] is True
    assert actual["acquired"] is False
    assert actual["paid"] is False
    assert actual["acquisitionId"] is None
    assert actual["calls"] == [] and actual["updates"] == []


@pytest.mark.parametrize("changes", [
    {"relatorio_id": None}, {"relatorio_id": 0}, {"relatorio_id": -1},
    {"relatorio_id": "501"}, {"relatorio_id": True}, {"relatorio_id": 1.5},
    {"request_fingerprint": None}, {"request_fingerprint": ""},
    {"request_fingerprint": "A" * 64}, {"request_fingerprint": "a" * 63},
])
def test_eligible_true_nao_substitui_identidade_valida(changes):
    actual = _state("empresa", _report({"eligible": True}, **changes))
    assert actual["purchasable"] is False
    assert actual["paywall"] is False


@pytest.mark.parametrize("profile", ["mei", "cpf", None])
def test_nao_empresa_com_eligible_true_nao_compra_ou_monta_paywall(profile):
    actual = _state(profile, _report({"eligible": True}), checkout=True)
    assert actual["purchasable"] is False
    assert actual["paywall"] is False
    assert actual["acquired"] is False
    assert actual["calls"] == [] and actual["updates"] == [], "CROSS_VERTICAL_CHECKOUT"


@pytest.mark.parametrize("result,diagnostic,paywall", [
    (None, False, False),
    (_report({"eligible": False}), True, False),
    (_report({"eligible": True}), True, True),
], ids=["ANALYSIS_EMPTY", "ANALYSIS_COMPLETE_NOT_ELIGIBLE", "ANALYSIS_COMPLETE_ELIGIBLE"])
def test_tres_estados_empresariais_sem_impor_design(result, diagnostic, paywall):
    actual = _state("empresa", result)
    assert (actual["diagnostic"], actual["paywall"]) == (diagnostic, paywall), "DIAGNOSIS_AND_COMMERCE_MUST_BE_DISTINCT"


def test_browser_nao_recalcula_f1_nem_chama_agent_para_elegibilidade():
    decision = _expression("taxReportPurchasable")
    checkout = _function("iniciarCheckout")
    for token in ("creditos_detectados", "CREDITO_ST_ESTIMADO", "valor_estimado"):
        assert token not in decision + checkout, "BROWSER_MUST_NOT_REIMPLEMENT_F1"
    # Expressão é executada sem agent, LLM, fetch ou helpers de autorização.
    assert not re.search(r"\b(?:fetch|agent\w*|llm\w*|openai|gemini|claude)\s*\(", decision, re.I)
    actual = _state("empresa", _report({"eligible": True}))
    assert actual["calls"] == []


def test_eligible_true_checkout_ainda_prepara_intent_backend_antes_do_post():
    actual = _state("empresa", _report({"eligible": True}), checkout=True)
    calls = actual["calls"]
    assert calls[0][0] == "intent", "ELIGIBILITY_MUST_NOT_BYPASS_F1_INTENT"
    intent = calls[0][1]
    post = next(call for call in calls if call[0] == "fetch")
    assert post[1].endswith("/checkout/one-time")
    assert intent["relatorioId"] == 501 and intent["requestFingerprint"] == "a" * 64
    assert intent["idempotencyKey"] == post[2]["headers"]["Idempotency-Key"]
    assert json.loads(post[2]["body"]) == {"empresa_id": 21, "offer_code": "tax-report-one-time-company"}
    assert actual["paid"] is False and actual["acquisitionId"] is None
    assert all(update[0] in {"setCheckoutLoading", "setCheckoutErro"} for update in actual["updates"])


def test_insights_canonico_objeto_nao_pode_receber_map_de_array():
    renderer = APP[APP.index('<h4>Insights</h4>'):APP.index('</ul>', APP.index('<h4>Insights</h4>'))]
    assert not re.search(r"\(\s*ra\?\.insights\s*\?\?\s*\[\]\s*\)\s*\.map\s*\(", renderer), "CANONICAL_INSIGHTS_OBJECT_IS_NOT_ARRAY"
    # Não impõe lista, texto ou design; congela somente a incompatibilidade.
