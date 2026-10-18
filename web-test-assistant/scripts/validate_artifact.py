#!/usr/bin/env python3
"""Validate web-test-assistant JSON artifacts without third-party packages."""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = "1.0"
KINDS = {"requirements", "test-plan", "run-manifest", "result-summary"}
REQ_STATUSES = {"ready", "needs_clarification", "unsupported"}
RUN_STAGES = {"BOOTSTRAP", "INGEST", "PLAN", "REVIEW", "GENERATE", "RUN", "HEAL", "REPORT", "COMPLETE"}
PLAN_STAGES = {"PLAN", "REVIEW", "GENERATE", "RUN", "HEAL", "REPORT", "COMPLETE"}
SAFE_HEAL_TYPES = {"locator_update", "wait_strategy", "fixture_repair", "setup_repair"}
RESULT_STATUSES = {"passed", "failed", "flaky", "skipped", "blocked", "infrastructure_error"}
SECRET_KEY_RE = re.compile(r"password|passwd|secret|token|authorization|cookie|card", re.I)
SECRET_VALUE_RES = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{12,}", re.I),
    re.compile(r"(?:password|passwd|secret|token)\s*[:=]\s*[^\s,;]{6,}", re.I),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
]
VARIABLE_RE = re.compile(r"^\$\{[A-Z][A-Z0-9_]*\}$")


@dataclass(frozen=True)
class ValidationError:
    path: str
    code: str
    message: str


def _error(errors, path, code, message):
    errors.append(ValidationError(path=path, code=code, message=message))


def _is_literal_secret(key, value):
    if not isinstance(value, str) or VARIABLE_RE.match(value):
        return False
    return bool(value and SECRET_KEY_RE.search(key)) or any(pattern.search(value) for pattern in SECRET_VALUE_RES)


def _scan_secrets(value, path, errors):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            if _is_literal_secret(str(key), child):
                _error(errors, child_path, "literal_secret", "Sensitive values must use an environment-variable reference")
            else:
                _scan_secrets(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_secrets(child, f"{path}/{index}", errors)
    elif isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_VALUE_RES):
        _error(errors, path, "literal_secret", "Sensitive values must use an environment-variable reference")


def _require_dict(payload, errors):
    if not isinstance(payload, dict):
        _error(errors, "/", "invalid_type", "Artifact must be a JSON object")
        return False
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        _error(errors, "/schemaVersion", "unsupported_schema", f"schemaVersion must be {SCHEMA_VERSION}")
    return True


def _validate_requirements(payload, errors):
    if payload.get("mode") not in {"requirement-validation", "characterization"}:
        _error(errors, "/mode", "invalid_mode", "mode must be requirement-validation or characterization")
    if not isinstance(payload.get("source"), dict):
        _error(errors, "/source", "missing_source", "source is required")
    requirements = payload.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        _error(errors, "/requirements", "missing_requirements", "requirements must be a non-empty array")
        return
    seen = set()
    for index, requirement in enumerate(requirements):
        path = f"/requirements/{index}"
        if not isinstance(requirement, dict):
            _error(errors, path, "invalid_type", "requirement must be an object")
            continue
        requirement_id = requirement.get("requirementId")
        if not isinstance(requirement_id, str) or not requirement_id:
            _error(errors, f"{path}/requirementId", "missing_requirement_id", "requirementId is required")
        elif requirement_id in seen:
            _error(errors, f"{path}/requirementId", "duplicate_requirement_id", "requirementId must be unique")
        seen.add(requirement_id)
        status = requirement.get("status")
        if status not in REQ_STATUSES:
            _error(errors, f"{path}/status", "invalid_status", "invalid requirement status")
        if not requirement.get("title"):
            _error(errors, f"{path}/title", "missing_title", "title is required")
        steps = requirement.get("steps")
        if not isinstance(steps, list) or not steps:
            _error(errors, f"{path}/steps", "missing_steps", "at least one step is required")
            continue
        if status == "ready":
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict) or not str(step.get("expected", "")).strip():
                    _error(errors, f"{path}/steps/{step_index}/expected", "missing_expected", "ready requirements need an observable expected outcome")


def _validate_plan(payload, errors):
    if payload.get("stage") not in PLAN_STAGES:
        _error(errors, "/stage", "invalid_stage", "invalid test-plan stage")
    requirements = payload.get("requirements", [])
    scenarios = payload.get("scenarios", [])
    exclusions = set(payload.get("excludedRequirements", []))
    if not isinstance(requirements, list):
        _error(errors, "/requirements", "invalid_type", "requirements must be an array of requirement IDs")
        requirements = []
    if not isinstance(scenarios, list):
        _error(errors, "/scenarios", "invalid_type", "scenarios must be an array")
        scenarios = []
    mapped = set()
    for index, scenario in enumerate(scenarios):
        path = f"/scenarios/{index}"
        if not isinstance(scenario, dict):
            _error(errors, path, "invalid_type", "scenario must be an object")
            continue
        mapped.update(scenario.get("requirementIds", []))
        steps = scenario.get("steps")
        if not isinstance(steps, list) or not steps:
            _error(errors, f"{path}/steps", "missing_steps", "scenario requires steps")
        else:
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict) or not str(step.get("expected", "")).strip():
                    _error(errors, f"{path}/steps/{step_index}/expected", "missing_expected", "each scenario step requires an expected outcome")
        mismatch = scenario.get("observedMismatch")
        if mismatch is not None and payload.get("mode") == "requirement-validation":
            if not isinstance(mismatch, dict) or not mismatch.get("expected") or not mismatch.get("observed"):
                _error(errors, f"{path}/observedMismatch", "invalid_mismatch", "observedMismatch requires expected and observed")
    for requirement_id in requirements:
        if requirement_id not in mapped and requirement_id not in exclusions:
            _error(errors, "/requirements", "unmapped_requirement", f"Requirement {requirement_id} has no scenario or exclusion")
    if payload.get("stage") in {"GENERATE", "RUN", "HEAL", "REPORT", "COMPLETE"}:
        if (payload.get("review") or {}).get("status") != "approved":
            _error(errors, "/review/status", "plan_not_approved", "generation and later stages require an approved plan")


def _validate_manifest(payload, errors):
    if not payload.get("runId"):
        _error(errors, "/runId", "missing_run_id", "runId is required")
    if payload.get("stage") not in RUN_STAGES:
        _error(errors, "/stage", "invalid_stage", "invalid workflow stage")
    bootstrap = payload.get("bootstrap")
    if not isinstance(bootstrap, dict):
        _error(errors, "/bootstrap", "missing_bootstrap", "bootstrap result is required")
    else:
        bootstrap_status = bootstrap.get("status")
        if bootstrap_status not in {"pending", "running", "complete", "failed"}:
            _error(errors, "/bootstrap/status", "invalid_bootstrap_status", "invalid bootstrap status")
        elif payload.get("stage") != "BOOTSTRAP" and bootstrap_status != "complete":
            _error(errors, "/bootstrap/status", "bootstrap_incomplete", "later stages require a completed bootstrap")
    history = payload.get("healHistory", [])
    if not isinstance(history, list):
        _error(errors, "/healHistory", "invalid_type", "healHistory must be an array")
        return
    rounds = {}
    for index, entry in enumerate(history):
        path = f"/healHistory/{index}"
        if not isinstance(entry, dict):
            _error(errors, path, "invalid_type", "heal entry must be an object")
            continue
        if entry.get("changeType") not in SAFE_HEAL_TYPES:
            _error(errors, f"{path}/changeType", "unsafe_heal", "Heal may only change locators, waits, fixtures, or setup")
        test_id = entry.get("testId")
        rounds[test_id] = rounds.get(test_id, 0) + 1
        if rounds[test_id] > 2:
            _error(errors, path, "heal_limit_exceeded", "A test may be healed at most twice")


def _validate_summary(payload, errors):
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        _error(errors, "/counts", "missing_counts", "counts are required")
    else:
        for status in RESULT_STATUSES | {"total"}:
            if not isinstance(counts.get(status), int) or counts[status] < 0:
                _error(errors, f"/counts/{status}", "invalid_count", "result count must be a non-negative integer")
    if not isinstance(payload.get("requirements"), list):
        _error(errors, "/requirements", "missing_requirements", "requirements summary is required")


def validate(kind, payload):
    errors = []
    if kind not in KINDS:
        return [ValidationError("/", "unknown_artifact_kind", f"Unknown artifact kind: {kind}")]
    if not _require_dict(payload, errors):
        return errors
    _scan_secrets(payload, "", errors)
    if kind == "requirements":
        _validate_requirements(payload, errors)
    elif kind == "test-plan":
        _validate_plan(payload, errors)
    elif kind == "run-manifest":
        _validate_manifest(payload, errors)
    else:
        _validate_summary(payload, errors)
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=sorted(KINDS))
    parser.add_argument("json_path", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"path": "/", "code": "invalid_json", "message": str(exc)}), file=sys.stderr)
        return 2
    errors = validate(args.kind, payload)
    for error in errors:
        print(json.dumps(error.__dict__, ensure_ascii=False), file=sys.stderr)
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
