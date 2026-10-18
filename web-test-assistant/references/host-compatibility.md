# Host Compatibility

Use one project-local copy at `.agents/skills/web-test-assistant/`. Both Codex and GitHub Copilot discover that location. Do not maintain a second `.github/skills` copy because duplicate skill names can drift or shadow each other.

## Invocation

| Host | Explicit invocation |
|---|---|
| Codex | `$web-test-assistant` |
| GitHub Copilot CLI | `/web-test-assistant` |
| Copilot App, IDE Agent Mode, Cloud Agent | Name `web-test-assistant` in the prompt or allow description-based selection |

Resolve `<skill-dir>` as the directory containing the loaded `SKILL.md`. Resolve every bundled script and reference from that directory; never substitute an author-machine absolute path. Invoke scripts through an available Python 3 interpreter rather than relying on executable bits.

## Review handoff

Interactive hosts may remain active at `REVIEW` while the user inspects `test-plan.md`. A non-interactive host, including Copilot Cloud Agent, must persist the plan and manifest, set `review.status` to `pending`, leave the run at `REVIEW`, and finish the current task with the exact resume path. It must not generate tests in that task.

A later task may continue only when the user explicitly approves the stored plan. Reload and validate the existing artifacts, record `review.status: approved`, and resume at `GENERATE`; do not rebuild completed stages.

Example follow-up:

```text
/web-test-assistant Resume .web-test-assistant/runs/<run-id>.
I approve the stored test plan; continue from GENERATE.
```

## Permissions and cloud environments

Automatic project bootstrap does not add a conversational confirmation gate. Host-enforced shell, write, or network permissions remain authoritative. Do not add or request a blanket `allowed-tools: shell`; if Copilot blocks a command, report the exact blocked command and resume after the host grants narrowly scoped access.

Copilot Cloud Agent normally permits public package registries and Playwright browser download hosts. If private registries or organization resources prevent bootstrap, leave the run failed at `BOOTSTRAP` and recommend repository-managed Copilot setup steps. Do not create or change `.github/workflows/copilot-setup-steps.yml` unless the user requests that repository configuration.
