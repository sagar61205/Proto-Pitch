# ProtoPitch — Development Guide

Conventions for building the platform described in `ARCHITECTURE.md`. The commands below
exist and are exercised by CI as of M1. See also `CONTRIBUTING.md` and `TESTING_GUIDE.md`.

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

## 2. Setup and commands

Run from the repository root.

```bash
make setup           # backend (uv) and frontend (npm) dependencies
make start           # one command from a fresh clone: build the UI, run API + worker on :8000
make dev             # API with reload, worker, Vite dev server on :5173
make check           # format, lint, types, unit and integration tests, API-type drift
make sandbox-images  # build the hash-pinned sandbox image (needs Docker and network)
make sandbox-lock    # regenerate the sandbox dependency lock after editing requirements.in
make sandbox-test    # sandbox isolation suite (needs Docker and the image)
make e2e             # Playwright smoke test against the real server
make api-types       # regenerate frontend API types from the backend's OpenAPI schema
make probe           # report whether prototype generation is available
```

`docker compose up --build` is an optional containerised run; the Docker socket is mounted
only into the worker service (see comments in `docker-compose.yml`).

Runtime state lives in `data/` (database, artifacts, workspaces) and is git-ignored.
Configuration is `config/*.yaml`, overridden by `PROTOPITCH_<SECTION>__<KEY>` environment
variables (for example `PROTOPITCH_SERVER__PORT=9000`). Unknown keys are rejected. Keys are
read from the environment or OS keychain only; never commit them and never store them in
the database.

Building the sandbox image behind a TLS-inspecting proxy: set `PROTOPITCH_BUILD_NETWORK`,
`PROTOPITCH_BUILD_CA_BUNDLE` and, if the default registry is unreachable,
`PROTOPITCH_BUILD_BASE_IMAGE` (see `scripts/build_sandbox_images.py`).

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
- Provider-specific identifiers appear only in provider adapters (`providers/`), their
  tests and `config/`. Core orchestration, business logic and generated-project logic use
  interfaces and task names only; switching providers is a configuration change.
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

## 4. Testing

### Policy

| Command | When it must be run |
|---------|---------------------|
| `make check` | Before every commit. Fast checks: lint, types, unit tests, frontend type check and unit tests. |
| `make sandbox-test` | Whenever sandbox, resolver, scoring-container, agent-container or any other isolation behaviour changes, and before completing any milestone that touches them. |
| `make e2e` | At the milestone gates that define end-to-end criteria (M4A, M4H, M4B, M5, M6, M7) and in CI. |
| Full applicable regression and security suites | Before declaring any milestone or checkpoint complete: every suite listed for it and for earlier milestones in `IMPLEMENTATION_PLAN.md` ("Cross-cutting test suites"). |

- A milestone is complete only when its acceptance criteria pass; the handoff records which
  commands were run and their results.
- Never weaken, skip, delete or special-case a test to manufacture success. A test that
  cannot pass is a reported failure or blocker, not something to work around.
- The real coding-agent acceptance run (M6.9) is owner-directed and is not part of
  unattended CI.

### Conventions

- Backend tests live in `backend/tests/`, one file per area (see `TESTING_GUIDE.md`).
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
| Job type | Module with `register(registry)`; list it in `jobs.extra_modules` or add it to the built-ins | No |
| Sandbox driver | Implement `SandboxDriver`; pass escape suite | No |
| Deployment target | Implement `DeploymentTarget`; approval-gate tests | No |
| Lifecycle state or transition | Change transition table **and** `ARCHITECTURE.md` §5; owner approval | Yes |

New recipes start as a hand-built working reference project; extract the recipe from it.

## 6. Security

### Execution isolation

Treat all of the following as potentially untrusted execution:

- generated code (model-written, agent-written or imported), including recipe code that
  has been modified;
- dependency installation;
- package lifecycle scripts (install, build and post-install hooks);
- frontend builds;
- test and evaluation commands that come from a generated project.

Rules:

- Run each only inside the isolation boundary assigned to it in `ARCHITECTURE.md` §12:
  the sandbox for generated code, tests and frontend builds; the resolver container for
  dependency resolution; the scoring container for platform evaluation; the agent container
  for automated coding agents. Never run them in the platform process or on the host.
- The dependency resolver must not have access to project source, platform credentials, or
  any network destination other than the configured package index.
- Lifecycle scripts stay disabled and source builds are refused: wheels only for Python,
  `--ignore-scripts` for Node.
- Follow the approved dependency workflow in `ARCHITECTURE.md` §7.10 exactly (hash-pinned
  profile images, policy check, index-only resolution, offline hash-verified install,
  platform-owned Dockerfile). Changing it is an architecture change needing owner approval.
- Critical metrics come from platform-owned evaluators, not from files a generated project
  writes about itself.

### Checklist for every change

- Does it read untrusted text? Then it goes through `PromptEnvelope` or the sanitiser, and
  its output is schema-validated.
- Does it execute anything generated, install anything, or build a frontend? Then it runs
  inside the isolation boundary above, nowhere else.
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
2. Do the work for one work item at a time; run `make check`, plus the suites the testing
   policy requires for what you changed.
3. Update documents affected by the change.
4. Update Status. At the end of a milestone, checkpoint or handoff stage, write the handoff
   from the template in `AGENTS.md` and stop.
