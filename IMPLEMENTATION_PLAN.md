# ProtoPitch — Implementation Plan

Read `ARCHITECTURE.md` first. This file is the working plan and the handoff record. Update
the **Status** section at the end of every working session.

---

## Status

| Item | State |
|------|-------|
| Current handoff stage | **H1 complete — stopped at phase boundary, awaiting owner approval** |
| Current milestone | M0 (architecture validation) delivered for review |
| Application code | None. Not authorised yet. |
| Next action | Owner answers decisions D1–D10 below and approves or amends the architecture. Then M1 may start. |

### Handoff stages (which coding model is working)

| Stage | Scope | Model |
|-------|-------|-------|
| H1 | M0: specification review, architecture, plan, handoff documents | Initial planning model |
| H2 | Technically hard components: M1 sandbox and job engine, M3, M4, M6 router | Owner's choice after approval |
| H3 | Routine development, tests, refinements, maintenance: remaining M1, M2, M5, M7, M8 | Owner's choice |

The owner chooses the model for each stage. Never switch models or invoke a more expensive
one without the owner's approval. Stop at each stage boundary and write a handoff summary in
this file.

---

## Decisions awaiting approval

Each has a recommendation. Rationale is in `docs/SPEC_REVIEW.md`.

| ID | Question | Recommendation |
|----|----------|----------------|
| D1 | Is the platform single-user and local-only in v1 (no login, bound to localhost)? | Yes |
| D2 | Demos use one shared manifest-driven demo shell instead of a bespoke frontend per project? | Yes |
| D3 | Cloud default: shared demo host (per spec) or one scale-to-zero service per demo? | Shared host for standard G1/G2 demos, dedicated service otherwise. Revisit after the first three real deployments. |
| D4 | v1 recipe catalogue is the four recipes covering Scenarios A–C? | Yes; forecasting, propensity and NL-to-SQL follow after M5 |
| D5 | Deterministic JD analysis is English-only; other languages need a configured model? | Yes |
| D6 | Outreach is draft-only, contacts are user-entered, and drafts state the demo was built with your own generation platform? | Yes |
| D7 | Seeded experience examples start as `UNVERIFIED` until you confirm each one? | Yes |
| D8 | RAG demo corpora need per-project approval; default to openly licensed or synthetic text when rights are unclear? | Yes |
| D9 | Plan changes: sandbox moves into M1; reference prototypes are hand-built before recipes are extracted? | Yes |
| D10 | Tooling: Python 3.12, uv, Ruff, mypy, pytest, Vitest, Playwright; Docker required for generation? | Yes |

---

## Milestones

Milestone numbers follow specification §25. Each lists dependencies, deliverables,
acceptance criteria (AC) and required tests. A milestone is done when its AC pass in CI and
the documents named in it are updated.

### M0 — Architecture validation (done, pending approval)

Deliverables: `docs/SPEC_REVIEW.md`, `ARCHITECTURE.md`, this plan, `AGENTS.md`,
`DEVELOPMENT_GUIDE.md`.
AC: owner approves, with D1–D10 answered.

### M1 — Foundation

Depends on: M0 approval. Stage: H2 for 1.4–1.5, H3 for the rest.

| # | Work item |
|---|-----------|
| 1.1 | Repository skeleton per ARCHITECTURE §10; uv project; frontend and demo-shell scaffolds; CI workflow (lint, types, tests, frontend build) |
| 1.2 | Configuration loading (`config/*.yaml` + environment), structured logging with redaction |
| 1.3 | Database models and migrations for Project, ProjectVersion, JDDocument, Artifact, Job, Step, Approval, AuditEvent; artifact store (local) |
| 1.4 | Lifecycle state machine with the transition table; job queue, worker, leases, checkpoint resume; SSE log stream |
| 1.5 | Docker sandbox driver, `core` sandbox image, resource limits, escape test suite |
| 1.6 | API: projects CRUD, state transitions, job status. UI: dashboard, new-project form, project page shell |
| 1.7 | Docker Compose for local run; `CONTRIBUTING.md`, `TESTING_GUIDE.md` first versions |

AC:
- Fresh clone starts with one documented command, no keys, no downloads beyond dependencies.
- Creating two projects for the same company yields two independent records and directories.
- Illegal state transitions are rejected with a clear error.
- Killing the worker mid-job and restarting resumes from the last completed step.
- Sandbox tests prove a job cannot read host environment variables, a planted secret file,
  another project's workspace, or reach the network; and that time and memory limits kill it.

Tests: state-machine property tests; job recovery integration test; sandbox escape tests;
API tests; one Playwright smoke test.

### M2 — Intelligence

Depends on: M1. Stage: H3 (taxonomy design review by H2 model if available).

| # | Work item |
|---|-----------|
| 2.1 | Taxonomy files: skills, capabilities with implication graph, technologies |
| 2.2 | Deterministic JD analyser with evidence spans, explicit/inferred labels, confidence; language detection |
| 2.3 | Candidate profile: model, editor UI, YAML import/export, seed profile; fit assessment |
| 2.4 | Research: UrlGuard, collectors (documents, URLs, official-site crawler, cache), extractive claim builder, Source and Claim storage |
| 2.5 | Opportunity archetypes, generator, 12-criterion scorer with `config/scoring.yaml` |
| 2.6 | UI: JD analysis page, opportunity discovery page with sources, assumptions and alternatives |

AC:
- Three fixture JDs (Scenarios A, B, C) are classified into the correct problem families;
  inferred capabilities cite the rule that produced them.
- A JD with keyword stuffing but ML-engineering responsibilities is not classified by
  keyword count alone (fixture).
- With research disabled or offline, the pipeline completes and every company statement is
  labelled hypothesis.
- No claim of kind `VERIFIED` exists without a source record.
- The fetcher refuses loopback, private and metadata addresses, including through redirects.
- Editing the profile changes fit results with no code change.

Tests: golden-file tests for analyser; injection fixture (JD containing instructions);
SSRF tests; scorer unit tests; offline test.

### M3 — Decision engine

Depends on: M2. Stage: H2.

| # | Work item |
|---|-----------|
| 3.1 | `ProblemSpec` model; registry loader and validation |
| 3.2 | Recipe SDK: manifest schema, discovery, conformance suite harness (manifests only at this point) |
| 3.3 | Decision engine: candidate composition, technology rules, trade-off ranking, data and evaluation plans, estimates, coverage map, Mermaid diagram |
| 3.4 | Proposal versioning, structured modifications, alternatives comparison |
| 3.5 | Approval records bound to payload hash; architecture review UI with all §8 actions |

AC:
- For each fixture JD the proposal lists every considered technology as selected or
  excluded with a reason; no technology is selected solely because the JD names it (test
  with a JD that lists LangGraph for a single-step retrieval problem → excluded).
- Adding a new capability and a manifest-only recipe changes proposals without editing
  engine code.
- Modifying a proposal creates a new version and invalidates the earlier approval.
- No build job can be enqueued without a valid approval.

Tests: rule-table unit tests; registry extension test; approval-gate tests; UI flow test.

### M4 — Generation

Depends on: M1 sandbox, M3. Stage: H2.

| # | Work item |
|---|-----------|
| 4.1 | Hand-built reference prototype for Scenario A in the generated-project layout, passing all checks in the sandbox |
| 4.2 | Demo shell v1 and manifest schema, built against 4.1 |
| 4.3 | Extract `recsys.implicit_feedback` recipe; RecipeComposer (G1); provenance and lock file |
| 4.4 | Check runner, results ingestion, EvaluationReport, document rendering with numeric lint |
| 4.5 | Repair loop: failure classifier, deterministic fixers, limits, RepairAttempt storage |
| 4.6 | Generation workspace UI (progress, logs, checks, errors, artifacts) and prototype review UI (live demo, code, evaluation) |
| 4.7 | Reference prototypes then recipes for `rag.grounded_qa`, `agent.tool_workflow`, `mlops.pipeline_monitoring` |
| 4.8 | `PROTOTYPE_RECIPE_GUIDE.md` |

AC:
- Each recipe passes the conformance suite.
- A generated project runs outside ProtoPitch with its own README instructions.
- Every number in generated documents exists in `results.json` for that build.
- A deliberately broken build ends `FAILED` after at most 3 repair attempts with stored
  diagnostics and intact partial work; it never reaches `READY_FOR_REVIEW`.
- Simulated or extractive components are disclosed in the demo and README.

Tests: conformance suite per recipe; repair-limit test; numeric-lint test; determinism test
(same inputs and seed → identical files).

### M5 — Three-scenario validation

Depends on: M4. Stage: H3.

AC (specification §24):
- Scenarios A, B and C each run end to end from JD to reviewed demo with measured
  evaluation, on a machine with no model keys and no local model.
- Cross-project: the three projects have different recipe sets, algorithms, data schemas,
  endpoints and metrics (asserted by a structural-difference test), and none modifies
  another's files.
- Regeneration creates version 2 and preserves version 1 and the owner's modifications.

Tests: three end-to-end tests in CI (network disabled); differentiation test; versioning
test.

### M6 — Model adapters and routing

Depends on: M2 (may run in parallel with M4). Stage: H2 for router and budgets, H3 for adapters.

| # | Work item |
|---|-----------|
| 6.1 | Provider protocol, `none` and `mock` adapters, router, `config/providers.yaml` |
| 6.2 | Budget enforcement, ProviderCall ledger, cost view (model spend separate from hosting) |
| 6.3 | Adapters: Ollama, Anthropic, OpenAI, Gemini, OpenAI-compatible |
| 6.4 | Model-backed variants: JD refinement, research synthesis, opportunity ideas, outreach rephrasing; PromptEnvelope |
| 6.5 | G2 SlotFiller; G3 AgentGenerator behind approval; model-based repair |
| 6.6 | `MODEL_PROVIDER_GUIDE.md` |

AC:
- Swapping a task between two mock providers is a configuration change only.
- With budget zero, no paid adapter is ever called (asserted by a test that fails on any
  outbound request).
- Provider failure with `on_failure: fail` stops the task and reports it; with
  `on_failure: deterministic` the artifact is marked as degraded.
- A search of the code for provider model identifiers outside `config/` and adapter
  defaults documentation returns nothing.
- Injection fixtures do not alter structured outputs beyond schema-valid data.

### M7 — Deployment, outreach, GitHub

Depends on: M5. Stage: H3.

| # | Work item |
|---|-----------|
| 7.1 | Deployment target interface; local target; Cloud Storage artifact store |
| 7.2 | Cloud Run shared demo host and dedicated target; plan screen with estimate; health validation, rollback, teardown, expiry |
| 7.3 | Outreach engine, claim check, contact records, outreach workspace UI |
| 7.4 | Optional GitHub adapter with approval and secret scan; CI workflow in generated repos |
| 7.5 | `DEPLOYMENT_GUIDE.md`, `API_REFERENCE.md` |

AC:
- Nothing is provisioned, pushed or published without a matching approval (tests with a
  fake cloud client).
- A failed deployment rolls back and leaves the project in `READY_FOR_REVIEW`.
- Claim check rejects drafts with unverified experience, unknown metrics or missing
  disclosure (fixtures).
- There is no code path that sends a message.

### M8 — Hardening

Depends on: M7. Stage: H3 with an H2-level security review.

Work: threat-model review against SPEC_REVIEW §5; dependency audit; failure-injection tests
for every case in specification §23; performance pass on generation time; backup and
restore; documentation completion (all files in specification §22); honest list of
incomplete capabilities in README.

AC: specification §26 definition of done, verified by the M5 end-to-end suite plus the
security and failure suites.

---

## Dependency summary

```
M0 → M1 → M2 → M3 → M4 → M5 → M7 → M8
            └────→ M6 ──────↗ (G2/G3 parts of M6 need M4)
```

## Cross-cutting test suites

| Suite | Introduced | Purpose |
|-------|-----------|---------|
| State machine and recovery | M1 | No illegal transitions; resume after interruption |
| Sandbox escape | M1 | Secrets, other projects and network unreachable |
| Golden JD fixtures | M2 | Classification stability, including adversarial JDs |
| Integrity | M2, M4, M7 | No unsourced verified claims; no unmeasured numbers; claim check |
| Recipe conformance | M3 | Every recipe renders, builds, tests and evaluates |
| Zero-API end to end | M5 | Scenarios A–C with network disabled and no keys |
| Differentiation | M5 | Projects differ structurally, not cosmetically |
| Provider switching and budget | M6 | Configuration-only routing; zero-budget guarantee |
| Approval gates | M3, M7 | Side effects impossible without approval |

## Risks to watch during implementation

1. Recipe abstraction growing too generic — keep recipes concrete; extract only what two
   recipes share.
2. Sandbox friction on macOS (file-mount performance, Docker Desktop resource limits) —
   measure in M1.
3. Deterministic JD analysis quality on real JDs — collect the owner's real JDs as fixtures
   early in M2.
4. Scenario B credibility without a model — review the extractive demo with the owner
   before investing in the agent recipe.

## Handoff log

| Date | Stage | Summary |
|------|-------|---------|
| 2026-11-16 | H1 | Specification reviewed; architecture, plan and handoff documents written. No application code. Awaiting approval of architecture and D1–D10. |
