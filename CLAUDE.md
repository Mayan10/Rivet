# Rivet: working rules for Claude Code

Rivet generates residential floor plans from a room program using a
guillotine slicing tree searched by simulated annealing, renders them to
PNG/SVG, and exports DXF. It is being turned into a subscription product.

## Read first
- `docs/architecture.md`
- `docs/design_rules.md`
- `docs/saas-buildout.md`
- `docs/prompts.md`

## Hard boundaries

1. **Layer separation is absolute.** `src/rivet/core/`, `src/rivet/render/`
   and `src/rivet/export/` are a pure library. They must never import from
   the service layer, touch a database, read environment variables, make
   network calls, or know that users, orgs, plans, or billing exist. Do not
   thread `user_id` or `org_id` into the generator. If a feature seems to
   need it, the answer is a parameter on the request object or a check in
   the service layer before the call.
2. **All service code lives in `src/rivet_service/`.**
3. **Determinism is a contract.** The same `GenerationRequest` and seed must
   produce byte-identical output across separate processes. Never introduce
   `set()` iteration, dict-ordering assumptions, `hash()` of a string, or
   unordered parallelism into the search path or anything downstream of it.
   Any change to search, scoring, or ordering needs a test that runs the
   same request in two subprocesses and compares output bytes.
4. **`pytest` must be green at the end of every task.** Never hand back a
   red suite.
5. **Every schema change goes through an Alembic migration.** No manual DDL,
   no `create_all()` outside test fixtures.
6. **No new runtime dependency** without telling me what it is, why the
   stdlib or an existing dependency is insufficient, and its maintenance
   status. Wait for my answer.

## Correctness rules

- Building code minimums are HARD constraints. They belong in a validator
  that rejects a layout, never in the soft penalty score. A layout that
  violates a code minimum must never be returned to a user, even if it is
  the best candidate available. Return an infeasibility result instead.
- Vastu, aesthetic preference, and adjacency desirability are SOFT. They go
  in the scorer. Never blur the two.
- Any dimensional value taken from a building code must carry a source
  comment naming the code and clause, for example
  `# NBC 2016 Part 3, cl. 12.2.1`. If you cannot cite it, do not hardcode
  it: surface it to me as a question instead.
- Never invent a code value. If you are unsure of a number, say so and stop.
- Geometry, area, and quantity figures are computed in exactly one place
  (`core/metrics.py`) and consumed by renderers, exporters, and the API.
  Never recompute an area inside a renderer or exporter.

## Style
- Match existing code style.
- Type hints on all public functions.
- New modules get tests in the same commit.
- Explain your plan before writing code for anything touching the search
  algorithm, auth, billing, or the download path. I need to be able to
  debug these without you.

## Working method
- Before implementing: list the files you will create or modify, and flag
  anything in my instructions that is wrong, ambiguous, or that you would
  do differently. Wait for my answer.
- Do not start the next phase. Stop when the current one is done.
