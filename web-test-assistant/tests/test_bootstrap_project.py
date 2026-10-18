import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "scripts" / "bootstrap_project.py"
    spec = importlib.util.spec_from_file_location("bootstrap_project", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


bootstrap_project = load_module()


class FakeRunner:
    def __init__(self, failures=None):
        self.calls = []
        self.failures = failures or {}

    def __call__(self, argv, cwd, env):
        argv = tuple(argv)
        self.calls.append({"argv": argv, "cwd": Path(cwd), "env": dict(env)})
        if argv in self.failures:
            return bootstrap_project.CommandResult(1, "", self.failures[argv])
        if argv == ("node", "--version"):
            return bootstrap_project.CommandResult(0, "v22.12.0\n", "")
        if argv[-1:] == ("--version",):
            return bootstrap_project.CommandResult(0, "Version 1.56.1\n", "")
        return bootstrap_project.CommandResult(0, "ok\n", "")


class BootstrapProjectTests(unittest.TestCase):
    def test_missing_playwright_is_installed_in_npm_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
            (project / "package-lock.json").write_text("{}", encoding="utf-8")
            runner = FakeRunner()

            result = bootstrap_project.bootstrap(project, runner=runner)

            commands = [call["argv"] for call in runner.calls]
            self.assertIn(
                ("npm", "install", "--save-dev", "@playwright/test@latest"),
                commands,
            )
            self.assertIn(
                ("npx", "--no-install", "playwright", "cli", "install"),
                commands,
            )
            self.assertIn(
                ("npx", "--no-install", "playwright", "install", "chromium"),
                commands,
            )
            self.assertFalse(any("@playwright/cli" in part for command in commands for part in command))
            playwright_calls = [call for call in runner.calls if "playwright" in call["argv"]]
            self.assertTrue(playwright_calls)
            self.assertTrue(all(call["env"]["PLAYWRIGHT_BROWSERS_PATH"] == "0" for call in playwright_calls))
            self.assertEqual("complete", result["status"])
            self.assertEqual("npm", result["packageManager"])
            self.assertTrue(result["installed"]["playwrightTest"])
            self.assertEqual(
                "node_modules/playwright-core/.local-browsers",
                result["browserPath"],
            )

    def test_existing_dependency_skips_package_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "package.json").write_text(
                json.dumps({"devDependencies": {"@playwright/test": "1.56.1"}}),
                encoding="utf-8",
            )
            runner = FakeRunner()

            result = bootstrap_project.bootstrap(project, runner=runner)

            commands = [call["argv"] for call in runner.calls]
            self.assertNotIn(
                ("npm", "install", "--save-dev", "@playwright/test@latest"),
                commands,
            )
            self.assertFalse(result["installed"]["playwrightTest"])

    def test_declared_dependency_with_missing_node_modules_is_restored(self):
        class MissingModulesRunner(FakeRunner):
            def __init__(self):
                super().__init__()
                self.dependencies_synced = False

            def __call__(self, argv, cwd, env):
                argv = tuple(argv)
                if argv == ("npm", "install"):
                    self.dependencies_synced = True
                if argv == ("npx", "--no-install", "playwright", "--version") and not self.dependencies_synced:
                    self.calls.append({"argv": argv, "cwd": Path(cwd), "env": dict(env)})
                    return bootstrap_project.CommandResult(1, "", "binary missing")
                return super().__call__(argv, cwd, env)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "package.json").write_text(
                json.dumps({"devDependencies": {"@playwright/test": "1.56.1"}}),
                encoding="utf-8",
            )
            runner = MissingModulesRunner()

            result = bootstrap_project.bootstrap(project, runner=runner)

            commands = [call["argv"] for call in runner.calls]
            self.assertIn(("npm", "install"), commands)
            self.assertEqual("complete", result["status"])

    def test_existing_playwright_without_agent_cli_is_upgraded_and_retried(self):
        class MissingCliRunner(FakeRunner):
            def __init__(self):
                super().__init__()
                self.upgraded = False

            def __call__(self, argv, cwd, env):
                argv = tuple(argv)
                install = ("npm", "install", "--save-dev", "@playwright/test@latest")
                if argv == install:
                    self.upgraded = True
                if argv == ("npx", "--no-install", "playwright", "cli", "--help") and not self.upgraded:
                    self.calls.append({"argv": argv, "cwd": Path(cwd), "env": dict(env)})
                    return bootstrap_project.CommandResult(1, "", "unknown command cli")
                return super().__call__(argv, cwd, env)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "package.json").write_text(
                json.dumps({"devDependencies": {"@playwright/test": "1.40.0"}}),
                encoding="utf-8",
            )
            runner = MissingCliRunner()

            result = bootstrap_project.bootstrap(project, runner=runner)

            commands = [call["argv"] for call in runner.calls]
            self.assertIn(
                ("npm", "install", "--save-dev", "@playwright/test@latest"),
                commands,
            )
            self.assertEqual(2, commands.count(("npx", "--no-install", "playwright", "cli", "--help")))
            self.assertTrue(result["installed"]["playwrightTest"])

    def test_pnpm_lock_selects_project_local_pnpm_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
            (project / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'", encoding="utf-8")
            runner = FakeRunner()

            result = bootstrap_project.bootstrap(project, runner=runner)

            commands = [call["argv"] for call in runner.calls]
            self.assertEqual("pnpm", result["packageManager"])
            self.assertIn(
                ("pnpm", "add", "--save-dev", "@playwright/test@latest"),
                commands,
            )
            self.assertIn(
                ("pnpm", "exec", "playwright", "cli", "install"),
                commands,
            )

    def test_install_failure_stops_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
            install = ("npm", "install", "--save-dev", "@playwright/test@latest")
            runner = FakeRunner({install: "registry unavailable"})

            with self.assertRaises(bootstrap_project.BootstrapError) as context:
                bootstrap_project.bootstrap(project, runner=runner)

            self.assertEqual("dependency_install_failed", context.exception.code)
            self.assertEqual(
                {"argv": list(install), "exitCode": 1},
                context.exception.commands[-1],
            )
            commands = [call["argv"] for call in runner.calls]
            self.assertNotIn(
                ("npx", "--no-install", "playwright", "install", "chromium"),
                commands,
            )

    def test_missing_node_stops_before_project_changes(self):
        class MissingNodeRunner(FakeRunner):
            def __call__(self, argv, cwd, env):
                if tuple(argv) == ("node", "--version"):
                    return bootstrap_project.CommandResult(127, "", "node not found")
                return super().__call__(argv, cwd, env)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            runner = MissingNodeRunner()

            with self.assertRaises(bootstrap_project.BootstrapError) as context:
                bootstrap_project.bootstrap(project, runner=runner)

            self.assertEqual("node_missing", context.exception.code)
            self.assertFalse((project / "package.json").exists())

    def test_completed_bootstrap_advances_manifest_to_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "run-manifest.json"
            manifest_path.write_text(
                json.dumps({
                    "stage": "BOOTSTRAP",
                    "status": "running",
                    "bootstrap": {"status": "running"},
                }),
                encoding="utf-8",
            )
            result = {"status": "complete", "packageManager": "npm"}

            bootstrap_project.update_manifest(manifest_path, result)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("INGEST", manifest["stage"])
            self.assertEqual("running", manifest["status"])
            self.assertEqual(result, manifest["bootstrap"])

    def test_failed_bootstrap_marks_manifest_failed_without_advancing(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "run-manifest.json"
            manifest_path.write_text(
                json.dumps({
                    "stage": "BOOTSTRAP",
                    "status": "running",
                    "bootstrap": {"status": "running"},
                }),
                encoding="utf-8",
            )
            result = {
                "status": "failed",
                "error": {"code": "dependency_install_failed"},
            }

            bootstrap_project.update_manifest(manifest_path, result)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("BOOTSTRAP", manifest["stage"])
            self.assertEqual("failed", manifest["status"])
            self.assertEqual(result, manifest["bootstrap"])

    def test_recheck_does_not_reset_an_in_progress_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "run-manifest.json"
            manifest_path.write_text(
                json.dumps({
                    "stage": "RUN",
                    "status": "running",
                    "bootstrap": {"status": "complete"},
                }),
                encoding="utf-8",
            )
            result = {"status": "complete", "packageManager": "pnpm"}

            bootstrap_project.update_manifest(manifest_path, result)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("RUN", manifest["stage"])
            self.assertEqual("running", manifest["status"])
            self.assertEqual(result, manifest["bootstrap"])


if __name__ == "__main__":
    unittest.main()
