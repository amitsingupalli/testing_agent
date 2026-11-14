"""Tests for the JUnit XML report writer."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from testing_agent.report.junit_report import junit_xml_bytes, write_junit_report


def make_report() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "target": "/tmp/project",
        "verdict": "PASS",
        "results": [
            {
                "runner": "pytest",
                "test_type": "unit",
                "manifest_directory": "",
                "passed": 5,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "duration_ms": 1234,
                "success": True,
                "missing_runner": False,
                "no_tests": False,
                "note": "all good",
                "failures": [],
            },
            {
                "runner": "npm-audit",
                "test_type": "security",
                "manifest_directory": "web",
                "passed": 0,
                "failed": 2,
                "errors": 0,
                "skipped": 0,
                "duration_ms": 500,
                "success": False,
                "missing_runner": False,
                "no_tests": False,
                "note": "audit found issues",
                "failures": [
                    {"name": "lodash", "message": "high: Prototype Pollution"},
                    {"name": "minimist", "message": "low: Prototype Pollution"},
                ],
            },
        ],
        "gate": {"passed": True, "checks": []},
    }


def test_junit_structure_counts() -> None:
    root = ET.fromstring(junit_xml_bytes(make_report()))

    assert root.tag == "testsuites"
    assert root.get("name") == "testing-agent"
    assert root.get("tests") == "7"
    assert root.get("failures") == "2"
    suites = root.findall("testsuite")
    assert len(suites) == 2
    assert suites[0].get("name") == "pytest:unit:."
    assert suites[0].get("tests") == "5"
    assert suites[0].get("time") == "1.234"
    assert suites[1].get("name") == "npm-audit:security:web"
    assert suites[1].get("failures") == "2"


def test_junit_failure_elements() -> None:
    root = ET.fromstring(junit_xml_bytes(make_report()))
    suite = root.findall("testsuite")[1]
    cases = suite.findall("testcase")

    assert len(cases) == 2
    assert cases[0].get("name") == "lodash"
    failure = cases[0].find("failure")
    assert failure is not None
    assert "Prototype Pollution" in (failure.get("message") or "")


def test_junit_success_has_aggregate_case() -> None:
    root = ET.fromstring(junit_xml_bytes(make_report()))
    suite = root.findall("testsuite")[0]
    case = suite.find("testcase")

    assert case is not None
    assert case.get("name") == "pytest unit ok"
    assert case.find("failure") is None
    assert "all good" in (case.findtext("system-out") or "")


def test_junit_no_tests_and_missing_runner_become_skipped() -> None:
    report = make_report()
    report["results"] = [
        {
            "runner": "semgrep",
            "test_type": "security",
            "manifest_directory": "",
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "duration_ms": 0,
            "success": False,
            "missing_runner": False,
            "no_tests": True,
            "note": "skipped",
            "failures": [],
        },
        {
            "runner": "none",
            "test_type": "system",
            "manifest_directory": "go",
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "duration_ms": 0,
            "success": False,
            "missing_runner": True,
            "no_tests": False,
            "note": "no adapter",
            "failures": [],
        },
    ]

    root = ET.fromstring(junit_xml_bytes(report))
    suites = root.findall("testsuite")

    assert root.get("skipped") == "2"
    for suite in suites:
        assert suite.get("tests") == "1"
        assert suite.get("skipped") == "1"
        case = suite.find("testcase")
        assert case is not None
        assert case.find("skipped") is not None


def test_write_junit_report_creates_file(tmp_path) -> None:
    path = write_junit_report(tmp_path, make_report())

    assert path == tmp_path / ".testing-agent" / "junit-report.xml"
    assert path.is_file()
    parsed = ET.parse(path)
    assert parsed.getroot().tag == "testsuites"
