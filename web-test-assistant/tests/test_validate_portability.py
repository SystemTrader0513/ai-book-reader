import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "scripts" / "validate_portability.py"
    spec = importlib.util.spec_from_file_location("validate_portability", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


validator = load_module()


class PortabilityValidationTests(unittest.TestCase):
    def test_skill_is_valid_from_shared_agents_project_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / ".agents" / "skills" / "web-test-assistant"
            shutil.copytree(ROOT, installed)

            errors = validator.validate(installed)

            self.assertEqual([], errors)

    def test_missing_host_compatibility_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / "web-test-assistant"
            shutil.copytree(ROOT, installed)
            (installed / "references" / "host-compatibility.md").unlink(missing_ok=True)

            errors = validator.validate(installed)

            self.assertIn("missing_host_compatibility", {error.code for error in errors})

    def test_broken_relative_markdown_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / "web-test-assistant"
            shutil.copytree(ROOT, installed)
            skill_md = installed / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text(encoding="utf-8") + "\n[missing](references/not-there.md)\n",
                encoding="utf-8",
            )

            errors = validator.validate(installed)

            self.assertIn("broken_reference", {error.code for error in errors})

    def test_openai_ui_metadata_is_optional_for_copilot_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / "web-test-assistant"
            shutil.copytree(ROOT, installed)
            shutil.rmtree(installed / "agents")

            errors = validator.validate(installed)

            self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
