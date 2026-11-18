"""Inventário independente e exclusivamente de leitura dos JUnit V4.2.

Não corrige nem normaliza suites; NÃO substitui a catraca V2 ou aprova GREEN.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


EXPECTED = {
    "baseline": {
        "declared": 4136, "cases": 4102, "gap": 34,
        "outcomes": {"passed": 4074, "failure": 13, "error": 0, "skipped": 15},
        "sha256": "798a14e3a2c6c517dd179559395a12e7fc370cdb49eb2fa3bd674b1599523692",
    },
    "candidate": {
        "declared": 4683, "cases": 4643, "gap": 40,
        "outcomes": {"passed": 4542, "failure": 84, "error": 0, "skipped": 17},
    },
}


class InventoryStop(ValueError):
    pass


def _digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def inspect_junit(path: Path) -> dict:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise InventoryStop("JUNIT_MISSING_OR_INVALID") from exc
    if root.tag not in {"testsuite", "testsuites"}:
        raise InventoryStop("JUNIT_ROOT_INVALID")
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise InventoryStop("JUNIT_NO_SUITES")
    declared = 0
    seen = {}
    breakdown = []
    for suite in suites:
        try:
            suite_declared = int(suite.attrib["tests"])
        except (ValueError, KeyError) as exc:
            raise InventoryStop("JUNIT_SUITE_TESTS_INVALID") from exc
        if suite_declared < 0:
            raise InventoryStop("JUNIT_NEGATIVE_TESTS")
        cases = suite.findall("testcase")
        if suite_declared < len(cases):
            raise InventoryStop("JUNIT_CASES_EXCEED_DECLARATION")
        declared += suite_declared
        for case in cases:
            cls, name = case.get("classname"), case.get("name")
            if not cls or not name:
                raise InventoryStop("JUNIT_IDENTITY_ABSENT")
            key = f"{cls}::{name}"
            if key in seen:
                raise InventoryStop("JUNIT_DUPLICATED_IDENTITY")
            matches = [x for x in ("failure", "error", "skipped")
                       if case.find(x) is not None]
            if len(matches) > 1:
                raise InventoryStop("JUNIT_MULTIPLE_OUTCOMES")
            seen[key] = matches[0] if matches else "passed"
        breakdown.append({
            "name": suite.get("name", ""),
            "declared": suite_declared,
            "cases": len(cases),
            "gap": suite_declared - len(cases),
        })
    outcomes = Counter(seen.values())
    with path.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "declared": declared,
        "cases": len(seen),
        "gap": declared - len(seen),
        "outcomes": {x: outcomes[x] for x in ("passed", "failure", "error", "skipped")},
        "sha256": sha,
        "ids_sha256": _digest(list(seen)),
        "failed_ids_sha256": _digest([key for key, value in seen.items()
                                     if value in ("failure", "error")]),
        "suites": breakdown,
        "_seen": seen,
    }


def verify_expected(label: str, actual: dict) -> None:
    reference = EXPECTED[label]
    for field in ("declared", "cases", "gap", "outcomes"):
        if actual[field] != reference[field]:
            raise InventoryStop(f"JUNIT_{label.upper()}_{field.upper()}_DRIFT")
    if "sha256" in reference and actual["sha256"] != reference["sha256"]:
        raise InventoryStop("JUNIT_BASELINE_DIGEST_DIVERGED")


def compare(repo: Path, baseline: Path, candidate: Path) -> dict:
    old, new = inspect_junit(baseline), inspect_junit(candidate)
    verify_expected("baseline", old)
    verify_expected("candidate", new)
    if set(old["_seen"]) - set(new["_seen"]):
        raise InventoryStop("JUNIT_BASELINE_IDS_MISSING")
    manifest = json.loads(
        (repo / "docs/B03_B04_BASELINE_ESCOPO_TRANSACIONAL_V2_20261118.json")
        .read_text(encoding="utf-8")
    )
    approved = set(manifest["accepted_failure_ids"])
    prior_failed = {key for key, value in old["_seen"].items()
                    if value in ("failure", "error")}
    current_failed = {key for key, value in new["_seen"].items()
                      if value in ("failure", "error")}
    if approved != prior_failed or not approved.issubset(current_failed):
        raise InventoryStop("JUNIT_HISTORICAL_RED_DIVERGED")
    if len(current_failed - approved) != 71:
        raise InventoryStop("JUNIT_NEW_RED_COUNT_DIVERGED")
    return {
        "status": "DIAGNOSTIC_ONLY_NOT_GREEN",
        "baseline": {key: value for key, value in old.items()
                     if key not in ("_seen", "suites")},
        "candidate": {key: value for key, value in new.items()
                      if key not in ("_seen", "suites")},
        "baseline_ids_subconjunto": True,
        "historic_red": len(approved),
        "new_red": len(current_failed - approved),
        "new_red_ids_sha256": _digest(list(current_failed - approved)),
        "testes_duplicados": 0,
        "subtestes_nao_provados_pelo_xml": True,
    }


def _self_test() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as temp:
        base = Path(temp) / "example.xml"
        base.write_text(
            '<testsuites><testsuite name="x" tests="3">'
            '<testcase classname="A" name="um"/>'
            '<testcase classname="A" name="dois"/></testsuite></testsuites>',
            encoding="utf-8",
        )
        result = inspect_junit(base)
        assert (result["declared"], result["cases"], result["gap"]) == (3, 2, 1)

        base.write_text(
            '<testsuite tests="2"><testcase classname="A" name="um"/>'
            '<testcase classname="A" name="um"/></testsuite>', encoding="utf-8",
        )
        try:
            inspect_junit(base)
        except InventoryStop as exc:
            assert str(exc) == "JUNIT_DUPLICATED_IDENTITY"
        else:
            raise AssertionError("MUST_REJECT_DUPLICATES")

        base.write_text(
            '<testsuite tests="1"><testcase classname="A" name="um"/>'
            '<testcase classname="A" name="dois"/></testsuite>', encoding="utf-8",
        )
        try:
            inspect_junit(base)
        except InventoryStop as exc:
            assert str(exc) == "JUNIT_CASES_EXCEED_DECLARATION"
        else:
            raise AssertionError("MUST_REJECT_TRUNCATION_INCONSISTENCY")
    print("V43_JUNIT_INVENTORY_SELFTEST_OK")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--baseline", type=Path,
                        default=Path(".pytest_cache/b03b04_baseline_main.xml"))
    parser.add_argument("--candidate", type=Path,
                        default=Path(".pytest_cache/b03b04_candidate_g12_v42.xml"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    try:
        result = compare(args.repo, args.baseline, args.candidate)
    except (InventoryStop, OSError, KeyError, ValueError, TypeError) as exc:
        print(f"STOP_V43_JUNIT_INVENTORY:{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
