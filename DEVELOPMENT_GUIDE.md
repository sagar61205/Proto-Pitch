# ProtoPitch — Development Guide

Conventions for building the platform described in `ARCHITECTURE.md`. Sections marked
*(from M1)* describe the intended setup; the repository contains documentation only until
the owner authorises M1. Whoever implements M1 must make these commands real and correct
this file where reality differs.

## 1. Prerequisites

| Tool | Version | Needed for |
|------|---------|-----------|
| Python | 3.12 | Backend, worker |
| uv | current | Python dependency and environment management |
| Node.js | 22 LTS | Platform frontend and demo shell |
| Docker | current (Docker Desktop on macOS) | Sandbox. Required only to build, test and preview generated prototypes; not for JD analysis, research or architecture review |
| Git | 2.40+ | Platform and generated-project history |

No model keys, local models or cloud accounts are needed to develop or run the
deterministic pipeline.

## 2. Setup and commands *(from M1)*

```bash
make setup        # uv sync, npm install for frontend and demo-shell
make sandbox-images  # build hash-pinned sandbox profile images (needs Docker and network)
make dev          # API on 127.0.0.1:8000, worker, frontend dev server
make check        # ruff, mypy, pytest, eslint, tsc, vitest — must pass before every commit
make e2e          # Playwright and three-scenario end-to-end tests (needs Docker)
make sandbox-test # sandbox escape suite
```

Runtime state lives in `data/` (database, artifacts, workspaces) and is git-ignored.
Configuration is `config/*.yaml` overridden by `PROTOPITCH_*` environment variables. Keys
are read from the environment or OS keychain only; never commit them and never store them
in the database.

## 3. Code conventions

Backend
- Package layout per `ARCHITECTURE.md` §10. Modules depend inward: `api` → services →
  `domain`; `domain` imports nothing from the rest.
- Cross-module contracts are `typing.Protocol` classes and Pydantic models in `domain/`.
- Full type annotations; mypy strict on `domain`, `jobs`, `sandbox`, `providers`, `security`.
- Database access only through repository classes in `db/`; every schema change has an
  Alembic migration.
- No network call outside `intelligence/research` (through `UrlGuard`), `providers`,
  `deploy` and `scm`. A test enforces this by import and socket checks.
- Structured logging through the platform logger (redaction is applied there); no `print`.
- Errors that the owner must see carry a code, a plain-language message and suggested next
  actions.

Frontend
- TypeScript strict; API types generated from the OpenAPI schema; no hand-written
  duplicates.
- Render all JD, web and model text as text, never as raw HTML.

Data files
- Taxonomies, archetypes, scoring weights, limits and prices are YAML validated by schema
  on load. Changing behaviour through them must not need code changes.

## 4. Testing conventions

- Unit tests sit next to the feature area under `backend/tests/<module>/`.
- Fixtures: JD fixtures in `backend/tests/fixtures/jds/` (Scenarios A–C, adversarial,
  non-English); web pages as saved files — tests never touch the live internet.
- Provider tests use the `mock` adapter. A global test guard fails any test that opens an
  outbound connection.
- Sandbox and end-to-end tests are marked `docker` and run in CI.
- Golden files change only with a reviewed reason stated in the commit message.
- Never delete, skip or loosen a test to make a build pass; fix the cause or raise it.

## 5. Adding things

| To add | Do this | Core change needed |
|--------|---------|--------------------|
| Skill or capability | Edit `taxonomy/*.yaml` | No |
| Technology rule | Add entry with `justified_when` to `taxonomy/technologies.yaml` | No |
| Opportunity archetype | Add YAML under `taxonomy/archetypes/` | No |
| Recipe | New directory with manifest, templates, class; register entry point; pass conformance suite | No |
| Provider | Implement `LLMProvider`; register; document in `MODEL_PROVIDER_GUIDE.md` | No |
| Sandbox driver | Implement `SandboxDriver`; pass escape suite | No |
| Deployment target | Implement `DeploymentTarget`; approval-gate tests | No |
| Lifecycle state or transition | Change transition table **and** `ARCHITECTURE.md` §5; owner approval | Yes |

New recipes start as a hand-built working reference project; extract the recipe from it.

## 6. Security checklist for every change

- Does it read untrusted text? Then it goes through `PromptEnvelope` or the sanitiser, and
  its output is schema-validated.
- Does it execute anything generated? Then it runs through `SandboxDriver`, nowhere else.
- Does it accept work from a coding agent? Then it goes through the import pipeline
  (`ARCHITECTURE.md` §7.8) whatever tool produced it.
- Does it assume a local path or same-host worker? Use the artifact store and job backend.
- Does it have an external side effect or cost? Then it is behind `ApprovalGate` and, for
  model calls, the budget check.
- Does it log? Confirm nothing sensitive bypasses redaction.
- Does it touch files? Confirm paths are confined to the current project's directory.

## 7. Git workflow

- Feature branches; `main` stays releasable. Commit messages state what changed and why.
- Commit messages, code and documents must not name the coding assistant or model that
  produced them.
- Generated projects have their own repositories under `data/workspaces/`; they are never
  committed into the platform repository.

## 8. Session checklist for a coding assistant

1. Read the Status section of `IMPLEMENTATION_PLAN.md`; confirm the work is authorised.
2. Do the work for one work item at a time; run `make check`.
3. Update documents affected by the change.
4. Update Status; at a stage boundary add a handoff-log row and stop.
