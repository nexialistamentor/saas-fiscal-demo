import re
from pathlib import Path


APP_SOURCE = (
    Path(__file__).resolve().parents[1] / "frontend-dashboard" / "src" / "App.jsx"
).read_text(encoding="utf-8")


def _resultado_xml_object_after(branch_condition: str) -> str:
    branch_start = APP_SOURCE.index(branch_condition)
    setter_start = APP_SOURCE.index("setResultadoXML(", branch_start)
    object_start = APP_SOURCE.index("{", setter_start)

    depth = 0
    for position in range(object_start, len(APP_SOURCE)):
        character = APP_SOURCE[position]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return APP_SOURCE[object_start : position + 1]

    raise AssertionError(f"Unclosed setResultadoXML object after {branch_condition!r}")


def _assert_backend_identity_fields(state_object: str, backend_result: str) -> None:
    for field in ("relatorio_id", "request_fingerprint"):
        expected_assignment = (
            rf"\b{field}\s*:\s*{re.escape(backend_result)}(?:\?|)\.{field}\b"
        )
        assert re.search(expected_assignment, state_object), (
            f"setResultadoXML must retain {field} exactly from "
            f"{backend_result}.{field}; local state object was:\n{state_object}"
        )


def test_sync_finished_result_retains_backend_report_id_and_fingerprint() -> None:
    state_object = _resultado_xml_object_after(
        'data.status === "finished" && data.result?.relatorio_id != null'
    )

    _assert_backend_identity_fields(state_object, "data.result")


def test_async_finished_result_retains_backend_report_id_and_fingerprint() -> None:
    state_object = _resultado_xml_object_after('statusData.status === "finished"')

    _assert_backend_identity_fields(state_object, "statusData.result")
