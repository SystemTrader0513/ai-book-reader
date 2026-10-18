# Artifact Contracts

All artifacts use `schemaVersion: "1.0"`, UTF-8 JSON, stable IDs, and paths relative to the run directory. Validate them with `scripts/validate_artifact.py`.

## `requirements.json`

- `mode`: `requirement-validation` or `characterization`.
- `source`: original path and input type.
- `requirements[]`: `requirementId`, `title`, `status`, `priority`, `preconditions`, `testData`, and `steps`.
- Requirement status: `ready`, `needs_clarification`, or `unsupported`.
- A `ready` step requires both `action` and observable `expected`.
- Sensitive test data must be `${ENV_VAR}`; literals are invalid.

## `test-plan.json`

- `requirements`: all ready requirement IDs selected for the run.
- `excludedRequirements`: IDs deliberately excluded with reasons in the Markdown plan.
- `scenarios[]`: scenario ID, requirement IDs, title, file, seed, steps, priority, risk tags, and optional `observedMismatch`.
- `review.status`: `pending`, `approved`, or `rejected`.
- Stages `GENERATE` and later require `approved`.

## `run-manifest.json`

- `runId`, `mode`, `baseUrl`, `environment`, `stage`, `status`, `bootstrap`, `review`, `artifacts`, `healHistory`.
- Stages: `BOOTSTRAP`, `INGEST`, `PLAN`, `REVIEW`, `GENERATE`, `RUN`, `HEAL`, `REPORT`, `COMPLETE`.
- `bootstrap` records the selected package manager, local CLI command, Node/Playwright versions, hermetic browser path, install decisions, and command exit codes. Stages after `BOOTSTRAP` require `bootstrap.status: complete`.
- Heal types: `locator_update`, `wait_strategy`, `fixture_repair`, `setup_repair`.
- Maximum two Heal entries per test.

## `result-summary.json`

- Results: `passed`, `failed`, `flaky`, `skipped`, `blocked`, `infrastructure_error`.
- Failure classes: `product_failure`, `test_failure`, `environment_failure`, `automation_failure`, `unknown`.
- `stablePassRate` counts only first-run stable passes. A retry that passes is `flaky`.
- `requirementCoverageRate` counts requirements with at least one explicitly annotated test.
- `unmappedTests` is a contract violation. Do not infer requirement IDs from titles.

The JSON schema files are documentation and interoperability contracts. The bundled validator implements the required runtime subset without third-party dependencies.
