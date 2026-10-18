#!/usr/bin/env python3
"""Install project-local Playwright prerequisites for web-test-assistant."""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import namedtuple
from pathlib import Path


CommandResult = namedtuple("CommandResult", "returncode stdout stderr")
MIN_NODE_MAJOR = 20
BROWSER_PATH = "node_modules/playwright-core/.local-browsers"


class BootstrapError(RuntimeError):
    def __init__(self, code, message, commands=None):
        super().__init__(message)
        self.code = code
        self.commands = list(commands or [])


def run_command(argv, cwd, env):
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(127, "", "executable not found")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _read_package_json(project):
    path = project / "package.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError("invalid_package_json", "package.json is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BootstrapError("invalid_package_json", "package.json must contain a JSON object")
    return payload


def detect_package_manager(project, package_json=None):
    package_json = package_json if package_json is not None else _read_package_json(project)
    declared = str(package_json.get("packageManager", "")).split("@", 1)[0]
    if declared in {"npm", "pnpm", "yarn"}:
        return declared
    if (project / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (project / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _install_command(manager):
    if manager == "pnpm":
        return ["pnpm", "add", "--save-dev", "@playwright/test@latest"]
    if manager == "yarn":
        return ["yarn", "add", "--dev", "@playwright/test@latest"]
    return ["npm", "install", "--save-dev", "@playwright/test@latest"]


def _sync_command(manager):
    return [manager, "install"]


def _playwright_command(manager, *args):
    if manager == "pnpm":
        return ["pnpm", "exec", "playwright", *args]
    if manager == "yarn":
        return ["yarn", "playwright", *args]
    return ["npx", "--no-install", "playwright", *args]


def _has_playwright_test(package_json):
    for field in ("devDependencies", "dependencies", "optionalDependencies"):
        dependencies = package_json.get(field) or {}
        if isinstance(dependencies, dict) and "@playwright/test" in dependencies:
            return True
    return False


def _browser_is_installed(project):
    path = project / BROWSER_PATH
    return path.is_dir() and any(path.iterdir())


def _run_required(runner, argv, project, env, records, error_code):
    result = runner(argv, project, env)
    records.append({"argv": list(argv), "exitCode": result.returncode})
    if result.returncode != 0:
        raise BootstrapError(
            error_code,
            "Command failed: " + " ".join(argv),
            commands=records,
        )
    return result


def _run_probe(runner, argv, project, env, records):
    result = runner(argv, project, env)
    records.append({"argv": list(argv), "exitCode": result.returncode})
    return result


def bootstrap(project, browser="chromium", runner=run_command):
    project = Path(project).resolve()
    if not project.is_dir():
        raise BootstrapError("project_missing", "Project directory does not exist")

    env = dict(os.environ)
    env["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    records = []
    installed = {
        "packageJson": False,
        "projectDependencies": False,
        "playwrightTest": False,
        "cliWorkspace": False,
        "browser": False,
    }

    node = _run_required(
        runner,
        ["node", "--version"],
        project,
        env,
        records,
        "node_missing",
    )
    match = re.search(r"v?(\d+)", node.stdout)
    if not match or int(match.group(1)) < MIN_NODE_MAJOR:
        raise BootstrapError(
            "node_unsupported",
            "Playwright CLI requires Node.js 20 or newer",
        )

    package_json = _read_package_json(project)
    manager = detect_package_manager(project, package_json)
    if not (project / "package.json").exists():
        _run_required(
            runner,
            ["npm", "init", "-y"],
            project,
            env,
            records,
            "package_init_failed",
        )
        installed["packageJson"] = True
        package_json = _read_package_json(project)

    if not _has_playwright_test(package_json):
        _run_required(
            runner,
            _install_command(manager),
            project,
            env,
            records,
            "dependency_install_failed",
        )
        installed["playwrightTest"] = True

    version_command = _playwright_command(manager, "--version")
    version = _run_probe(runner, version_command, project, env, records)
    if version.returncode != 0:
        if _has_playwright_test(package_json) and not installed["playwrightTest"]:
            _run_required(
                runner,
                _sync_command(manager),
                project,
                env,
                records,
                "dependency_install_failed",
            )
            installed["projectDependencies"] = True
            version = _run_required(
                runner,
                version_command,
                project,
                env,
                records,
                "playwright_unavailable",
            )
        else:
            raise BootstrapError("playwright_unavailable", "Project-local Playwright is unavailable after installation")

    cli_help_command = _playwright_command(manager, "cli", "--help")
    cli_help = _run_probe(runner, cli_help_command, project, env, records)
    if cli_help.returncode != 0:
        if installed["playwrightTest"]:
            raise BootstrapError("playwright_cli_unavailable", "Project-local Playwright CLI is unavailable after installation")
        _run_required(
            runner,
            _install_command(manager),
            project,
            env,
            records,
            "dependency_install_failed",
        )
        installed["playwrightTest"] = True
        version = _run_required(
            runner,
            version_command,
            project,
            env,
            records,
            "playwright_unavailable",
        )
        _run_required(
            runner,
            cli_help_command,
            project,
            env,
            records,
            "playwright_cli_unavailable",
        )

    if not (project / ".playwright").exists():
        _run_required(
            runner,
            _playwright_command(manager, "cli", "install"),
            project,
            env,
            records,
            "cli_workspace_install_failed",
        )
        installed["cliWorkspace"] = True

    if not _browser_is_installed(project):
        _run_required(
            runner,
            _playwright_command(manager, "install", browser),
            project,
            env,
            records,
            "browser_install_failed",
        )
        installed["browser"] = True

    return {
        "status": "complete",
        "packageManager": manager,
        "nodeVersion": node.stdout.strip(),
        "playwrightVersion": version.stdout.strip(),
        "cliCommand": _playwright_command(manager, "cli"),
        "browser": browser,
        "browserPath": BROWSER_PATH,
        "hermeticBrowser": True,
        "installed": installed,
        "commands": records,
    }


def update_manifest(manifest_path, result):
    manifest_path = Path(manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError("manifest_update_failed", "Cannot read run manifest") from exc
    if not isinstance(manifest, dict):
        raise BootstrapError("manifest_update_failed", "Run manifest must be a JSON object")

    current_stage = manifest.get("stage")
    manifest["bootstrap"] = result
    if result.get("status") == "complete":
        if current_stage == "BOOTSTRAP":
            manifest["stage"] = "INGEST"
            manifest["status"] = "running"
    else:
        manifest["stage"] = "BOOTSTRAP"
        manifest["status"] = "failed"

    temporary = manifest_path.with_name(manifest_path.name + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(manifest_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--browser", default="chromium")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)

    try:
        result = bootstrap(args.project, browser=args.browser)
        exit_code = 0
    except BootstrapError as exc:
        result = {
            "status": "failed",
            "error": {"code": exc.code, "message": str(exc)},
            "commands": exc.commands,
        }
        exit_code = 2

    if args.manifest:
        try:
            update_manifest(args.manifest, result)
        except BootstrapError as exc:
            result = {"status": "failed", "error": {"code": exc.code, "message": str(exc)}}
            exit_code = 2

    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
