# Web Test Assistant Workflow

## Contents

1. Bootstrap and run directory
2. State transitions
3. Stage protocols
4. Failure classification
5. Playwright configuration
6. Host adaptation

## Bootstrap and run directory

Create the run directory and an initial `run-manifest.json` with stage `BOOTSTRAP`, status `running`, and `bootstrap.status` set to `running`. Then run:

```bash
python3 <skill-dir>/scripts/bootstrap_project.py \
  --project <target-repository> \
  --manifest <run>/run-manifest.json \
  --output <run>/bootstrap.json
```

Do not ask for dependency-install confirmation. The bootstrap is idempotent and detects the project's declared package manager or lockfile. It creates `package.json` with npm when absent, installs missing `@playwright/test@latest` as a project dev dependency, restores missing `node_modules`, upgrades project-local Playwright when the declared version lacks `playwright cli`, initializes `.playwright`, and installs Chromium with `PLAYWRIGHT_BROWSERS_PATH=0`. It never installs `@playwright/cli` globally.

Node.js 20 or newer must already exist. Do not automatically install Node.js or operating-system packages, and never use `--with-deps`. A failed bootstrap keeps stage `BOOTSTRAP`, marks the manifest `failed`, and stops the workflow. A mandatory runtime permission dialog may still be surfaced by the host; continue automatically after the host grants it without adding a separate conversational confirmation gate.

On `RESUME`, rerun bootstrap to detect removed or stale prerequisites. A successful recheck updates `bootstrap` without resetting the current stage.

Create a unique run directory:

```text
.web-test-assistant/runs/<run-id>/
  input/
  bootstrap.json
  requirements.json
  test-plan.json
  test-plan.md
  run-manifest.json
  artifacts/results.json
  artifacts/html-report/
  artifacts/test-results/
  result-summary.json
  test-result.md
```

Use a sortable run ID such as `run-20261017T083000Z`. Do not overwrite another run.

## State transitions

| Stage | Required input | Required output | Next stage |
|---|---|---|---|
| `BOOTSTRAP` | Target repository with Node.js 20+ | Local Playwright dependency, CLI workspace, Chromium, bootstrap record | `INGEST` |
| `INGEST` | Markdown or text requirement | `requirements.json` | `PLAN` |
| `PLAN` | Valid requirements, base URL, seed | `test-plan.json`, `test-plan.md` | `REVIEW` |
| `REVIEW` | Complete plan | Approved/rejected review record | `GENERATE` only if approved |
| `GENERATE` | Approved plan | One Playwright test per scenario | `RUN` |
| `RUN` | Generated suite | JSON/HTML results and evidence | `HEAL` or `REPORT` |
| `HEAL` | Eligible automation failure | Diff record and rerun result | `RUN` or `REPORT` |
| `REPORT` | Plan, manifest, JSON results | Summary JSON and Markdown report | `COMPLETE` |

On failure, keep the current stage, set manifest status to `failed` or `blocked`, and record a concise reason. `RESUME` reads the manifest, validates referenced artifacts, and restarts at the first incomplete stage; it never recreates completed artifacts without an explicit user request.

## BOOTSTRAP

The bootstrap script selects commands as follows:

| Manager | Install Playwright Test | Local Playwright prefix |
|---|---|---|
| npm | `npm install --save-dev @playwright/test@latest` | `npx --no-install playwright` |
| pnpm | `pnpm add --save-dev @playwright/test@latest` | `pnpm exec playwright` |
| yarn | `yarn add --dev @playwright/test@latest` | `yarn playwright` |

Use the `cliCommand` saved in the manifest for subsequent CLI operations. Prefix later Playwright Test and CLI commands with `PLAYWRIGHT_BROWSERS_PATH=0` so they use the project-local browser. Preserve the project's existing Playwright version when `@playwright/test` is already declared.

## INGEST

1. Copy the original requirement file into `input/`.
2. Produce stable requirement IDs, preserving supplied IDs when present.
3. Record title, priority, preconditions, environment/test-data references, steps, expected outcomes, and automation status.
4. Mark missing expected outcomes or material ambiguity `needs_clarification`. Mark inherently unsupported flows `unsupported` with a reason.
5. Validate `requirements.json`; do not plan invalid `ready` requirements.

## PLAN

Prefer an existing seed test or fixture that establishes login, feature flags, and starting navigation. If none exists, propose the smallest seed rather than bypassing application setup.

Explore through the seed:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 PLAYWRIGHT_HTML_OPEN=never <pw> test tests/seed.spec.ts --debug=cli
PLAYWRIGHT_BROWSERS_PATH=0 <pw> cli attach <session-name>
PLAYWRIGHT_BROWSERS_PATH=0 <pw> cli resume
PLAYWRIGHT_BROWSERS_PATH=0 <pw> cli snapshot
```

`<pw>` is the local package-manager prefix saved during bootstrap, such as `npx --no-install playwright`.

Map primary journeys, validation errors, boundaries, persistence, navigation, permissions, and destructive operations. Page observations may refine actions and locators. In `requirement-validation`, they cannot replace expected outcomes; store a discrepancy in `observedMismatch`.

Each scenario contains `scenarioId`, `requirementIds`, title, output file, seed, ordered steps with expected outcomes, priority, and risk tags. Every ready requirement maps to a scenario or an explicit exclusion.

## REVIEW

Render `test-plan.md` for the user. Review:

- requirement coverage and exclusions;
- positive, negative, boundary, permission, and persistence cases;
- destructive or production-affecting actions;
- test-data variables and secret handling;
- unsupported and ambiguous requirements.

Record `pending`, `approved`, or `rejected`, reviewer, timestamp, and notes. Stop until approved. On an interactive host, wait for the user's response. On a non-interactive host, persist the run at `REVIEW`, set `review.status` to `pending`, return the run path, and end the task. A later explicit approval resumes from `GENERATE` without recreating prior artifacts. Follow [host compatibility](host-compatibility.md) for host-specific invocation and permission behavior.

## GENERATE

Generate scenarios sequentially from a fresh seed. Use accessibility snapshots and semantic locators. One scenario produces one test file. Every test includes:

```ts
test('REQ-LOGIN-001 valid user can sign in', {
  tag: ['@REQ-LOGIN-001', '@P0'],
  annotation: { type: 'requirement', description: 'REQ-LOGIN-001' },
}, async ({ page }) => {
  await page.getByLabel('Username').fill(process.env.TEST_USER!);
  await page.getByLabel('Password').fill(process.env.TEST_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});
```

Never embed credential values. Fail generation if a scenario has no assertion.

## RUN

Use Playwright Test, not a sequence of CLI commands, for the formal run. Set `PLAYWRIGHT_BROWSERS_PATH=0`, write all outputs below the current run directory, and preserve the exit code and invocation in the manifest.

## HEAL

Eligible changes: `locator_update`, `wait_strategy`, `fixture_repair`, `setup_repair`. Start a failing test with `--debug=cli`, attach, inspect snapshot/console/network/trace, make one minimal change, and rerun the original test.

For each attempt record test ID, round, change type, evidence, changed file, diff summary, and rerun result. Stop after two attempts or immediately when the required change affects business expectations, deletes an assertion, adds a skip, expands a timeout to hide a performance failure, or changes production data.

## Failure classification

| Classification | Evidence |
|---|---|
| `product_failure` | Business assertion contradicts the requirement |
| `test_failure` | Test logic is wrong but not eligible for automatic Heal |
| `environment_failure` | App unavailable, browser crash, network/fixture dependency unavailable |
| `automation_failure` | Stale locator, invalid wait, setup/fixture automation defect |
| `unknown` | Evidence is insufficient or conflicting |

## Playwright configuration

Merge these values with the target application's existing configuration; do not discard existing projects, fixtures, or reporters:

```ts
reporter: [
  ['list'],
  ['json', { outputFile: '<run>/artifacts/results.json' }],
  ['html', { outputFolder: '<run>/artifacts/html-report', open: 'never' }],
],
use: {
  screenshot: 'only-on-failure',
  trace: 'retain-on-failure',
  video: 'retain-on-failure',
}
```

## REPORT

Run the bundled aggregation and rendering scripts. A malformed JSON result is an infrastructure error. Exit code `3` from the aggregator means one or more tests lack an explicit requirement annotation; fix the mapping before treating the report as complete.

## Host adaptation

All paths in this workflow are relative to the loaded skill directory or target repository. Codex uses `$web-test-assistant`; Copilot CLI uses `/web-test-assistant`. Do not depend on `agents/openai.yaml` outside OpenAI hosts. GitHub Copilot ignores that optional UI metadata and consumes `SKILL.md`, scripts, and references directly.
