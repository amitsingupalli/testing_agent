"""JUnit XML output so CI systems can ingest testing-agent results."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from testing_agent.report.json_report import report_dir


def junit_xml_bytes(report: dict) -> bytes:
    """Render a build_report() dict as a JUnit XML document."""
    generated_at = str(report.get("generated_at", ""))
    suites = ET.Element(
        "testsuites",
        {
            "name": "testing-agent",
            "tests": "0",
            "failures": "0",
            "errors": "0",
            "skipped": "0",
            "time": "0",
        },
    )

    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    total_time = 0.0

    for result in report.get("results", []):
        runner = str(result.get("runner", "unknown"))
        test_type = str(result.get("test_type", "unknown"))
        scope = str(result.get("manifest_directory") or ".")
        suite_name = f"{runner}:{test_type}:{scope}"

        passed = int(result.get("passed", 0) or 0)
        failed = int(result.get("failed", 0) or 0)
        errors = int(result.get("errors", 0) or 0)
        skipped = int(result.get("skipped", 0) or 0)
        duration = float(result.get("duration_ms", 0) or 0) / 1000.0
        no_tests = bool(result.get("no_tests", False))
        missing = bool(result.get("missing_runner", False))

        suite_tests = max(passed + failed + errors + skipped, 1 if (no_tests or missing) else 0)
        if no_tests or missing:
            skipped += 1
            suite_tests = max(suite_tests, 1)

        suite = ET.SubElement(
            suites,
            "testsuite",
            {
                "name": suite_name,
                "tests": str(suite_tests),
                "failures": str(failed),
                "errors": str(errors),
                "skipped": str(skipped),
                "time": f"{duration:.3f}",
                "timestamp": generated_at,
            },
        )

        failures = result.get("failures") or []
        if failures:
            for index, failure in enumerate(failures):
                case = ET.SubElement(
                    suite,
                    "testcase",
                    {
                        "name": str(failure.get("name", f"failure-{index + 1}"))[:200],
                        "classname": suite_name,
                        "time": "0",
                    },
                )
                ET.SubElement(
                    case,
                    "failure",
                    {"message": str(failure.get("message", ""))[:500], "type": "assertion"},
                ).text = str(failure.get("message", ""))[:2000]
        elif result.get("success", False):
            case = ET.SubElement(
                suite,
                "testcase",
                {
                    "name": f"{runner} {test_type} ok",
                    "classname": suite_name,
                    "time": f"{duration:.3f}",
                },
            )
            note = result.get("note")
            if note:
                ET.SubElement(case, "system-out").text = str(note)[:2000]
        else:
            case = ET.SubElement(
                suite,
                "testcase",
                {
                    "name": f"{runner} {test_type} result",
                    "classname": suite_name,
                    "time": f"{duration:.3f}",
                },
            )
            if failed or errors:
                ET.SubElement(
                    case,
                    "failure" if not errors else "error",
                    {"message": str(result.get("note", ""))[:500]},
                ).text = str(result.get("note", ""))[:2000]
            elif no_tests or missing:
                ET.SubElement(case, "skipped")

        total_tests += suite_tests
        total_failures += failed
        total_errors += errors
        total_skipped += skipped
        total_time += duration

    suites.set("tests", str(total_tests))
    suites.set("failures", str(total_failures))
    suites.set("errors", str(total_errors))
    suites.set("skipped", str(total_skipped))
    suites.set("time", f"{total_time:.3f}")

    ET.indent(suites, space="  ")
    return ET.tostring(suites, encoding="utf-8", xml_declaration=True) + b"\n"


def write_junit_report(root: Path | str, report: dict) -> Path:
    """Write junit-report.xml under <root>/.testing-agent/."""
    base = report_dir(Path(root))
    base.mkdir(parents=True, exist_ok=True)
    target = base / "junit-report.xml"
    target.write_bytes(junit_xml_bytes(report))
    return target
