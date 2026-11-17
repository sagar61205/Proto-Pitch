# ProtoPitch

A local-first platform that turns a job description into a tested, company-relevant working
prototype and a hiring-manager outreach draft.

**Current state: milestone M1 (foundation, sandbox and job engine) is implemented.** You can
create projects from job descriptions, watch their jobs run and recover, and run code in the
isolation sandbox. JD analysis, research, architecture proposals, prototype generation and
outreach are later milestones and do not exist yet.

## Quick start

Needs Python 3.12, [uv](https://docs.astral.sh/uv/) and Node.js 22. No API keys, no models,
no Docker.

```bash
make start
```

Then open http://127.0.0.1:8000.

To enable the sandbox (required later for building and previewing prototypes), install
Docker and run:

```bash
make sandbox-images
```

The dashboard shows whether the sandbox is available and can run an isolation self-test.

## Documents

| Document | Contents |
|----------|----------|
| [ProtoPitch_Complete_Master_Prompt.pdf](ProtoPitch_Complete_Master_Prompt.pdf) | Original specification |
| [docs/SPEC_REVIEW.md](docs/SPEC_REVIEW.md) | Contradictions, gaps, risks and limits found in the specification |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Approved design: modules, interfaces, data model, workflows |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Milestones, acceptance criteria, open decisions, status and handoff log |
| [AGENTS.md](AGENTS.md) | Rules for any coding assistant working on this repository |
| [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) | Conventions and commands |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to make a change |
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | Test suites, when to run them, what they cover |
