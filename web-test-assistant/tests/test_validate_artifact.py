import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


validator = load_module("validate_artifact", "validate_artifact.py")


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ValidateArtifactTests(unittest.TestCase):
    def test_valid_requirements_artifact_passes(self):
        errors = validator.validate("requirements", fixture("requirements.valid.json"))
        self.assertEqual([], errors)

    def test_unresolved_requirement_is_not_executable(self):
        payload = fixture("requirements.ambiguous.json")
        payload["requirements"][0]["status"] = "ready"
        errors = validator.validate("requirements", payload)
        self.assertIn("missing_expected", {error.code for error in errors})

    def test_literal_secret_is_rejected_without_echoing_it(self):
        payload = fixture("requirements.valid.json")
        secret = "Bearer abcdefghijklmnopqrstuvwxyz123456"
        payload["requirements"][0]["testData"]["token"] = secret
        errors = validator.validate("requirements", payload)
        self.assertIn("literal_secret", {error.code for error in errors})
        self.assertNotIn(secret, " ".join(error.message for error in errors))

    def test_requirement_validation_preserves_expected_behavior(self):
        payload = self._approved_plan()
        payload["scenarios"][0]["observedMismatch"] = {
            "expected": "Dashboard is visible",
            "observed": "Login error is visible"
        }
        errors = validator.validate("test-plan", payload)
        self.assertEqual([], errors)
        self.assertEqual(
            "Dashboard is visible",
            payload["scenarios"][0]["steps"][0]["expected"],
        )

    def test_each_ready_requirement_has_scenario_or_exclusion(self):
        payload = self._approved_plan()
        payload["requirements"] = ["REQ-LOGIN-001", "REQ-LOGIN-002"]
        errors = validator.validate("test-plan", payload)
        self.assertIn("unmapped_requirement", {error.code for error in errors})

    def test_generation_requires_approved_plan(self):
        payload = self._approved_plan()
        payload["review"]["status"] = "pending"
        payload["stage"] = "GENERATE"
        errors = validator.validate("test-plan", payload)
        self.assertIn("plan_not_approved", {error.code for error in errors})

    def test_plan_rejects_unknown_stage(self):
        payload = self._approved_plan()
        payload["stage"] = "MAGIC"
        errors = validator.validate("test-plan", payload)
        self.assertIn("invalid_stage", {error.code for error in errors})

    def test_heal_cannot_change_business_expectation(self):
        payload = fixture("run-manifest.valid.json")
        payload["stage"] = "HEAL"
        payload["healHistory"] = [{
            "testId": "REQ-LOGIN-002",
            "round": 1,
            "changeType": "expected_value_changed",
            "reason": "Make the current page pass",
            "result": "passed"
        }]
        errors = validator.validate("run-manifest", payload)
        self.assertIn("unsafe_heal", {error.code for error in errors})

    def test_manifest_requires_completed_bootstrap_after_bootstrap_stage(self):
        payload = fixture("run-manifest.valid.json")
        payload.pop("bootstrap", None)

        errors = validator.validate("run-manifest", payload)

        self.assertIn("missing_bootstrap", {error.code for error in errors})

    def test_bootstrap_failure_blocks_later_stage(self):
        payload = fixture("run-manifest.valid.json")
        payload["stage"] = "INGEST"
        payload["bootstrap"] = {
            "status": "failed",
            "error": {"code": "dependency_install_failed"},
        }

        errors = validator.validate("run-manifest", payload)

        self.assertIn("bootstrap_incomplete", {error.code for error in errors})

    def test_running_bootstrap_stage_is_valid(self):
        payload = fixture("run-manifest.valid.json")
        payload["stage"] = "BOOTSTRAP"
        payload["status"] = "running"
        payload["bootstrap"] = {"status": "running"}

        errors = validator.validate("run-manifest", payload)

        self.assertNotIn("invalid_stage", {error.code for error in errors})
        self.assertNotIn("bootstrap_incomplete", {error.code for error in errors})

    def test_result_summary_requires_total_count(self):
        payload = {
            "schemaVersion": "1.0",
            "counts": {
                "passed": 1,
                "failed": 0,
                "flaky": 0,
                "skipped": 0,
                "blocked": 0,
                "infrastructure_error": 0
            },
            "requirements": []
        }
        errors = validator.validate("result-summary", payload)
        self.assertIn("invalid_count", {error.code for error in errors})

    @staticmethod
    def _approved_plan():
        return {
            "schemaVersion": "1.0",
            "mode": "requirement-validation",
            "stage": "REVIEW",
            "requirements": ["REQ-LOGIN-001"],
            "excludedRequirements": [],
            "review": {"status": "approved"},
            "scenarios": [{
                "scenarioId": "SCN-LOGIN-001",
                "requirementIds": ["REQ-LOGIN-001"],
                "title": "Valid login",
                "file": "tests/login/valid-login.spec.ts",
                "seed": "tests/seed.spec.ts",
                "steps": [{"action": "Sign in", "expected": "Dashboard is visible"}]
            }]
        }


if __name__ == "__main__":
    unittest.main()
