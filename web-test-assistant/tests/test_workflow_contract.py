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


validator = load_module("workflow_validate", "validate_artifact.py")
aggregator = load_module("workflow_aggregate", "aggregate_results.py")
renderer = load_module("workflow_render", "render_report.py")


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class WorkflowContractTests(unittest.TestCase):
    def test_valid_run_artifacts_are_traceable_end_to_end(self):
        requirements = fixture("requirements.valid.json")
        plan = self._plan()
        manifest = fixture("run-manifest.valid.json")
        results = fixture("playwright-results.pass-fail-flaky.json")
        self.assertEqual([], validator.validate("requirements", requirements))
        self.assertEqual([], validator.validate("test-plan", plan))
        summary = aggregator.aggregate(results, plan, manifest)
        report = renderer.render(summary)
        self.assertEqual(3, summary["counts"]["total"])
        self.assertIn("REQ-LOGIN-001", report)
        self.assertTrue(all(item["requirementId"] for item in summary["requirements"]))

    def test_product_mismatch_is_reported_not_healed(self):
        plan = self._plan()
        manifest = fixture("run-manifest.valid.json")
        summary = aggregator.aggregate(
            fixture("playwright-results.pass-fail-flaky.json"),
            plan,
            manifest,
        )
        matches = [item for item in summary["failures"] if item["requirementId"] == "REQ-LOGIN-002"]
        self.assertEqual(1, len(matches))
        failed = matches[0]
        self.assertEqual("product_failure", failed["classification"])
        self.assertEqual([], summary["healHistory"])

    @staticmethod
    def _plan():
        return {
            "schemaVersion": "1.0",
            "mode": "requirement-validation",
            "stage": "REVIEW",
            "requirements": ["REQ-LOGIN-001", "REQ-LOGIN-002", "REQ-PROFILE-001"],
            "excludedRequirements": [],
            "review": {"status": "approved"},
            "scenarios": [
                {"scenarioId": "SCN-1", "requirementIds": ["REQ-LOGIN-001"], "title": "Valid login", "file": "tests/login/valid-login.spec.ts", "seed": "tests/seed.spec.ts", "steps": [{"action": "Sign in", "expected": "Dashboard is visible"}]},
                {"scenarioId": "SCN-2", "requirementIds": ["REQ-LOGIN-002"], "title": "Invalid login", "file": "tests/login/invalid-login.spec.ts", "seed": "tests/seed.spec.ts", "steps": [{"action": "Submit invalid password", "expected": "Invalid credentials message is visible"}]},
                {"scenarioId": "SCN-3", "requirementIds": ["REQ-PROFILE-001"], "title": "Update profile", "file": "tests/profile/update-profile.spec.ts", "seed": "tests/seed.spec.ts", "steps": [{"action": "Save profile", "expected": "Success message is visible"}]}
            ]
        }


if __name__ == "__main__":
    unittest.main()
