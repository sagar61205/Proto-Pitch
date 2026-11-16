# ProtoPitch — Specification Review (Phase 0)

Review of `ProtoPitch_Complete_Master_Prompt.pdf` (27 parts, referred to below as "§N").
This document records what the specification gets wrong, leaves open, or makes risky, and
how the architecture resolves each point.

Status: approved by the owner on 2026-11-16 and updated to match Architecture revision 2.1
and Implementation Plan revision 4. Nothing here is implemented.

Reading notes:
- Decision IDs in brackets (D1–D10, U1–U7) refer to the Decisions section of
  `IMPLEMENTATION_PLAN.md`. All are settled; the only open item there is U8, the owner's
  choice of coding model for M1.
- In §4 the labels M1–M15 number *missing requirements*. They are not the milestones
  M0–M8 of the implementation plan.
- Where this review and `ARCHITECTURE.md` differ, the architecture is authoritative.

---

## 1. Verdict

The specification is buildable as a single-user, local-first platform. Its core idea — a
recipe-driven prototype factory with an approval checkpoint and strict honesty rules — is
sound. Three things in it cannot be delivered as literally written; the owner has accepted
the restated versions:

1. **"Autonomous, meaningfully different prototypes for every JD" and "works with zero paid
   API credits" cannot both hold without limits.** Without a capable code generator,
   differentiation is bounded by the recipe catalogue. See §3.
2. **A zero-API "agentic RAG" demo has no generative model in it.** Retrieval, orchestration,
   tool execution and evaluation are real; the answer text is extractive and the planner is
   rule-based. This must be disclosed in the demo itself. See §3.
3. **"Identify hiring managers from public sources" is mostly not automatable within the
   spec's own rules** (no scraping, no invented names). The platform can recommend which
   *roles* to contact and surface names that appear in sources the user supplied; the user
   finds the person. See C4.

---

## 2. Contradictions and how they are resolved

| # | Conflict | Resolution |
|---|----------|------------|
| C1 | **Phase numbering.** The handoff section calls planning "Phase 1"; §25 calls it "Phase 0" and uses "Phase 1" for the foundation build. | Two separate vocabularies. **Handoff stages H1–H3** = which coding model is working. **Milestones M0–M8** = §25 phases. H1 covers M0 only. |
| C2 | **Bespoke generation vs deterministic zero-API operation** (§9, §10, §11, §27). | Three generation modes with explicit capability limits (G1 recipe composition, G2 model-assisted slots, G3 bespoke agent generation). Unsupported requests are refused with an explanation rather than faked. See §3. |
| C3 | **"Go beyond keyword matching" (§4) with no model.** A deterministic analyser is a taxonomy plus an implication graph — more than keywords, less than comprehension. | Ship the deterministic analyser as the baseline, record every inference with provenance and confidence, and let a configured model refine it. The UI states which analyser produced the result. |
| C4 | **Hiring-manager identification (§16) vs no scraping / no invented contacts.** LinkedIn and similar sites prohibit automated collection. | The platform outputs *target role titles* and reasons. Named people are only shown when the name appears in a stored source (e.g. the JD names the hiring manager, or an engineering-blog byline). Contact details are entered by the user. The platform never sends anything; it produces drafts to copy. |
| C5 | **Linear state list (§3) vs regeneration, modification loops, optional deployment.** As listed, outreach is only reachable after `DEPLOYED`, and `FAILED` loses where the failure happened. | Keep the state names; define the transition graph explicitly (ARCHITECTURE.md §5): `READY_FOR_REVIEW → OUTREACH_READY` is allowed without deployment; deployment failure returns to `READY_FOR_REVIEW`, it does not fail the project; `FAILED` records `failed_from` and is resumable. |
| C6 | **Shared demo hosting (§19) vs "treat generated code as untrusted" (§20).** Several generated demos in one service share a process boundary. | Settled (D3, U6, clarification C1). The shared demo host accepts only trusted G1 recipe runtime code shipped with the platform and validated non-executable artifacts; it contains no generated code. G2 and G3 demos, and any modified G1 build, run in dedicated isolated services with a role-less service account, no secrets and outbound network access denied by default (ARCHITECTURE §7.12, §12). |
| C7 | **Generated frontend per project (§9) vs sandbox with no network and bounded generation time.** A per-project `npm install` + build is slow, needs network egress and is the most failure-prone step. | Settled (D2). One prebuilt **demo shell** (React) with an extensible panel registry renders G1 and G2 demos from a manifest plus the demo's own API, with no per-project Node build. G3 may generate a custom frontend, built offline in the `web` sandbox profile (ARCHITECTURE §7.8, §9). |
| C8 | **"No silent fallback" (§10) vs "graceful degradation" (§23).** | Fallback to another *paid* provider never happens automatically. Fallback to the *deterministic* implementation is allowed only when the task's routing config says `on_failure: deterministic`, and it is recorded and shown on the artifact. |
| C9 | **Coding-agent adapters (§10) vs secret isolation (§20).** A coding agent needs credentials and network; the sandbox has neither. | Settled (U3, U7, decisions A16, A17). G3 uses a vendor-neutral contract: a work order goes out, a change set comes back. Three execution modes: `manual` and `interactive`, where the owner runs any coding tool and no API key is needed, and `automated`, where the platform runs a configured command after approval. The agent's execution environment is separate from the generated-code sandbox: an owner-run agent is outside the platform; an automated agent runs in its own agent container holding only its own credential, with an egress allowlist. Neither is trusted. All imported agent work must pass scope checks, protected-path checks, secret scan, dependency approval, sandbox testing, platform-owned evaluation and claim validation before it can reach review (ARCHITECTURE §7.8, §12). |
| C10 | **Docker Compose packaging (§17) vs launching sandbox containers.** A containerised backend needs the Docker socket, which is root-equivalent on the host. | Default local mode runs the backend natively and uses Docker only for sandboxes. The Compose setup isolates socket access in a small dedicated runner service. |
| C11 | **Use JD-listed technology (to impress) vs "no blind keyword-to-framework mapping" (§7, §27).** | A JD-listed technology is recorded as `employer_listed` and never justifies itself. Instead, opportunity scoring prefers *problems* where the listed technologies are genuinely warranted. If none exists, the proposal says the technology was excluded and why. |

---

## 3. Limits of differentiated generation without paid APIs (required by §25)

### Generation modes

| Mode | Needs a model? | What varies per JD | Honest limit |
|------|----------------|--------------------|--------------|
| **G1 Recipe composition** | No | Recipe selection and combination, algorithm set, data schema and synthetic-data domain, metrics, demo panels, documentation | Two JDs that map to the same recipe and domain produce structurally similar code. Problem types outside the catalogue cannot be built. |
| **G2 Model-assisted slots** | Yes — local (Ollama) or paid, opt-in | Everything in G1 plus model-written code inside declared extension points (feature logic, domain rules, extra tools, copy), validated by the recipe's tests | Quality depends on the model. Small local models will often fail validation; the slot then falls back to the recipe default and says so. |
| **G3 Bespoke generation** | A coding agent: run by the owner in any tool (manual or interactive handoff, no API key needed) or run by the platform with an API credential (automated) | Whole project, guided by the approved architecture; may include a custom frontend | Needs a capable coding agent and the owner's time or budget. Failure rate is highest; always behind an approved proposal, and imported work is validated like any untrusted input. |

### What zero-API operation delivers, stage by stage

| Stage | Works with no model | Degradation compared to model-assisted |
|-------|---------------------|-----------------------------------------|
| JD analysis | Section parsing, skill taxonomy, capability inference via implication graph, seniority/location heuristics, candidate fit | Misses unusual phrasing and unstated business goals. **English only**; other languages are detected and flagged, not analysed. Company and role names come from the form fields, not from free text. |
| Company research | Fetching user-supplied and guessed official URLs, extraction, extractive evidence passages tied to sources | No search-based discovery, no synthesis. With no URLs and no documents, research is empty and everything downstream is labelled hypothesis. |
| Opportunities | Archetype library instantiated with company evidence, 12-criterion scoring | Limited novelty; opportunities are variations on known archetypes. |
| Architecture decision | Rule-based selection over the capability registry with stated rationale and exclusions | Solid inside the registry; cannot reason about technologies it has no entry for. |
| Prototype generation | G1 for the supported catalogue. G3 by manual or interactive handoff is also possible with no API key, if the owner runs a coding tool. | See G1 limit above; G3 depends on the external tool and the owner's time. |
| Recommender demo (Scenario A) | Fully real: baselines, CF, content-based, matrix factorisation, ranking, measured metrics | Neural recommender is optional and needs the larger PyTorch image. |
| RAG / agent demo (Scenario B) | Real ingestion, BM25 + dense (LSA) hybrid retrieval, real LangGraph state machine, real tool calls, measured retrieval metrics | **No generative answers and no LLM planning.** Answers are extractive with citations; routing is rule-based. Disclosed in the demo. Answer-quality metrics that need a judge model are reported as "not evaluated". |
| MLOps demo (Scenario C) | Fully real pipeline, validation, drift detection, CI workflow | Drift events are injected and labelled simulated. |
| Outreach | Template-based drafts with claim checks | Less personalised wording. |

Dense retrieval without model downloads uses TF-IDF → truncated SVD vectors in FAISS. It is a
genuine vector index but weaker than transformer embeddings; the demo names the method.

---

## 4. Missing requirements

| # | Gap | Proposed handling |
|---|-----|-------------------|
| M1 | **Users and authentication.** Spec never says who logs in. | v1 is single-user, bound to `127.0.0.1`, no accounts. Hosting the platform itself is out of scope until auth exists; seams for remote workers are kept. Settled (D1). |
| M2 | **JD language.** Target markets are NL/DE/FI; JDs may not be English. | Detect language; deterministic analysis is English-only; translation is a model task (opt-in). Settled (D5). |
| M3 | **Candidate-profile verification.** Spec demands "verified" experience but defines no verification act. | Verification = the owner sets the evidence level in the profile editor. Seeded experience examples start as `UNVERIFIED` and cannot appear in outreach until confirmed. Settled (D7). |
| M4 | **Job execution model.** Long-running generation, recovery and progress streaming are required but unspecified. | DB-backed job queue, one worker process, checkpointed idempotent steps with leases, server-sent events for progress. No Redis or Celery. |
| M5 | **Corpus rights for RAG demos.** Indexing a company's public documentation into a public demo republishes their content. | Corpus sources need per-project approval; demos show short attributed excerpts with links; openly licensed or synthetic corpora are the default when rights are unclear. Settled (D8). |
| M6 | **Public demo abuse and cost exposure.** A public URL that calls a paid model is an open wallet. | Deployed demos make no paid calls by default. Model-backed deployed demos need an explicit approval, a hard spend cap and rate limiting. |
| M7 | **Demo lifetime.** No takedown or expiry defined. | Deployments carry an expiry date (default 60 days), a teardown action and a cost-to-date view. |
| M8 | **Personal data.** Hiring-manager names and emails are personal data under GDPR. | Store only what the user enters, per project, with delete and export; never enrich automatically. |
| M9 | **Trademarks and affiliation.** Company-themed demos could imply endorsement. | No logos or brand assets; every demo and README carries an "independent demonstration, not affiliated, synthetic data" notice. |
| M10 | **Dataset licences.** "Public data" is not the same as "licensed for this use". | Dataset registry records licence and source; downloads need approval; synthetic data is the default. |
| M11 | **Generated-code licence and attribution.** | Generated repos default to MIT, with a provenance file listing recipes, versions and any model involvement. |
| M12 | **Honest authorship.** The prototype is produced by a factory, then presented as evidence of the candidate's ability. | Settled (D6). Mentioning ProtoPitch in outreach is optional. Authorship must remain truthful: no draft may misstate how the prototype was made. Demos and READMEs clearly disclose independent development, data provenance and relevant limitations. Nothing may imply employment by, affiliation with or collaboration with the target company. Each project includes walkthrough notes so the candidate can explain every component in an interview (ARCHITECTURE §7.13). |
| M13 | **Budget defaults.** Spec asks for limits but sets none. | Configurable caps: per call, per project, per month; default paid budget is zero. |
| M14 | **Backups and deletion.** | Single `data/` directory (DB + artifacts) that is safe to copy; project delete is a destructive, approval-gated operation. |
| M15 | **Where generation runs if the platform is ever hosted.** Cloud Run cannot run nested containers. | v1 generation is local only. The sandbox driver interface leaves room for a Cloud Run Jobs / Cloud Build driver later. |

---

## 5. Security risks

| # | Risk | Control |
|---|------|---------|
| S1 | Generated code reads platform secrets or other projects | Sandbox container: non-root, read-only root filesystem, no network, all capabilities dropped, only that project's workspace mounted, empty environment. Escape tests are part of the acceptance suite. |
| S2 | Malicious dependency or install-time code execution | Hash-pinned dependency profiles baked into sandbox images. Extra packages pass a policy check (pre-approved, denied or owner approval), are resolved wheels-only with hashes in a resolver container that sees no project source or credentials and reaches only the package index, then installed offline. Lifecycle scripts are disabled (ARCHITECTURE §7.10). |
| S3 | Prompt injection through JD text, web pages or documents | Model calls that read untrusted text have no tools and must return schema-validated structured data. Downstream prompts receive only enumerated values and length-limited, sanitised strings. Retrieved text is never treated as an instruction. |
| S4 | Server-side request forgery through the research fetcher | Block private, loopback and metadata address ranges after DNS resolution; cap redirects, size and time; content-type allowlist; honour `robots.txt`. |
| S5 | Stored cross-site scripting from JD or web content shown in the UI or copied into demos | Escape on render; sanitise Markdown; strict content security policy; demo copy is escaped at generation time. |
| S6 | Secrets leaking into logs, generated repos or pushed commits | Central redaction filter on all logs; secret scan before any commit or push; keys live only in environment or OS keychain, never in the database. |
| S7 | Docker socket exposure | See C10. |
| S8 | Unapproved side effects (repo creation, deployment, paid calls) | Every side-effecting operation requires an `Approval` record bound to the exact payload hash; the executor refuses without one. |
| S9 | Shared demo host cross-reads | See C6: the shared host runs no generated code and loads only validated non-executable artifacts; demos contain only public or synthetic data by policy. |
| S10 | Runaway loops | Hard caps on repair attempts (default 3), per-step and per-build wall-clock time, tokens and spend. |
| S11 | Generated code misreporting its own results | Critical metrics are computed or verified by platform-owned evaluators on a platform-held evaluation set, in a container separate from project code; self-reported results cannot support claims (ARCHITECTURE §7.9). |

## 6. Cost risks

| # | Risk | Control |
|---|------|---------|
| $1 | Model-assisted code generation and repair consume tokens unpredictably | Estimate before each call, per-project budget, ledger of every call, stop at cap. Deterministic fixers run before any model-based repair. |
| $2 | Public demos generating ongoing spend | See missing requirements M6 and M7 in §4. |
| $3 | Cloud resources left running | Scale to zero, max-instances cap, expiry, single inventory view of everything the platform provisioned. Container images in the registry are the main idle cost; old images are pruned. |
| $4 | Large images and models (PyTorch, embeddings) | Opt-in profiles; resource check before selection; no automatic downloads. |
| $5 | Owner time | The largest real cost. The catalogue is deliberately small in v1 (four recipes). |

Local operation with no model configured costs nothing beyond the machine it runs on. Cloud
prices change; the platform computes estimates from an editable price table and shows them
before provisioning rather than hard-coding figures.

## 7. Technical limitations to accept

- Generation requires Docker on the owner's machine. Without it, analysis through proposal
  still works and generation is blocked with a clear message.
- Supported v1 problem families: recommendation/ranking, grounded retrieval QA, tool-using
  agent workflows, ML pipeline monitoring. Computer vision, speech, reinforcement learning and
  large-scale training are classified and proposed but not generated without G3.
- Evaluations run on synthetic or public data and say so. They demonstrate method, not
  business impact.
- SQLite supports one writer; fine for one user and one worker.
- Research quality is capped by what the user supplies or what an official site exposes.

## 8. Changes recommended to the specification's plan

All four were accepted (D9) and are reflected in Implementation Plan revision 4.

1. **Move the sandbox into M1.** It is the highest-risk component and everything in M4A
   onward depends on it.
2. **Build reference prototypes by hand first, then extract recipes** (M4A for Scenario A,
   M4B for the rest). A recipe abstraction designed before a working example exists will be
   wrong.
3. **Treat deployment and outreach as optional facets of a project**, not mandatory steps.
4. **Keep the platform orchestrator free of agent frameworks.** A plain state machine and job
   runner are easier to recover and test. LangGraph appears inside generated prototypes where
   it is justified.
