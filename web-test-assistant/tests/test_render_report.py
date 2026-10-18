import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


renderer = load_module("render_report", "render_report.py")


class RenderReportTests(unittest.TestCase):
    def test_report_contains_traceability_matrix(self):
        report = renderer.render(self._summary())
        self.assertIn("## 4. 需求覆盖矩阵", report)
        self.assertIn("REQ-LOGIN-002", report)
        self.assertIn("artifacts/test-results/login/trace.zip", report)
        self.assertIn("## 9. 残余风险与发布建议", report)

    def test_report_redacts_sensitive_values(self):
        summary = self._summary()
        summary["failures"][0]["message"] = "Authorization: Bearer secret-token-1234567890"
        report = renderer.render(summary)
        self.assertNotIn("secret-token-1234567890", report)
        self.assertIn("[REDACTED]", report)

    @staticmethod
    def _summary():
        return {
            "schemaVersion": "1.0",
            "run": {"runId": "run-1", "environment": "test", "baseUrl": "https://example.test", "mode": "requirement-validation"},
            "counts": {"total": 2, "passed": 1, "failed": 1, "flaky": 0, "skipped": 0, "blocked": 0, "infrastructure_error": 0},
            "rates": {"stablePassRate": 0.5, "requirementCoverageRate": 1.0},
            "requirements": [
                {"requirementId": "REQ-LOGIN-001", "status": "passed", "tests": ["valid login"]},
                {"requirementId": "REQ-LOGIN-002", "status": "failed", "tests": ["invalid login"]}
            ],
            "tests": [],
            "failures": [{
                "requirementId": "REQ-LOGIN-002",
                "title": "invalid login",
                "classification": "product_failure",
                "message": "Expected invalid credentials message",
                "evidence": ["artifacts/test-results/login/trace.zip"]
            }],
            "healHistory": [],
            "unmappedTests": [],
            "unexecutedRequirements": [],
            "residualRisks": ["One P0 requirement failed"],
            "releaseRecommendation": "do-not-release"
        }


if __name__ == "__main__":
    unittest.main()
