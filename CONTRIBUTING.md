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

Run the web UI locally:

```bash
python scripts/run_dev_server.py
# -> http://127.0.0.1:5000
```

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

Or via Docker (`docker compose up`, then `docker compose run --rm api
alembic upgrade head` once). `tests/service/` needs a reachable
`DATABASE_URL` and skips cleanly (not fails) without one, so `pytest -q`
stays green with no Postgres running at all.

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
- CI runs `ruff check` and `pytest` on 3.10–3.12; please make sure both
  pass locally first.

## Reporting bugs / requesting features

Open a GitHub issue using the templates under `.github/ISSUE_TEMPLATE/`.
For layout-quality bugs, include the exact request (plot + room program +
seed) that reproduces it — `rivet generate ... --seed N` output is
deterministic, so that's normally enough to reproduce your report exactly.
