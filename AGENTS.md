# AGENTS.md — instructions for any coding assistant working on ProtoPitch

These instructions apply to every coding model or agent, whichever vendor it comes from.
The project must stay maintainable without the chat history of earlier sessions: if you
learn something a successor needs, write it into the documents below.

## Start here

1. `IMPLEMENTATION_PLAN.md` → **Status** section: what stage the project is in and what is
   authorised.
2. `ARCHITECTURE.md`: the design you must follow.
3. `docs/SPEC_REVIEW.md`: why the design departs from the specification in places.
4. `DEVELOPMENT_GUIDE.md`: conventions and commands.
5. `ProtoPitch_Complete_Master_Prompt.pdf`: the owner's original specification.

## Authorisation rules

- **Do not write application code until the Status section says a milestone is authorised.**
  Work only on the authorised milestone. M4 is delivered as four separately authorised
  checkpoints in the order M4A, M4H, M4S, M4B.
- M5 and M6.9 (the real coding-agent acceptance run) are mandatory release gates. Passing
  an earlier checkpoint never substitutes for them, and no checkpoint relaxes sandboxing,
  platform-owned evaluation, claim validation, cost limits, versioning or owner approvals.
- Stop at each handoff-stage boundary (H1 → H2 → H3) and at the end of each authorised
  milestone or checkpoint; write a handoff using the template below.
- The owner chooses which coding model works on which stage. Do not switch models, spawn
  more expensive models, or assume you can, without the owner's approval.
- Do not create remote repositories, deploy, provision cloud resources, call paid APIs, or
  send messages on the owner's behalf without explicit approval in the current session.
- Ask before changing anything in the decision log (`ARCHITECTURE.md` §11). Propose the
  change, get approval, then update the log.

## Invariants — never break these

1. **Model independence.**
   - Provider-specific identifiers (provider names, model names, endpoints, SDK imports)
     are permitted only in provider adapters, adapter tests and configuration files.
   - Core orchestration, business logic and generated-project logic stay provider-agnostic:
     they use the provider and coding-agent interfaces and task names, never a vendor.
   - Switching providers is a configuration change and must not require editing core
     application code.
   - The platform must not depend on the assistant that built it.
2. **Zero-API operation.** The application starts and the deterministic pipeline runs with
   no keys, no local model and no model downloads.
3. **No silent paid usage and no silent fallback.** Paid providers are opt-in, budgeted,
   logged and approved.
4. **No fabrication.** No invented sources, company problems, contacts, candidate
   experience or metrics — in code, fixtures presented as real, documents or demos.
   Synthetic and simulated things are labelled.
5. **Evidence typing.** Company statements are `Claim` records; `VERIFIED` needs traceable
   evidence. Critical metrics are computed or verified by platform-owned evaluators, never
   taken on trust from generated result files. Performance and
   business-impact claims in any generated text must trace to those records.
6. **Untrusted input.** JDs, web pages, uploaded documents, model output, imported agent
   work and generated code are untrusted. The platform executes generated code only inside
   the isolation boundaries of `ARCHITECTURE.md` §12. Platform credentials never enter them.
7. **Approval gates.** Side-effecting operations check for a matching `Approval`.
8. **Project isolation.** One project never reads or writes another project's data.
9. **Bounded work.** Retries, repairs, time, tokens and spend all have hard limits.
10. **Extension by registration.** New capability, recipe, provider, sandbox driver or
    deployment target = new plugin or data file, not a core change.
11. **Failures are failures.** Never mark a failed build, test or deployment as successful,
    and never skip or weaken a test to get a pass.
12. **No silent substitution.** If a JD needs a capability the recipes cannot build, say
    so and offer the options; never build something unrelated instead.
13. **Remote-ready seams.** Respect the constraints of `ARCHITECTURE.md` §13 (no shared
    local paths, no same-host assumptions).

## Working practice

- Small, reviewable commits with clear messages; tests in the same commit as the code.
- Run the full check command from `DEVELOPMENT_GUIDE.md` before every commit.
- Each milestone's acceptance criteria in `IMPLEMENTATION_PLAN.md` are the definition of
  done; do not declare completion on anything less.
- Prefer the simplest design that meets the criteria. No new service, queue, framework or
  dependency without a stated reason recorded in the decision log.
- When behaviour or interfaces change, update the relevant document in the same change.

## Handoff template

At every stop point, write this to `docs/handoffs/<YYYY-MM-DD>-<milestone>.md`, add a
one-line row to the handoff log in `IMPLEMENTATION_PLAN.md`, and repeat it in your final
message. Fill every field; write "none" rather than leaving one empty. Report results as
they are — a failing or unrun test is stated as such.

```markdown
# Handoff — <date> — <stage and milestone or checkpoint>

## Completed milestone and work items
<milestone id; each work-item id with done / partial / not started>

## Last commit hash
<full hash> on branch <name>; pushed: yes / no

## Files modified
<paths, grouped by purpose>

## Tests executed and their results
<each command run → passed / failed / skipped counts; suites not run and why>

## Known failures and blockers
<failing tests, open defects, missing approvals, environment problems>

## Exact next authorized task
<milestone and work-item id exactly as authorised in the Status section, or
"None — awaiting owner authorisation of <milestone>">
```

## Keeping the handoff documents current

| Document | Update when |
|----------|-------------|
| `IMPLEMENTATION_PLAN.md` | Every session: Status; milestone progress; handoff log at stage boundaries |
| `ARCHITECTURE.md` | Any change to modules, interfaces, data model, lifecycle or decisions |
| `DEVELOPMENT_GUIDE.md` | Any change to setup, commands, conventions or layout |
| `AGENTS.md` | Any change to rules or invariants (owner approval required) |

Documents still to be written, with the milestone that owns each: `CONTRIBUTING.md` and
`TESTING_GUIDE.md` (M1), `PROTOTYPE_RECIPE_GUIDE.md` (M4B), `MODEL_PROVIDER_GUIDE.md`
(coding-agent section started in M4H, completed in M6), `DEPLOYMENT_GUIDE.md` and
`API_REFERENCE.md` (M7).
