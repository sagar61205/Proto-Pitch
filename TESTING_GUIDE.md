# ProtoPitch — Testing Guide

## Commands

| Command | What it runs | Needs | When |
|---------|--------------|-------|------|
| `make check` | Ruff format and lint, mypy (strict), backend unit and integration tests, frontend type check, ESLint, Vitest, demo-shell tests, API-type drift check | Python, Node | Before every commit |
| `make sandbox-test` | Sandbox isolation suite against the real sandbox image | Docker, `make sandbox-images` | Whenever sandbox or isolation behaviour changes; before completing a milestone that touches it |
| `make e2e` | Playwright smoke test against the real server (API, worker, built interface) | Python, Node, Chromium (`npx playwright install chromium` once) | At milestone gates and in CI |

CI (`.github/workflows/ci.yml`) runs all three on every push and pull request.

Policy (see `DEVELOPMENT_GUIDE.md` §4): before a milestone is declared complete, every
suite listed for it and for earlier milestones must pass. Never weaken or skip a test to
manufacture success. The isolation suite **fails** when Docker or the image is missing; it
does not skip, because an isolation suite that silently did not run proves nothing.

## What the suites cover

| File | Covers |
|------|--------|
| `backend/tests/test_lifecycle.py` | The transition table, approval-gated edges, failure/resume and archive/restore rules; property tests over random walks |
| `backend/tests/test_foundation.py` | Configuration, redaction, artifact store, deterministic workspace snapshots, path confinement, migrations |
| `backend/tests/test_jobs.py` | Step ordering, bounded retries, permanent errors, single-owner leasing, fenced writes, **kill -9 recovery**, **workspace deleted between steps**, deadline, graceful release |
| `backend/tests/test_api.py` | Projects, independence of projects, validation, owner actions, approval gates, complete deletion, resume, server-sent events, auth hook, host-header and cross-site protections |
| `backend/tests/test_no_docker.py` | The platform with Docker absent, including starting the real server process with a minimal environment |
| `backend/tests/test_architecture_rules.py` | Structural rules from `AGENTS.md` |
| `backend/tests/test_sandbox.py` (`docker` marker) | Host environment, planted secret files, other projects' workspaces, network, time / memory / process limits, privileges, read-only mounts, output cap, image digest and lock hash, local preview |
| `frontend/src/**/*.test.ts(x)` | Lifecycle presentation, error rendering, text-not-markup |
| `demo-shell/src/shell.test.tsx` | Manifest validation (disclosures required), panel registry |
| `frontend/e2e/smoke.spec.ts` | Create a project in the browser, watch its job finish, archive and restore, no browser errors |

## Conventions

- Tests never touch the internet. `backend/tests/conftest.py` fails any test that opens a
  non-loopback connection.
- Each test gets its own data directory (`tmp_path`); nothing writes to `data/`.
- Extra job types for tests live in `backend/tests/fixture_jobs.py` and are loaded through
  the registry's extension mechanism, the same way real extensions are.
- Tests that start real processes (`spawn` in `backend/tests/helpers.py`) pass a minimal
  environment: no API keys, tokens or proxy settings from the host.
- Tests state the behaviour they protect in their name. When a test fails, fix the cause.

## Running a subset

```bash
cd backend && uv run pytest tests/test_jobs.py -k recovery
```

```bash
cd backend && uv run pytest -m docker -k network
```

```bash
cd frontend && npx playwright test --trace off
```

## Not yet covered (later milestones)

Golden JD fixtures and evidence integrity (M2); architecture validation and recipe
conformance (M3); platform evaluation, claim validation and dependency workflow (M4A);
scenario end-to-end and differentiation (M5); providers and coding-agent handoff (M4H, M6);
deployment trust boundaries (M7).
