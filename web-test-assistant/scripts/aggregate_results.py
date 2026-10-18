#!/usr/bin/env python3
"""Aggregate Playwright JSON results into a requirement-oriented summary."""

import argparse
import json
import sys
from pathlib import Path


KNOWN_RESULTS = {"passed", "failed", "timedOut", "skipped", "interrupted"}
COUNT_KEYS = ("passed", "failed", "flaky", "skipped", "blocked", "infrastructure_error")


def _iter_specs(suites):
    for suite in suites or []:
        yield from suite.get("specs", []) or []
        yield from _iter_specs(suite.get("suites", []) or [])


def _requirement_ids(test, title):
    ids = [
        item.get("description")
        for item in test.get("annotations", []) or []
        if item.get("type") == "requirement" and item.get("description")
    ]
    return sorted(set(ids))


def _normalize_status(results):
    if not results:
        return "infrastructure_error"
    statuses = [result.get("status") for result in results]
    if any(status not in KNOWN_RESULTS for status in statuses):
        return "infrastructure_error"
    if statuses[-1] == "passed" and any(status in {"failed", "timedOut", "interrupted"} for status in statuses[:-1]):
        return "flaky"
    if statuses[-1] == "passed":
        return "passed"
    if statuses[-1] == "skipped":
        return "skipped"
    if statuses[-1] in {"failed", "timedOut"}:
        return "failed"
    return "infrastructure_error"


def _last_error(results):
    for result in reversed(results):
        errors = result.get("errors") or ([] if not result.get("error") else [result["error"]])
        if errors:
            error = errors[0]
            return str(error.get("message") if isinstance(error, dict) else error)
    return ""


def _evidence(results):
    paths = []
    for result in results:
        for attachment in result.get("attachments", []) or []:
            if attachment.get("path"):
                paths.append(attachment["path"])
    return sorted(set(paths))


def _classification(status, message, mode):
    if status not in {"failed", "infrastructure_error"}:
        return None
    lowered = message.lower()
    if status == "infrastructure_error" or any(token in lowered for token in ("browser closed", "econn", "net::", "worker process")):
        return "environment_failure"
    if any(token in lowered for token in ("strict mode violation", "locator resolved", "waiting for locator", "selector")):
        return "automation_failure"
    return "product_failure" if mode == "requirement-validation" else "unknown"


def _requirement_status(statuses):
    for status in ("failed", "infrastructure_error", "flaky", "passed", "blocked", "skipped"):
        if status in statuses:
            return status
    return "blocked"


def aggregate(results, plan, manifest):
    if not isinstance(results.get("suites"), list):
        raise ValueError("Playwright result is missing suites")
    tests = []
    failures = []
    unmapped = []
    mode = plan.get("mode") or manifest.get("mode") or "requirement-validation"
    for spec in _iter_specs(results.get("suites", [])):
        title = spec.get("title", "Untitled test")
        for test in spec.get("tests", []) or []:
            attempts = test.get("results", []) or []
            status = _normalize_status(attempts)
            requirement_ids = _requirement_ids(test, title)
            message = _last_error(attempts)
            evidence = _evidence(attempts)
            tests.append({
                "title": title,
                "file": spec.get("file", ""),
                "project": test.get("projectName", ""),
                "requirementIds": requirement_ids,
                "status": status,
                "attempts": len(attempts),
                "durationMs": sum(int(attempt.get("duration") or 0) for attempt in attempts),
                "message": message,
                "evidence": evidence,
            })
            if not requirement_ids:
                unmapped.append({"title": title, "file": spec.get("file", "")})
            classification = _classification(status, message, mode)
            if classification:
                for requirement_id in requirement_ids or [""]:
                    failures.append({
                        "requirementId": requirement_id,
                        "title": title,
                        "classification": classification,
                        "message": message,
                        "evidence": evidence,
                    })

    counts = {key: 0 for key in COUNT_KEYS}
    for item in tests:
        counts[item["status"]] += 1
    counts["total"] = len(tests)

    planned_ids = list(plan.get("requirements", []))
    if not planned_ids:
        planned_ids = sorted({rid for scenario in plan.get("scenarios", []) for rid in scenario.get("requirementIds", [])})
    requirement_rows = []
    unexecuted = []
    for requirement_id in planned_ids:
        matched = [item for item in tests if requirement_id in item["requirementIds"]]
        if not matched:
            unexecuted.append(requirement_id)
        requirement_rows.append({
            "requirementId": requirement_id,
            "status": _requirement_status([item["status"] for item in matched]),
            "tests": [item["title"] for item in matched],
        })

    total = counts["total"]
    covered = len(planned_ids) - len(unexecuted)
    risks = []
    if counts["failed"]:
        risks.append(f'{counts["failed"]} test(s) failed')
    if counts["flaky"]:
        risks.append(f'{counts["flaky"]} test(s) are flaky')
    if counts["infrastructure_error"]:
        risks.append(f'{counts["infrastructure_error"]} infrastructure error(s)')
    if unexecuted:
        risks.append(f'{len(unexecuted)} requirement(s) were not executed')
    recommendation = "do-not-release" if counts["failed"] or counts["infrastructure_error"] else ("review" if risks else "release")

    return {
        "schemaVersion": "1.0",
        "run": {
            "runId": manifest.get("runId", ""),
            "environment": manifest.get("environment", ""),
            "baseUrl": manifest.get("baseUrl", ""),
            "mode": mode,
        },
        "counts": counts,
        "rates": {
            "stablePassRate": (counts["passed"] / total) if total else 0.0,
            "requirementCoverageRate": (covered / len(planned_ids)) if planned_ids else 0.0,
        },
        "requirements": requirement_rows,
        "tests": tests,
        "failures": failures,
        "healHistory": manifest.get("healHistory", []),
        "unmappedTests": unmapped,
        "unexecutedRequirements": unexecuted,
        "residualRisks": risks,
        "releaseRecommendation": recommendation,
    }


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON from {path}: {exc}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    args.output.unlink(missing_ok=True)
    try:
        summary = aggregate(_read_json(args.results), _read_json(args.plan), _read_json(args.manifest))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 3 if summary["unmappedTests"] else 0


if __name__ == "__main__":
    sys.exit(main())
