# ProtoPitch — Implementation Plan

Read `ARCHITECTURE.md` first. This file is the working plan and the handoff record. Update
the **Status** section at the end of every working session.

---

## Status

| Item | State |
|------|-------|
| Architecture | **Approved by the owner** (revision 2.1, 2026-11-16). Unchanged by this plan revision. |
| Implementation plan | **Revision 4** — milestone structure approved by the owner on 2026-11-16 subject to sequencing adjustments, which this revision incorporates |
| Current handoff stage | H2/H3 — M1 in progress |
| Application code | M1 under implementation |
| Next action | Complete M1 work items 1.1–1.7 and their acceptance criteria, write the handoff, stop. M2 is not authorised. |

### Authorisation

| Milestone | Authorised |
|-----------|------------|
| M0 | Complete |
| M1 | **Yes — authorised by the owner on 2026-11-16** ("M1: Foundation, Sandbox and Job Engine") |
| M2, M3, M4A, M4H, M4S, M4B, M5, M6, M7, M8 | **No.** Each starts only when the owner authorises it here. |

### Handoff stages (which coding model is working)

| Stage | Scope | Model |
|-------|-------|-------|
| H1 | M0: specification review, architecture, plan, handoff documents | Initial planning model |
| H2 | Technically hard components: M1 sandbox and job engine, M3, M4A, M4H, M4B evaluators, M6 router, automation and agent container, M7 trust-boundary enforcement | Owner's choice |
| H3 | Routine development, tests, refinements, maintenance: remaining M1, M2, M4S, remaining M4B, M5, remaining M6 and M7, M8 | Owner's choice |

The owner chooses the model for each stage. Never switch models or invoke a more expensive
one without the owner's approval. Stop at each stage boundary and write a handoff summary in
this file.

---

## Decisions

### Settled by the owner (2026-11-16)

| ID | Decision |
|----|----------|
| D1 | v1 is single-user and local-first, with seams for remote workers and cloud execution; no mobile application (ARCHITECTURE §13) |
| D2 | Demo shell for G1/G2 with an extensible panel registry; G3 may generate a custom frontend (§7.8, §9) |
| D3 | Shared demo host takes only trusted recipe runtime code and validated non-executable artifacts (§7.12, §12) |
| D4 | v1 catalogue: the four recipes of §7.7 |
| D6 | Outreach is draft-only and accurate about independence, data and authorship; mentioning ProtoPitch is optional (§7.13) |
| D9 | Sandbox in M1; reference prototypes before recipes |
| D10 | Tooling per §4 |
| U1 | A valid model-proposed architecture is the default recommendation; the baseline is always shown (§7.5) |
| U2 | Models may propose unregistered components, flagged and G3-only (§7.5) |
| U3 | Automated agents run in an agent container with egress allowlist; dedicated spend-capped key (§12) |
| U4 | **Superseded by clarification 1:** dedicated cloud services deny egress by default; exceptions by approval (A25) |
| U5 | `VERIFIED` only for verbatim-checked quotes; generalisations are `INFERRED` (§7.2) |
| U6 | G2 and G3 demos deploy to dedicated services (§7.12) |
| C1–C3 | Clarifications of 2026-11-16: restricted egress (A25), platform-owned evaluation (A26), real coding-agent acceptance test (A27) |
| D5 | Deterministic JD analysis is English-only; other languages are detected, flagged and need a configured model |
| D7 | Seeded experience examples start as `UNVERIFIED` until the owner confirms each one |
| D8 | RAG demo corpora need per-project approval; openly licensed or synthetic text is the default when rights are unclear |
| U7 | The real G3 acceptance run (M6) uses Claude Code in `interactive` mode. This names the owner's test environment only; nothing in the platform depends on it (AGENTS invariant 1). |
| S1–S5 | Sequencing adjustments of 2026-11-16: M4 split into M4A and M4B; early manual/interactive handoff checkpoint (M4H); early shareability checkpoint (M4S); M5 and the M6 real-agent run are mandatory release gates; all security, evaluation, cost-control, versioning and approval requirements preserved |

D4, D9, D10, U1–U3, U5 and U6 are recorded as settled because the approved architecture
states them. Say so if any of them was not meant to be approved.

### Open

| ID | Question | Needed by |
|----|----------|-----------|
| — | None. U8 was settled when the owner authorised M1 in the session that carries it out. | — |

---

## Milestones

Milestone numbers follow specification §25. Each lists dependencies, deliverables,
acceptance criteria (AC) and required tests. A milestone is done when its AC pass in CI and
the documents named in it are updated.

### M0 — Architecture validation

Deliverables: `docs/SPEC_REVIEW.md`, `ARCHITECTURE.md` (approved), this plan, `AGENTS.md`,
`DEVELOPMENT_GUIDE.md`.
AC: architecture approved (done); this plan approved (pending).

### M1 — Foundation

Depends on: M0, U8. Stage: H2 for 1.4–1.5, H3 for the rest.

| # | Work item |
|---|-----------|
| 1.1 | Repository skeleton per ARCHITECTURE §10; uv project; frontend and demo-shell scaffolds; CI workflow |
| 1.2 | Configuration loading, structured logging with redaction, `AuthProvider` hook on all routes (`LocalNoAuth`) |
| 1.3 | Database models and migrations for Project, ProjectVersion, JDDocument, Artifact, Job, Step, Approval, AuditEvent; `ArtifactStore` (local) |
| 1.4 | Lifecycle state machine; `JobBackend` interface with database implementation; worker, leases, checkpoint resume; workspace materialise/save through the artifact store; SSE log stream |
| 1.5 | Docker sandbox driver (`run` and `serve`); hash-pinned `core` profile image built by `make sandbox-images`; resource limits; escape test suite; sandbox capability probe |
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

Depends on: M1. Stage: H3.

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

Depends on: M2. Stage: H2.

| # | Work item |
|---|-----------|
| 3.1 | `ProblemSpec` model; registry loader and validation |
| 3.2 | Recipe SDK: manifest schema, discovery, conformance harness |
| 3.3 | Deterministic baseline engine: composition, technology rules, trade-off ranking, plans, estimates, coverage map, diagram |
| 3.4 | `ArchitectureValidator` (capability, justification, feasibility, resources, security, evaluability) applied to every candidate; evaluator registry interface so evaluability can check that each critical metric has a platform evaluator |
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
- **Every proposal names its critical metrics. A candidate whose critical metric has no
  platform evaluator is accepted only with the stated condition that the metric is
  `SELF_REPORTED` and unusable in claims.**
- **A JD whose primary capability has no recipe (computer-vision fixture) produces a gap
  report offering the feasible options; the platform does not select an unrelated buildable
  prototype, and cannot enter `GENERATING` until the owner chooses.**
- Adding a capability and a manifest-only recipe changes proposals without engine edits.
- Modifying a proposal creates a new version and invalidates the earlier approval; no build
  can be enqueued without a valid approval. **This stage runs with Docker absent.**

Tests: rule-table tests; validator fixtures; reasoner tests with mock provider; gap tests;
registry extension test; approval-gate tests; UI flow test.

### M4 — Generation (four checkpoints)

M4 is delivered as M4A → M4H → M4S → M4B. Each checkpoint has its own acceptance criteria
and needs its own authorisation. M4H and M4S depend only on M4A and are independent of each
other; the order shown is the default. None of the checkpoints is a release: the release
gates are M5 and the M6 real-agent acceptance run.

Every checkpoint inherits these rules without exception: generated or imported code runs
only in the sandbox; critical metrics are platform-computed; nothing is built without an
approved proposal; repairs, time and spend are bounded; each build is a version and earlier
versions are preserved; side effects need an approval.

#### M4A — One complete Scenario A prototype

Depends on: M1 sandbox, M3. Stage: H2.

Goal: one recommender prototype, generated from a JD through the approved proposal, that
works end to end — the first proof that the factory produces real software.

| # | Work item |
|---|-----------|
| 4A.1 | Hand-built reference prototype for Scenario A in the generated-project layout, passing all checks in the sandbox |
| 4A.2 | Demo shell v1, manifest schema and panel registry, built against 4A.1 |
| 4A.3 | Extract `recsys.implicit_feedback`; RecipeComposer (G1); provenance and lock file; per-project Git repository |
| 4A.4 | Check runner and full check sequence for this recipe |
| 4A.5 | Platform evaluation harness: evaluator registry, platform-held evaluation set and split, two-phase predict/score execution, ranking evaluator, baselines and sanity checks, metric provenance, comparison with self-reported results; template rendering by record reference |
| 4A.6 | Quantitative claim validation: detector, matching, `QuantClaim` records, review listing |
| 4A.7 | Dependency workflow: policy file, resolver container with index-only proxy, wheelhouse cache, offline install, platform-owned Dockerfile build |
| 4A.8 | Repair loop: failure classifier, deterministic fixers, limits, RepairAttempt storage |
| 4A.9 | Local preview through the sandbox `serve` path on `127.0.0.1` |
| 4A.10 | Generation workspace UI and prototype review UI (live demo, code, architecture, evaluation, documents) |

AC:
- The Scenario A fixture JD goes from `CREATED` to `READY_FOR_REVIEW` with no model, no key
  and the network disabled; a build cannot start without an approved proposal.
- The recipe passes the conformance suite; the interactive demo returns personalised
  results from the running service in local preview, not canned output.
- The project is a standalone Git repository that installs and runs outside ProtoPitch from
  its own README and lock file.
- G1 builds run entirely with the network disabled.
- A build needing an extra package: unapproved → blocked pending approval; approved →
  resolved wheels-only with hashes, installed offline, and the check sequence passes; a
  package with no wheel is refused; a hash mismatch fails the install.
- The resolver container cannot read workspace code or secrets and cannot reach any host
  other than the package index.
- Claim validation: a document stating a metric that differs from the evaluation record, a
  comparison not computable from records, or a business-impact figure phrased as an
  achieved result is blocked; the same document with versions, dates, ports, dataset sizes
  and parameter values passes untouched.
- Platform-owned evaluation:
  - every critical metric is stored as `PLATFORM_COMPUTED` with evaluator version, seed and
    data hash;
  - the ranking evaluator passes known-answer tests (hand-computed fixtures);
  - a project whose `results.json` is edited to inflate a critical metric fails the
    evaluation check, and the stored value is the platform's;
  - project code cannot read held-out labels during the prediction phase, and no project
    code runs in the scoring container;
  - leaked test items or a perfect score are flagged by the sanity checks;
  - a `SELF_REPORTED` metric cannot satisfy claim validation.
- A deliberately broken build ends `FAILED` after at most 3 repair attempts with stored
  diagnostics and intact partial work.
- Synthetic data and any simulated component are disclosed in the demo and README.
- Same inputs and seed produce identical files; regenerating creates version 2 and leaves
  version 1 intact.

Tests: Scenario A end-to-end test; conformance suite; evaluator known-answer, tamper and
label-isolation tests; dependency-workflow tests; claim-validation fixtures; repair-limit
test; determinism and versioning tests.

#### M4H — Early G3 handoff checkpoint (manual and interactive only)

Depends on: M4A. Stage: H2.

Goal: prove the coding-agent contract early, on the sandbox and validation infrastructure
that already exists, with no API, no automation and no new trust.

In scope: the work order (ARCHITECTURE §7.8), `manual` and `interactive` modes, the import
pipeline. Out of scope until M6: `automated` mode, the agent container, provider adapters,
custom frontends (an imported change set containing one is refused with that explanation),
the real coding-agent acceptance run.

| # | Work item |
|---|-----------|
| 4H.1 | Work-order writer and schema: `WORK_ORDER.md`, `work_order.json`, workspace `AGENTS.md`, `acceptance/`, allowed and protected paths |
| 4H.2 | G3 build path for an approved proposal whose required mode is G3: project skeleton, `AWAITING_EXTERNAL_WORK` sub-status, resume after restart |
| 4H.3 | Export and import by local path and by Git bundle or archive |
| 4H.4 | Import pipeline: scope check, restoration of protected paths, secret scanner, dependency diff into the M4A workflow, full sandbox check sequence, platform evaluation, claim validation |
| 4H.5 | `protopitch handoff check` command for interactive iteration |
| 4H.6 | Feedback work orders (`FEEDBACK.md`), rounds counted against the repair limit |
| 4H.7 | Handoff section of the generation UI; first version of the coding-agent section of `MODEL_PROVIDER_GUIDE.md` |

AC:
- A G3 build cannot start without an approved G3 proposal; the gap report and the owner's
  choice are recorded (computer-vision or other out-of-catalogue fixture JD).
- Round trip with no API key and no provider configured: export a work order, apply a
  change set produced outside ProtoPitch, import, validate, reach `READY_FOR_REVIEW`.
  Verified in CI with scripted external change sets.
- The work order is self-sufficient: a reader with only the exported files can tell what to
  build, where they may write, and how completion is judged.
- Import rejects or neutralises, one fixture each: edits outside allowed paths; modified
  acceptance checks; an edited evaluation set, evaluator configuration or prediction
  contract; a forged results file; an added secret; an unapproved dependency. A
  `RESULT.json` claiming success does not affect the outcome.
- Imported code executes only in the sandbox; critical metrics for imported work are
  `PLATFORM_COMPUTED`, or visibly `SELF_REPORTED` and unusable in claims where no evaluator
  exists for the metric family.
- A failing import produces a feedback work order; rounds stop at the repair limit and the
  build ends `FAILED` with diagnostics and partial work kept.
- A build waiting in `AWAITING_EXTERNAL_WORK` survives a platform restart and consumes no
  budget.
- Each import is a commit in the project repository; earlier versions are untouched.

Tests: handoff contract tests with scripted change sets; import defence fixtures; restart
test; repair-limit test. An informal trial with a real coding tool is welcome but is not a
criterion here; the formal run is M6.

#### M4S — Early shareability checkpoint

Depends on: M4A. Stage: H3.

Goal: everything needed to approach a hiring manager with a working prototype, without any
public cloud deployment.

| # | Work item |
|---|-----------|
| 4S.1 | Share package for a `READY_FOR_REVIEW` project: standalone repository, README, architecture and evaluation documents, `WALKTHROUGH.md` (how each component works and how to explain it) |
| 4S.2 | Technical summary: a short document rendered from the proposal and evaluation records |
| 4S.3 | Outreach engine with deterministic templates: LinkedIn note, LinkedIn message, email; target-role suggestions; user-entered `Contact` records |
| 4S.4 | Outreach claim check (ARCHITECTURE §7.13) |
| 4S.5 | Outreach workspace UI; `READY_FOR_REVIEW → OUTREACH_READY` transition |
| 4S.6 | Export of the share package as an archive or Git bundle, gated by secret scan |

AC:
- The share package for the M4A prototype contains repository, README, walkthrough and
  technical summary; every performance statement in them passes claim validation against
  `PLATFORM_COMPUTED` records and states the data basis.
- README and demo state that the work is an independent demonstration and what data it
  uses.
- Outreach claim check, one fixture each: rejects unverified experience, unsupported
  performance or impact claims, implied company involvement, and misstated authorship;
  accepts an accurate draft that does not mention ProtoPitch; a draft citing results must
  state the data basis.
- Drafts never contain an invented name, email address or link. Where no public link
  exists, the draft carries a clearly marked placeholder for the owner to fill.
- There is no code path that sends a message, creates a remote repository or deploys.
  Publishing the repository at this stage is something the owner does by hand.
- Export is refused if the secret scan finds anything.
- A project reaches `OUTREACH_READY` without any deployment; profile items below the
  required evidence level never appear in a draft.

Tests: claim-check fixtures; share-package content test; secret-scan export test; lifecycle
test.

Public demo hosting stays in M7. An earlier deployment path would need its own proposal,
owner approval and tests, and is not planned.

#### M4B — Remaining recipes and evaluators

Depends on: M4A. Stage: H2 for evaluators and the agent recipe, H3 for the rest.

| # | Work item |
|---|-----------|
| 4B.1 | Reference prototype, then recipe, for `rag.grounded_qa`; retrieval evaluator |
| 4B.2 | Reference prototype, then recipe, for `agent.tool_workflow`; tool-call sequence evaluator. Review the extractive, rule-routed demo with the owner before finishing the recipe |
| 4B.3 | Reference prototype, then recipe, for `mlops.pipeline_monitoring`; classification, regression and drift-detection evaluators |
| 4B.4 | Additional demo-shell panels these recipes need (cited answers, traces, monitoring views), added through the panel registry |
| 4B.5 | `PROTOTYPE_RECIPE_GUIDE.md` |

AC:
- Each recipe passes the conformance suite and every M4A evaluation, claim, dependency,
  determinism and repair criterion.
- Each new evaluator passes known-answer tests; critical metrics are `PLATFORM_COMPUTED`.
- The Scenario B demo states that answers are extractive and routing is rule-based when no
  model is configured; judge-based answer quality is reported as not evaluated.
- The Scenario C demo labels injected drift as simulated.
- RAG corpora are used only with a per-project approval; the default corpus is openly
  licensed or synthetic (D8).
- Share packages and outreach drafts (M4S, if delivered) work for each new recipe.

Tests: conformance suite per recipe; evaluator known-answer tests; disclosure tests.

### M5 — Three-scenario validation — **mandatory release gate**

Depends on: M4A, M4B (and M4S for the share-package criterion). Stage: H3.

AC (specification §24):
- Scenarios A, B and C each run end to end from JD to reviewed demo with no model keys, no
  local model and the network disabled. All headline metrics shown in each demo and its
  documents are `PLATFORM_COMPUTED`.
- The three projects differ in recipe set, algorithms, data schema, endpoints and metrics
  (structural-difference test); none modifies another's files.
- Regeneration creates version 2 and preserves version 1 and the owner's modifications.
- Each scenario's demo states what is synthetic, simulated or extractive.
- Each scenario yields a share package and outreach drafts that pass the claim check.

Tests: three end-to-end tests in CI; differentiation test; versioning test.

### M6 — Model adapters, routing and advanced coding-agent execution

Depends on: M2 for 6.1–6.4 (can run in parallel with M3–M4); M4H for 6.5–6.9.
Stage: H2 for router, budgets, automation and agent container; H3 for adapters.

| # | Work item |
|---|-----------|
| 6.1 | Provider protocol, `none` and `mock` adapters, router, `config/providers.yaml` |
| 6.2 | Budget enforcement, ProviderCall ledger, cost view |
| 6.3 | Adapters: Ollama, Anthropic, OpenAI, Gemini, OpenAI-compatible |
| 6.4 | Model-backed tasks: JD refinement and translation, research synthesis, opportunity ideas, architecture reasoning (live `ArchitectureReasoner`), outreach rephrasing; PromptEnvelope |
| 6.5 | G2 SlotFiller |
| 6.6 | `automated` handoff mode: generic command adapter, `config/coding_agents.yaml`, agent container, egress allowlist, time and spend limits, approval |
| 6.7 | `web` sandbox profile; custom-frontend build, smoke test and disclosure check; import accepts custom frontends |
| 6.8 | `MODEL_PROVIDER_GUIDE.md` completed, with example coding-agent configurations |
| 6.9 | **Real coding-agent acceptance run — mandatory release gate** (A27): Claude Code in interactive mode (U7); out-of-catalogue fixture JD; scripted procedure; acceptance report artifact |

AC:
- Swapping a task between two mock providers is a configuration change only.
- With budget zero, no paid adapter is ever called (test fails on any outbound request).
- Provider failure with `on_failure: fail` stops the task; with `deterministic` the artifact
  is marked degraded.
- No provider or model identifier appears in code outside configuration files.
- Injection fixtures do not alter structured outputs beyond schema-valid data.
- Model-rephrased outreach passes the same claim check as template drafts.
- Two different stub coding agents, defined only by configuration entries, complete the
  same work order through the automated mode with no code change; their output goes through
  the unchanged M4H import pipeline.
- The agent container cannot read platform credentials or other projects and cannot reach
  hosts outside its allowlist; an automated run cannot start without an approval and a
  budget, and stops at its limits.
- A G3 build with a custom frontend builds offline, loads, and is rejected if the required
  disclosures are missing.
- **G3 end-to-end acceptance with the real coding-agent environment (owner-directed, not
  unattended CI). All of the following are observed and recorded in the acceptance report:**
  1. Gap report produced; G3 chosen and the proposal approved.
  2. Work order created and readable by the agent without ProtoPitch-specific tooling.
  3. The real agent generates the code; no manual edits by the owner to the generated
     source.
  4. Change set imported; scope, protected-path, secret and dependency checks pass or
     correctly block.
  5. Full sandbox check sequence passes within the repair limit, including at least one
     feedback round if the first import fails.
  6. Critical metrics are `PLATFORM_COMPUTED`; documents pass claim validation.
  7. Project reaches `READY_FOR_REVIEW` and the demo runs in local preview.

  The report records environment name and version, mode, rounds, elapsed time, any spend
  and check results. M6 is not complete without a passing report. If the run fails, the
  failure and diagnosis are recorded and M6 stays open.

Tests: provider switching and budget tests; automated-mode tests with stub agents;
agent-container isolation tests; custom-frontend tests; real-environment acceptance run.

### M7 — Deployment and GitHub

Depends on: M5; 7.3 also needs M6 (G2/G3 builds exist). Stage: H2 for 7.2–7.3, H3 for the rest.

| # | Work item |
|---|-----------|
| 7.1 | Deployment target interface; `local` target wrapping the existing preview; Cloud Storage artifact store |
| 7.2 | Shared demo host: trusted runtime image, artifact validator, hash manifest, eligibility check (G1, installed recipe versions, unmodified render) |
| 7.3 | Dedicated Cloud Run target: role-less service account per demo, egress denied by default through an isolated no-route network, egress-exception approval type, plan screen showing target rationale, network posture and estimate; health validation, rollback, teardown, expiry. Confirm the exact network settings against current Cloud Run documentation and record them in `DEPLOYMENT_GUIDE.md` |
| 7.4 | Outreach integration: deployed demo and repository links in drafts and share packages |
| 7.5 | Optional GitHub adapter with approval and secret scan; CI workflow in generated repos |
| 7.6 | `DEPLOYMENT_GUIDE.md` (including the trust-boundary table), `API_REFERENCE.md` |

AC:
- Nothing is provisioned, pushed or published without a matching approval (fake cloud client).
- Shared-host eligibility: a G1 build is accepted; a G2 or G3 build, a G1 build with one
  modified source file, and a build containing a pickle or other executable-format artifact
  are each refused and routed to a dedicated service.
- The shared host refuses to load an artifact whose hash is not in the manifest, and its
  image contains no per-project code (inspection test).
- Dedicated services are created with a service account that has no roles and no secrets
  or credential environment variables.
- Egress default: the generated configuration for every dedicated service routes all egress
  to the isolated network with a deny rule; a configuration without it is refused unless a
  matching egress-exception approval names the destinations.
- Live verification on one deployed dedicated demo (owner-approved, smallest instance): a
  probe from inside the service to a public host and to a cloud API endpoint fails; the
  demo itself still serves requests. The result is recorded.
- A deployment target that cannot restrict egress reports that in its plan and cannot be
  applied without the exception approval.
- A failed deployment rolls back and leaves the project in `READY_FOR_REVIEW`.
- Links inserted into drafts are only those of recorded deployments or repositories; drafts
  with new links pass the claim check again.
- The plan screen shows estimated hosting cost separately from any model spend; deployments
  have an expiry and a teardown action.

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
M0 → M1 → M2 → M3 → M4A ─┬→ M4H ─────────────┐
            │            ├→ M4S              │
            │            └→ M4B → M5* ───────┼→ M7 → M8
            └→ M6.1–6.4 ─────────→ M6.5–6.9* ┘
                                   (* mandatory release gates)
```

| Milestone | Hard dependencies | Owner inputs needed |
|-----------|-------------------|---------------------|
| M1 | M0 | Coding model (U8), authorisation |
| M2 | M1 | Confirmation of each seeded experience item (D7) |
| M3 | M2 | — |
| M4A | M1 sandbox, M3 | Review of the Scenario A prototype |
| M4H | M4A | — |
| M4S | M4A | Review of the share package and drafts |
| M4B | M4A | Review of the extractive Scenario B demo; corpus approvals |
| M5 | M4A, M4B (M4S for share packages) | Review of the three demos |
| M6 | 6.1–6.4: M2. 6.5–6.9: M4H | Running the acceptance session in Claude Code; approval and budget for any paid or automated run |
| M7 | M5; 7.3: M6 | Cloud project; approval for the live egress verification and any deployment |
| M8 | M7 | — |

Default order of work: M1, M2, M3, M4A, M4H, M4S, M4B, M5, M6, M7, M8, with M6.1–6.4
available to run alongside M3–M4 if the owner wants parallel work.

## Release gates

v1 is not released, and specification §26 is not claimed as met, until both pass:

1. **M5** — Scenarios A, B and C end to end with no model, no key and no network.
2. **M6.9** — the real coding-agent acceptance run with a passing report.

M4A, M4H and M4S are early checkpoints that deliver usable capability; passing them does
not substitute for either gate. No checkpoint relaxes sandboxing, platform-owned
evaluation, claim validation, cost limits, versioning or owner approvals.

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
| Sandbox and container isolation | M1, M4A, M6 | Sandbox, resolver, scoring and agent containers hold their boundaries |
| Platform evaluation | M4A, M4B | Evaluators are correct; tampered or self-reported results cannot become trusted metrics |
| No-Docker operation | M1–M3 | Analysis through approval works without Docker |
| Golden JD fixtures | M2 | Classification stability, including adversarial JDs |
| Evidence integrity | M2 | Verified claims are traceable; inferences have premises |
| Architecture validation | M3 | Model candidates cannot bypass constraints; gaps are explicit |
| Recipe conformance | M3 | Every recipe renders, builds, tests and evaluates |
| Quantitative claim validation | M4A, M4S | Unsupported performance and impact claims blocked; technical numbers allowed |
| Dependency workflow | M4A | Offline, hash-verified, policy-gated installs |
| Zero-API end to end | M4A (Scenario A), M5 (all three) | Scenarios with network disabled and no keys |
| Outreach claim check | M4S | Drafts are accurate; nothing is sent or invented |
| Differentiation | M5 | Projects differ structurally, not cosmetically |
| Provider switching and budget | M6 | Configuration-only routing; zero-budget guarantee |
| Coding-agent handoff | M4H, M6 | Tool-independent contract; import pipeline defences (M4H); automated mode and agent container (M6) |
| Real coding-agent acceptance | M6 | Owner-directed end-to-end G3 run with a real environment |
| Deployment trust boundaries | M7 | Shared host takes only trusted code and safe artifacts; dedicated services have no egress, roles or secrets |
| Approval gates | M3, M4H, M4S, M7 | Side effects impossible without approval |
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
8. Prediction-interface contract too rigid for novel G3 problems — evaluators are added by
   registration; until one exists the metric is visibly `SELF_REPORTED`.
9. Real-agent acceptance run is not repeatable in CI — keep the scripted procedure and the
   stored report; rerun when the handoff contract changes.
10. Cloud network settings change over time — the egress configuration is verified live in
    M7, not assumed.
11. Early checkpoints being mistaken for a release — the release gates section is the rule.
12. M4H validating only ranking metrics until M4B adds evaluators — other metric families
    stay visibly `SELF_REPORTED` in the meantime.
13. Outreach before deployment has no public demo link — drafts carry a marked placeholder;
    the owner publishes the repository by hand or waits for M7.

## Handoff log

| Date | Stage | Summary |
|------|-------|---------|
| 2026-11-16 | H1 | Specification reviewed; architecture, plan and handoff documents written. No application code. |
| 2026-11-16 | H1 | Owner approved the architecture in principle with ten revisions. Revision 2 written: model architecture reasoning with validation, G3 custom frontends, coding-agent execution contract, trusted-only shared demo host, quantitative claim validation, traceable verified claims, dependency workflow, explicit capability gaps, remote-ready seams, revised outreach rules. D1, D2, D3, D6 settled. Awaiting approval of revision 2 and open decisions. No application code. |
| 2026-11-16 | H1 | Owner approved the architecture (revision 2) with three clarifications, incorporated as A25–A27: egress denied by default for dedicated cloud services, platform-owned evaluation, real coding-agent acceptance test. Plan revised to revision 3 to match. Awaiting approval of the plan, open decisions D5, D7, D8, U7, U8 and authorisation of M1. No application code. |
| 2026-11-16 | H1 | Owner approved the milestone structure with sequencing adjustments. Plan revision 4: M4 split into M4A (complete Scenario A prototype), M4H (early manual/interactive handoff), M4S (early shareability) and M4B (remaining recipes and evaluators); outreach engine moved from M7 to M4S; M5 and M6.9 declared mandatory release gates. D5, D7, D8, U7 settled. Architecture unchanged. Awaiting the owner's choice of coding model and explicit authorisation of M1. No application code. |
