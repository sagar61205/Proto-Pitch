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
  Work only on the authorised milestone.
- Stop at each handoff-stage boundary (H1 → H2 → H3) and add a row to the handoff log.
- The owner chooses which coding model works on which stage. Do not switch models, spawn
  more expensive models, or assume you can, without the owner's approval.
- Do not create remote repositories, deploy, provision cloud resources, call paid APIs, or
  send messages on the owner's behalf without explicit approval in the current session.
- Ask before changing anything in the decision log (`ARCHITECTURE.md` §11). Propose the
  change, get approval, then update the log.

## Invariants — never break these

1. **Model independence.** No provider or model name in application code, tests or
   generated projects' logic. Names live in `config/providers.yaml`. The platform must not
   depend on the assistant that built it.
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

## Keeping the handoff documents current

| Document | Update when |
|----------|-------------|
| `IMPLEMENTATION_PLAN.md` | Every session: Status; milestone progress; handoff log at stage boundaries |
| `ARCHITECTURE.md` | Any change to modules, interfaces, data model, lifecycle or decisions |
| `DEVELOPMENT_GUIDE.md` | Any change to setup, commands, conventions or layout |
| `AGENTS.md` | Any change to rules or invariants (owner approval required) |

Documents still to be written, with the milestone that owns each: `CONTRIBUTING.md` and
`TESTING_GUIDE.md` (M1), `PROTOTYPE_RECIPE_GUIDE.md` (M4), `MODEL_PROVIDER_GUIDE.md` (M6),
`DEPLOYMENT_GUIDE.md` and `API_REFERENCE.md` (M7).
