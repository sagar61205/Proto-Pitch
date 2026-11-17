# Contributing to ProtoPitch

This applies to people and to coding assistants alike. Assistants must also follow
`AGENTS.md`, which takes precedence where the two differ.

## Before you start

1. Read the **Status** section of `IMPLEMENTATION_PLAN.md`. Work only on a milestone it
   marks as authorised.
2. Read `ARCHITECTURE.md` for the design and `DEVELOPMENT_GUIDE.md` for conventions.

## Set-up

```bash
make setup
```

```bash
make start
```

`make start` serves the application on http://127.0.0.1:8000. For development with reload
use `make dev` (http://127.0.0.1:5173). Neither needs Docker, API keys or a model.

To build, test and preview generated prototypes you also need Docker and the sandbox image:

```bash
make sandbox-images
```

## Making a change

- One work item at a time; small commits; tests in the same commit as the code.
- Run `make check` before every commit. Run `make sandbox-test` whenever sandbox or
  isolation behaviour changes, and `make e2e` when the interface or the server start-up
  changes. See `TESTING_GUIDE.md`.
- A failing test is fixed at its cause or reported. Never skip, delete or loosen a test to
  get a pass.
- Schema change → a new Alembic migration (`cd backend && uv run alembic revision
  --autogenerate -m "..."`). A test fails if models and migrations drift.
- API change → `make api-types`, and commit the regenerated files.
- Behaviour or interface change → update the affected document in the same commit.
- Approved decisions (`ARCHITECTURE.md` §11) change only with the owner's approval.

## Rules that are checked automatically

| Rule | Checked by |
|------|-----------|
| Only designated modules may open network connections | `tests/test_architecture_rules.py` |
| No provider or model names in core code | `tests/test_architecture_rules.py` |
| `domain/` imports nothing from the rest of the platform | `tests/test_architecture_rules.py` |
| No `print` in platform code | `tests/test_architecture_rules.py`, Ruff |
| Untrusted text is never rendered as HTML | ESLint rule in `frontend/eslint.config.js` |
| Models and migrations agree | `tests/test_foundation.py` |
| Frontend API types match the backend | `make api-types-check` |
| Every API route passes through the authentication hook | `tests/test_api.py` |

## Commit messages

State what changed and why. Do not name the coding assistant or model that produced the
change in commit messages, code or documents.

## Stopping

At the end of a milestone or checkpoint, write the handoff from the template in `AGENTS.md`
and stop until the owner authorises the next one.
