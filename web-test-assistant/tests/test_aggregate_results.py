import copy
import importlib.util
import json
import tempfile
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


aggregator = load_module("aggregate_results", "aggregate_results.py")


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class AggregateResultsTests(unittest.TestCase):
    def test_aggregate_counts_pass_fail_and_flaky(self):
        summary = aggregator.aggregate(
            fixture("playwright-results.pass-fail-flaky.json"),
            self._plan(),
            fixture("run-manifest.valid.json"),
        )
        self.assertEqual(1, summary["counts"]["passed"])
        self.assertEqual(1, summary["counts"]["failed"])
        self.assertEqual(1, summary["counts"]["flaky"])
        self.assertAlmostEqual(1 / 3, summary["rates"]["stablePassRate"])

    def test_unknown_status_becomes_infrastructure_error(self):
        results = fixture("playwright-results.pass-fail-flaky.json")
        results["suites"][0]["specs"][0]["tests"][0]["results"][0]["status"] = "mystery"
        summary = aggregator.aggregate(results, self._plan(), fixture("run-manifest.valid.json"))
        self.assertEqual(1, summary["counts"]["infrastructure_error"])

    def test_missing_suites_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing suites"):
            aggregator.aggregate({}, self._plan(), fixture("run-manifest.valid.json"))

    def test_unmapped_test_is_reported(self):
        results = fixture("playwright-results.pass-fail-flaky.json")
        results["suites"][0]["specs"][0]["tests"][0]["annotations"] = []
        summary = aggregator.aggregate(results, self._plan(), fixture("run-manifest.valid.json"))
        self.assertEqual(1, len(summary["unmappedTests"]))

    def test_truncated_json_does_not_leave_stale_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            results = directory / "results.json"
            plan = directory / "plan.json"
            manifest = directory / "manifest.json"
            output = directory / "summary.json"
            results.write_text('{"suites": [', encoding="utf-8")
            plan.write_text(json.dumps(self._plan()), encoding="utf-8")
            manifest.write_text(json.dumps(fixture("run-manifest.valid.json")), encoding="utf-8")
            output.write_text('{"stale": true}', encoding="utf-8")
            exit_code = aggregator.main([
                "--results", str(results),
                "--plan", str(plan),
                "--manifest", str(manifest),
                "--output", str(output),
            ])
            self.assertEqual(2, exit_code)
            self.assertFalse(output.exists())

    @staticmethod
    def _plan():
        return {
            "schemaVersion": "1.0",
            "mode": "requirement-validation",
            "scenarios": [
                {"scenarioId": "SCN-1", "requirementIds": ["REQ-LOGIN-001"], "title": "Valid login"},
                {"scenarioId": "SCN-2", "requirementIds": ["REQ-LOGIN-002"], "title": "Invalid login"},
                {"scenarioId": "SCN-3", "requirementIds": ["REQ-PROFILE-001"], "title": "Update profile"}
            ]
        }


if __name__ == "__main__":
    unittest.main()
