# ProtoPitch — Implementation Plan

Read `ARCHITECTURE.md` first. This file is the working plan and the handoff record. Update
the **Status** section at the end of every working session.

---

## Status

| Item | State |
|------|-------|
| Current handoff stage | **H1 — architecture revision 2 delivered; stopped, awaiting owner approval** |
| Current milestone | M0 (architecture validation), revision 2 |
| Application code | None. Not authorised. |
| Next action | Owner approves revision 2 and answers the open decisions below, then names the coding model for M1. |

### Handoff stages (which coding model is working)

| Stage | Scope | Model |
|-------|-------|-------|
| H1 | M0: specification review, architecture, plan, handoff documents | Initial planning model |
| H2 | Technically hard components: M1 sandbox and job engine, M3, M4, M6 router and handoff contract, M7 trust-boundary enforcement | Owner's choice after approval |
| H3 | Routine development, tests, refinements, maintenance: remaining M1, M2, M5, M7, M8 | Owner's choice |

The owner chooses the model for each stage. Never switch models or invoke a more expensive
one without the owner's approval. Stop at each stage boundary and write a handoff summary in
this file.

---

## Decisions

### Settled by the owner (2026-11-16)

| ID | Decision |
|----|----------|
| D1 | v1 is single-user and local-first, with seams kept for remote workers and cloud execution; no mobile application (ARCHITECTURE §13) |
| D2 | Shared manifest-driven demo shell for G1/G2 with an extensible panel registry; G3 may generate a custom frontend (§7.8, §9) |
| D3 | Shared Cloud Run demo host is restricted to trusted recipe runtime code and validated non-executable artifacts; generated executable code runs in dedicated isolated services (§7.12, §12) |
| D6 | Outreach is draft-only and must be accurate about independence, data and authorship; mentioning ProtoPitch is optional (§7.13) |
| R1–R10 | The ten revisions requested on review are incorporated as decisions A15–A24 and revised A4, A6, A9, A12, A13 (§11) |

### Open — need an answer before the milestone shown

| ID | Question | Recommendation | Needed by |
|----|----------|----------------|-----------|
| D4 | v1 recipe catalogue is the four recipes covering Scenarios A–C? | Yes; forecasting, propensity and NL-to-SQL follow after M5 | M3 |
| D5 | Deterministic JD analysis is English-only; other languages need a configured model? | Yes | M2 |
| D7 | Seeded experience examples start as `UNVERIFIED` until you confirm each one? | Yes | M2 |
| D8 | RAG demo corpora need per-project approval; default to openly licensed or synthetic text when rights are unclear? | Yes | M4 |
| D9 | Sandbox moves into M1; reference prototypes are hand-built before recipes are extracted? | Yes | M1 |
| D10 | Tooling: Python 3.12, uv, Ruff, mypy, pytest, Vitest, Playwright? | Yes | M1 |
| U1 | When a valid model-proposed architecture and the deterministic baseline differ, which is the default recommendation? | The model proposal, with the baseline always shown as an alternative | M3 |
| U2 | May a model propose a component whose capability is not in the registry? | Yes, flagged `unregistered` and buildable only by G3 | M3 |
| U3 | Automated coding agents run code inside their agent container, where that code could read the agent's own API key. Accept with egress allowlist and a dedicated spend-capped key, or restrict automated agents to edit-only? | Accept with the controls; edit-only makes most agents ineffective | M6 |
| U4 | Dedicated Cloud Run demo services have open outbound internet by default. Accept (role-less account, no secrets) or require an egress-deny network configuration, which adds cost and set-up? | Accept for v1; keep egress-deny as an option | M7 |
| U5 | Model-written research summaries: `VERIFIED` only for verbatim-checked quotes, generalisations stored as `INFERRED`? | Yes (strict rule) | M2 |
| U6 | G2 demos contain model-written code, so in the cloud each needs a dedicated service rather than the shared host. Accept this consequence of D3? | Yes | M7 |

---

## Milestones

Milestone numbers follow specification §25. Each lists dependencies, deliverables,
acceptance criteria (AC) and required tests. A milestone is done when its AC pass in CI and
the documents named in it are updated.

### M0 — Architecture validation (revision 2 delivered, pending approval)

Deliverables: `docs/SPEC_REVIEW.md`, `ARCHITECTURE.md`, this plan, `AGENTS.md`,
`DEVELOPMENT_GUIDE.md`.
AC: owner approves revision 2.

### M1 — Foundation

Depends on: M0 approval, D9, D10. Stage: H2 for 1.4–1.5, H3 for the rest.

| # | Work item |
|---|-----------|
| 1.1 | Repository skeleton per ARCHITECTURE §10; uv project; frontend and demo-shell scaffolds; CI workflow |
| 1.2 | Configuration loading, structured logging with redaction, `AuthProvider` hook on all routes (`LocalNoAuth`) |
| 1.3 | Database models and migrations for Project, ProjectVersion, JDDocument, Artifact, Job, Step, Approval, AuditEvent; `ArtifactStore` (local) |
| 1.4 | Lifecycle state machine; `JobBackend` interface with database implementation; worker, leases, checkpoint resume; workspace materialise/save through the artifact store; SSE log stream |
| 1.5 | Docker sandbox driver; hash-pinned `core` profile image built by `make sandbox-images`; resource limits; escape test suite; sandbox capability probe |
| 1.6 | API: projects CRUD, state transitions, job status. UI: dashboard, new-project form, project page shell |
| 1.7 | Docker Compose for local run; `CONTRIBUTING.md`, `TESTING_GUIDE.md` first versions |

AC:
- Fresh clone starts with one documented command, no keys, no model downloads.
- **The platform starts and serves the UI with Docker absent; the probe reports generation
  as unavailable and nothing else is affected.**
- Creating two projects for the same company yields two independent records and directories.
- Illegal state transitions are rejected with a clear error.
- Killing the worker mid-job and restarting resumes from the last completed step.
- **A job step completes correctly when its workspace directory is deleted between steps
  (state is recovered from the artifact store), proving no shared-path assumption.**
- Sandbox tests prove a job cannot read host environment variables, a planted secret file,
  another project's workspace, or reach the network; and that time and memory limits kill it.
- **The sandbox image digest and lock hash are recorded on the run.**

Tests: state-machine property tests; job recovery and workspace re-materialisation tests;
sandbox escape tests; no-Docker start-up test; API tests; one Playwright smoke test.

### M2 — Intelligence

Depends on: M1, D5, D7, U5. Stage: H3.

| # | Work item |
|---|-----------|
| 2.1 | Taxonomy files: skills, capabilities with implication graph, technologies |
| 2.2 | Deterministic JD analyser with evidence spans, explicit/inferred labels, confidence; language detection |
| 2.3 | Candidate profile: model, editor UI, YAML import/export, seed profile; fit assessment |
| 2.4 | Research: UrlGuard, collectors, source snapshots, `Evidence` records with verbatim check, claim kinds and automatic downgrade |
| 2.5 | Opportunity archetypes, generator, 12-criterion scorer, JD-relevance gate |
| 2.6 | UI: JD analysis page; opportunity discovery page showing each claim's kind, source, authority and retrieval date |

AC:
- Three fixture JDs (Scenarios A, B, C) are classified into the correct problem families;
  inferred capabilities cite the rule that produced them.
- A keyword-stuffed JD is not classified by keyword count alone (fixture).
- **Every `VERIFIED` claim has an evidence excerpt that is found verbatim in its stored
  snapshot; a claim whose excerpt is altered or whose snapshot is removed is downgraded.**
- **Every `INFERRED` claim lists premise claims that are `VERIFIED` or `USER_PROVIDED`; a
  generalisation with no premises is stored as `HYPOTHESIS`.**
- With research disabled or offline, the pipeline completes with all company statements
  labelled hypothesis. **This stage runs with Docker absent.**
- The fetcher refuses loopback, private and metadata addresses, including through redirects.
- **An opportunity below the JD-relevance gate is never auto-selected, whatever its
  feasibility score.**
- Editing the profile changes fit results with no code change.

Tests: analyser golden files; injection fixture; evidence integrity tests; SSRF tests;
scorer and gate tests; offline test.

### M3 — Decision engine

Depends on: M2, D4, U1, U2. Stage: H2.

| # | Work item |
|---|-----------|
| 3.1 | `ProblemSpec` model; registry loader and validation |
| 3.2 | Recipe SDK: manifest schema, discovery, conformance harness |
| 3.3 | Deterministic baseline engine: composition, technology rules, trade-off ranking, plans, estimates, coverage map, diagram |
| 3.4 | `ArchitectureValidator` (capability, justification, feasibility, resources, security, evaluability) applied to every candidate |
| 3.5 | `ArchitectureReasoner` interface with mock-model implementation: propose, compare, revise; candidate origin tracking |
| 3.6 | Capability-gap analysis and options (G2, G3, alternative opportunity, stop) |
| 3.7 | Proposal versioning, structured modifications, alternatives comparison; approvals bound to payload hash; architecture review UI |

AC:
- With no model configured the engine produces a complete proposal; outputs are identical
  across runs.
- For each fixture JD every considered technology is selected or excluded with a reason; a
  JD listing LangGraph for a single-step retrieval problem yields an exclusion.
- **A mock model can propose an architecture containing a component outside the baseline
  and outside the catalogue; it is shown with origin `model`, a validation report and the
  required generation mode, alongside the baseline.**
- **Invalid model candidates are rejected with reasons: unjustified technology (JD mention
  only), disallowed dependency, resource limit exceeded, runtime credential or network
  requirement, no evaluation plan (one fixture each).**
- **A mock model revises a proposal in response to an owner modification; the revision is
  re-validated and versioned.**
- **Malformed or instruction-bearing model output cannot bypass validation or approval.**
- **A JD whose primary capability has no recipe (computer-vision fixture) produces a gap
  report offering the feasible options; the platform does not select an unrelated buildable
  prototype, and cannot enter `GENERATING` until the owner chooses.**
- Adding a capability and a manifest-only recipe changes proposals without engine edits.
- Modifying a proposal creates a new version and invalidates the earlier approval; no build
  can be enqueued without a valid approval. **This stage runs with Docker absent.**

Tests: rule-table tests; validator fixtures; reasoner tests with mock provider; gap tests;
registry extension test; approval-gate tests; UI flow test.

### M4 — Generation

Depends on: M1 sandbox, M3, D8. Stage: H2.

| # | Work item |
|---|-----------|
| 4.1 | Hand-built reference prototype for Scenario A in the generated-project layout, passing all checks in the sandbox |
| 4.2 | Demo shell v1, manifest schema and panel registry, built against 4.1 |
| 4.3 | Extract `recsys.implicit_feedback`; RecipeComposer (G1); provenance and lock file |
| 4.4 | Check runner, results ingestion, EvaluationReport, template rendering by record reference |
| 4.5 | Quantitative claim validation: detector, matching, `QuantClaim` records, review listing |
| 4.6 | Dependency workflow: policy file, resolver container with index-only proxy, wheelhouse cache, offline install, platform-owned Dockerfile build |
| 4.7 | Repair loop: failure classifier, deterministic fixers, limits, RepairAttempt storage |
| 4.8 | Generation workspace UI and prototype review UI |
| 4.9 | Reference prototypes then recipes for `rag.grounded_qa`, `agent.tool_workflow`, `mlops.pipeline_monitoring` |
| 4.10 | `PROTOTYPE_RECIPE_GUIDE.md` |

AC:
- Each recipe passes the conformance suite; a generated project runs outside ProtoPitch
  from its own README and lock file.
- **G1 builds run entirely with the network disabled.**
- **A build needing an extra package: unapproved → blocked pending approval; approved →
  resolved wheels-only with hashes, installed offline, and the check sequence passes; a
  package with no wheel is refused; a hash mismatch fails the install.**
- **The resolver container cannot read workspace code or secrets and cannot reach any host
  other than the package index (tests).**
- **Claim validation: a document stating a metric that differs from the evaluation record,
  a comparison not computable from records, or a business-impact figure phrased as an
  achieved result is blocked; the same document with versions, dates, ports, dataset sizes
  and parameter values passes untouched.**
- A deliberately broken build ends `FAILED` after at most 3 repair attempts with stored
  diagnostics and intact partial work.
- Simulated or extractive components are disclosed in the demo and README.
- Same inputs and seed produce identical files.

Tests: conformance suite; dependency-workflow tests; claim-validation fixtures (positive and
negative); repair-limit test; determinism test.

### M5 — Three-scenario validation

Depends on: M4. Stage: H3.

AC (specification §24):
- Scenarios A, B and C each run end to end from JD to reviewed demo with measured
  evaluation, with no model keys, no local model and the network disabled.
- The three projects differ in recipe set, algorithms, data schema, endpoints and metrics
  (structural-difference test); none modifies another's files.
- Regeneration creates version 2 and preserves version 1 and the owner's modifications.
- **Each scenario's demo states what is synthetic, simulated or extractive.**

Tests: three end-to-end tests in CI; differentiation test; versioning test.

### M6 — Model adapters, routing and coding-agent handoff

Depends on: M2 (router can start in parallel with M4); 6.5–6.8 need M4; U3.
Stage: H2 for router, budgets, handoff contract and agent container; H3 for adapters.

| # | Work item |
|---|-----------|
| 6.1 | Provider protocol, `none` and `mock` adapters, router, `config/providers.yaml` |
| 6.2 | Budget enforcement, ProviderCall ledger, cost view |
| 6.3 | Adapters: Ollama, Anthropic, OpenAI, Gemini, OpenAI-compatible |
| 6.4 | Model-backed tasks: JD refinement, research synthesis, opportunity ideas, architecture reasoning (live `ArchitectureReasoner`), outreach rephrasing; PromptEnvelope |
| 6.5 | G2 SlotFiller |
| 6.6 | Work-order writer and schema; import pipeline (scope, protected paths, secret scan, dependency diff, sandbox checks); `AWAITING_EXTERNAL_WORK`; feedback rounds |
| 6.7 | Handoff modes: `manual` (export/import by path, bundle or archive), `interactive` (`protopitch handoff check`), `automated` (generic command adapter, agent container, egress allowlist, limits, approval) |
| 6.8 | `web` sandbox profile; custom-frontend build, smoke test and disclosure check |
| 6.9 | `MODEL_PROVIDER_GUIDE.md`, including a coding-agent section with example configurations |

AC:
- Swapping a task between two mock providers is a configuration change only.
- With budget zero, no paid adapter is ever called (test fails on any outbound request).
- Provider failure with `on_failure: fail` stops the task; with `deterministic` the artifact
  is marked degraded.
- No provider or model identifier appears in code outside configuration files.
- **Manual handoff round trip with no API key configured: export a work order, apply a
  change set produced outside ProtoPitch, import, validate, reach `READY_FOR_REVIEW`.**
- **Two different stub coding agents, defined only by configuration entries, complete the
  same work order through the automated mode with no code change.**
- **Import rejects or neutralises: edits outside allowed paths, modified acceptance checks,
  a forged results file, an added secret, an unapproved dependency (one fixture each).
  A `RESULT.json` claiming success does not affect the outcome.**
- **The agent container cannot read platform credentials or other projects and cannot
  reach hosts outside its allowlist.**
- **A build paused in `AWAITING_EXTERNAL_WORK` survives a platform restart and consumes no
  budget while waiting; feedback rounds stop at the repair limit.**
- **A G3 build with a custom frontend builds offline, loads, and is rejected if the
  required disclosures are missing.**
- Injection fixtures do not alter structured outputs beyond schema-valid data.

### M7 — Deployment, outreach, GitHub

Depends on: M5 (and M6 for dedicated-service cases); U4, U6. Stage: H2 for 7.2, H3 for the rest.

| # | Work item |
|---|-----------|
| 7.1 | Deployment target interface; local target; Cloud Storage artifact store |
| 7.2 | Shared demo host: trusted runtime image, artifact validator, hash manifest, eligibility check (G1, installed recipe versions, unmodified render) |
| 7.3 | Dedicated Cloud Run target; role-less service account per demo; plan screen with target rationale and estimate; health validation, rollback, teardown, expiry |
| 7.4 | Outreach engine, revised claim check, contact records, outreach workspace UI |
| 7.5 | Optional GitHub adapter with approval and secret scan; CI workflow in generated repos |
| 7.6 | `DEPLOYMENT_GUIDE.md` (including the trust-boundary table), `API_REFERENCE.md` |

AC:
- Nothing is provisioned, pushed or published without a matching approval (fake cloud client).
- **Shared-host eligibility: a G1 build is accepted; a G2 or G3 build, a G1 build with one
  modified source file, and a build containing a pickle or other executable-format artifact
  are each refused and routed to a dedicated service.**
- **The shared host refuses to load an artifact whose hash is not in the manifest, and its
  image contains no per-project code (asserted by inspection test).**
- **Dedicated services are created with a service account that has no roles and no secrets
  mounted (asserted against the generated deployment configuration).**
- A failed deployment rolls back and leaves the project in `READY_FOR_REVIEW`.
- **Outreach claim check: rejects unverified experience, unsupported performance or impact
  claims, implied company involvement and misstated authorship; accepts an accurate draft
  that does not mention ProtoPitch; a draft citing results must state the data basis.**
- There is no code path that sends a message.

### M8 — Hardening

Depends on: M7. Stage: H3 with an H2-level security review.

Work: threat-model review against ARCHITECTURE §12; dependency audit; failure-injection
tests for every case in specification §23; generation-time performance pass; backup and
restore; documentation completion (all files in specification §22); honest list of
incomplete capabilities in README; **remote-readiness review** (§13 constraints verified by
running the worker against an HTTP job-backend stub and a non-local artifact store stub).

AC: specification §26 definition of done, verified by the M5 end-to-end suite plus the
security, failure and remote-readiness suites.

---

## Dependency summary

```
M0 → M1 → M2 → M3 → M4 → M5 → M7 → M8
            └─ M6.1–6.4 (parallel) ─┐
                         M4 → M6.5–6.8 → (dedicated-service cases in M7)
```

## Scenario confirmation

Scenarios A, B and C are implementable and testable end to end under this architecture in
G1, with no model, no key and no network, exercised by the M5 suite. This is a design
confirmation; nothing has been built or run yet.

| Scenario | Recipe(s) | Real | Stated limitation |
|----------|-----------|------|-------------------|
| A — recommender | `recsys.implicit_feedback` | Baselines, collaborative and content-based filtering, matrix factorisation, ranking, Precision/Recall/NDCG@K, coverage, diversity, cold start | Synthetic interactions; neural model optional and needs the `torch` profile |
| B — agentic RAG | `rag.grounded_qa` + `agent.tool_workflow` | Ingestion, hybrid retrieval, LangGraph state graph, tool execution, traces, retrieval and tool-sequence metrics | Without a model: extractive cited answers and rule-based routing; judge-based answer quality reported as not evaluated |
| C — ML engineering | `mlops.pipeline_monitoring` | Validated data pipeline, training, model registry, drift detection, monitoring view, CI and deployment documents | Drift events injected and labelled simulated |

## Cross-cutting test suites

| Suite | Introduced | Purpose |
|-------|-----------|---------|
| State machine and recovery | M1 | No illegal transitions; resume after interruption |
| Sandbox and container isolation | M1, M4, M6 | Sandbox, resolver and agent containers hold their boundaries |
| No-Docker operation | M1–M3 | Analysis through approval works without Docker |
| Golden JD fixtures | M2 | Classification stability, including adversarial JDs |
| Evidence integrity | M2 | Verified claims are traceable; inferences have premises |
| Architecture validation | M3 | Model candidates cannot bypass constraints; gaps are explicit |
| Recipe conformance | M3 | Every recipe renders, builds, tests and evaluates |
| Quantitative claim validation | M4, M7 | Unsupported performance and impact claims blocked; technical numbers allowed |
| Dependency workflow | M4 | Offline, hash-verified, policy-gated installs |
| Zero-API end to end | M5 | Scenarios A–C with network disabled and no keys |
| Differentiation | M5 | Projects differ structurally, not cosmetically |
| Provider switching and budget | M6 | Configuration-only routing; zero-budget guarantee |
| Coding-agent handoff | M6 | Tool-independent contract; import pipeline defences |
| Deployment trust boundaries | M7 | Shared host takes only trusted code and safe artifacts |
| Approval gates | M3, M7 | Side effects impossible without approval |
| Remote readiness | M8 | No local-path or same-host assumptions |

## Risks to watch during implementation

1. Recipe abstraction growing too generic — extract only what two recipes share.
2. Sandbox friction on macOS (mount performance, Docker Desktop limits) — measure in M1.
3. Deterministic JD analysis quality on real JDs — collect the owner's real JDs as fixtures
   early in M2.
4. Scenario B credibility without a model — review the extractive demo with the owner
   before investing in the agent recipe.
5. Claim detector misses or false alarms — keep the owner-facing claim listing; tune on
   real generated documents.
6. Shared-host eligibility depends on deterministic rendering — the determinism test is a
   release gate for every recipe.
7. Model-proposed architectures raising cost through G3 — conditions and estimates are
   shown before approval.

## Handoff log

| Date | Stage | Summary |
|------|-------|---------|
| 2026-11-16 | H1 | Specification reviewed; architecture, plan and handoff documents written. No application code. |
| 2026-11-16 | H1 | Owner approved the architecture in principle with ten revisions. Revision 2 written: model architecture reasoning with validation, G3 custom frontends, coding-agent execution contract, trusted-only shared demo host, quantitative claim validation, traceable verified claims, dependency workflow, explicit capability gaps, remote-ready seams, revised outreach rules. D1, D2, D3, D6 settled. Awaiting approval of revision 2 and open decisions. No application code. |
