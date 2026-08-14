# Contributing to Rivet

Thanks for considering a contribution. Rivet is a small, focused engine —
the bar for a good PR is that it's well-tested and doesn't grow the
dependency footprint without a strong reason.

## Development setup

```bash
git clone https://github.com/Mayan10/Rivet.git
cd Rivet
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run the test suite and linter before opening a PR:

```bash
pytest -q
ruff check src tests
```

Try the CLI end-to-end (also a fast way to sanity-check a change to the
engine without spinning up the web server):

```bash
rivet generate --width 15 --length 13 \
  --room living_room --room master_bedroom+ensuite \
  --room bedroom:2+ensuite --room kitchen --room dining_room --room bathroom \
  --seed 1 --out-dir /tmp/rivet-dev
```

Run the standalone demo server — the Flask app in `src/rivet/api/` with
the thin UI in `web/`, no database or accounts involved:

```bash
python scripts/run_dev_server.py
# -> http://127.0.0.1:5000
```

(That's separate from the product stack: the FastAPI service and the
Next.js app, both below.)

### Service layer (optional, `src/rivet_service/`)

The SaaS build-out (`docs/saas-buildout.md`) lives in a separate package
with its own dependency extra, so plain engine/CLI contributors never
need it:

```bash
pip install -e ".[dev,service]"
createdb rivet   # any local Postgres works; docker-compose.yml has one too
export DATABASE_URL=postgresql+psycopg://localhost/rivet
alembic -c alembic.ini upgrade head
uvicorn rivet_service.main:app --reload
```

`SECRET_KEY` (signs email-verification/password-reset tokens, see
`config.py`) has a dev-only default -- fine locally, must be overridden
anywhere real. Email verification and password reset don't send real
email yet (no provider is wired up -- Phase 7 status in
`docs/prompts.md`); the token is logged server-side instead.

Generations run as background jobs (Phase 8), so testing that path also
needs Redis, and the default storage backend is local disk (no extra
setup) -- S3 needs MinIO or real AWS S3:

```bash
brew install redis && brew services start redis   # or docker compose up redis
python -m rivet_service.jobs.worker                # separate terminal, consumes the queue
```

`tests/service/` skips whatever infra isn't reachable (Postgres, Redis,
MinIO each independently) rather than failing -- see
`tests/service/conftest.py`.

Or via Docker (`docker compose up`, then `docker compose run --rm api
alembic upgrade head` once). `tests/service/` needs a reachable
`DATABASE_URL` and skips cleanly (not fails) without one, so `pytest -q`
stays green with no Postgres running at all.

### Frontend (optional, `apps/web/`)

The Next.js app is a separate toolchain — Bun, not pip — so engine
contributors never need it either, and frontend contributors never need
the Python venv unless they're running the backend alongside.

```bash
bun install                 # repo root; it's a Bun workspace
bun run dev                 # mprocs: FastAPI on :8000 + Next.js on :3000
bun run --cwd apps/web dev  # or just the frontend, on :3000
```

The regression gate for the frontend is a full type-check plus lint, not
unit tests:

```bash
bun run --cwd apps/web lint
bun run --cwd apps/web build
```

More detail — configuration, layout, and conventions — is in
[`apps/web/README.md`](apps/web/README.md).

## Branches

Work is split by area, not by task, and there are three long-lived
branches. Please don't open a branch per feature.

- `main` — production. Never commit directly; everything lands via PR.
- `frontend` — work under `apps/web/`.
- `backend` — work under `src/`.
- `chore/<topic>` — CI, infra, tooling, docs; short-lived, deleted after
  merge.

Open (or update) a PR to `main` from the branch matching the area you're
changing, and after it merges, fast-forward that branch to `main` before
starting the next task on it. [`AGENTS.md`](AGENTS.md) has the full
rules, including the layering boundaries between the engine and the
service.

## Project layout

See [`docs/architecture.md`](docs/architecture.md) for how a request flows
through the system. In short:

- `src/rivet/core/` — the generation engine (models, rulebook, graph,
  layout search, scoring, opening placement). No I/O, no framework
  dependencies. This is the part to test most thoroughly.
- `src/rivet/render/` — turns a `Layout` into PNG/SVG. No dataset imagery,
  no external image assets — everything is drawn from geometry.
- `src/rivet/export/` — DXF export via `ezdxf`.
- `src/rivet/api/` and `web/` — the Flask API and its thin HTML/CSS/JS client.
- `src/rivet/cli.py` — scriptable entry point, also useful as a fast
  smoke test of the whole pipeline.
- `src/rivet_service/` — the SaaS service layer (FastAPI, Postgres,
  auth, billing -- `docs/saas-buildout.md`). Depends on `rivet.core`/
  `render`/`export`; nothing in those three ever imports back from here.
- `apps/web/` — the Next.js app (marketing site today, product UI next).
  Talks to `rivet_service` over HTTP only; holds no engine logic.

## Where contributions are most useful

- **Design rules** (`src/rivet/core/rules.py`): if you have domain
  expertise (architecture, civil engineering) and can point out a rule
  that's wrong, missing, or too US/India-centric, that's a high-value PR.
  Please include a rationale (a standard, a code reference, or a clear
  worked example) — these constants get cited by name elsewhere in the
  codebase and in `docs/design_rules.md`.
- **Layout search quality** (`core/layout_engine.py`, `core/scoring.py`):
  better heuristics, smarter simulated-annealing moves, or a genuinely
  different search strategy behind the same `search_layouts` interface.
- **Multi-storey support**: currently out of scope (see the README
  limitations section) — a well-scoped proposal for stacking floors
  (staircase alignment, structural continuity) is welcome as an issue
  before a large PR.
- **Renderer/exporter fidelity**: more accurate door/window symbols,
  hatching, furniture blocks in the DXF, etc.

## Testing expectations

- New behavior in `core/` needs a test in the matching `tests/test_*.py`.
- If you touch `core/layout_engine.py`, run the suite a few times locally
  (`pytest -q tests/test_layout_engine.py`) — it's a stochastic search, so
  a change that looks fine on one seed can regress another.
- If you change DXF output, `tests/test_dxf_export.py` round-trips the
  file through `ezdxf.readfile(...).audit()` — keep that passing with 0
  structural errors.

## Commit / PR style

- Keep PRs focused; separate refactors from behavior changes.
- Describe *why*, not just *what*, in the PR description — especially for
  rulebook or scoring-weight changes, where the reasoning matters more
  than the diff.
- CI runs `ruff check` and `pytest` on 3.10–3.12, plus a secret scan and
  a service-layer job against real Postgres/Redis/MinIO; please make sure
  the first two pass locally. Changes under `apps/web/` additionally run
  `lint` and `build` (`.github/workflows/web.yml`).

## Reporting bugs / requesting features

Open a GitHub issue using the templates under `.github/ISSUE_TEMPLATE/`.
For layout-quality bugs, include the exact request (plot + room program +
seed) that reproduces it — `rivet generate ... --seed N` output is
deterministic, so that's normally enough to reproduce your report exactly.
