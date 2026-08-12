# Design rules

This is the human-readable version of [`src/rivet/core/rules.py`](../src/rivet/core/rules.py)
and [`src/rivet/core/validator.py`](../src/rivet/core/validator.py), which
are the single source of truth — if this document and the code disagree,
the code is right and this file needs an update. Raw source extraction
(page numbers, full clause text) lives in
[`docs/regulatory_sources.md`](regulatory_sources.md).

Two rulesets ship, selected per-request via `GenerationRequest.ruleset`:

- **`TNCDBR_2019`** (default) — cited values from the Tamil Nadu Combined
  Development and Building Rules, 2019 (base text, February 2019 edition).
  Not yet checked against TNCDBR's 14 post-2019 amendment G.O.s — see
  `docs/regulatory_sources.md`.
- **`GENERIC`** — uncited placeholder values, kept as a fallback for
  jurisdictions without a cited ruleset yet. Every value in it is
  explicitly flagged `"uncited placeholder"` in `core/rules.py` — don't
  present its output as code-compliant.

These are a residential design **assistant**, not a substitute for a
licensed engineer's stamped drawings or your local building code, which
always takes precedence.

## Hard vs. soft

This is the most important distinction in the rulebook, enforced by
splitting it across two modules:

- **Hard** (`core/validator.py`): a layout that fails one of these is
  never returned to a user, full stop — `core/generator.py` searches for
  another candidate instead, and reports an explicit `InfeasibleResult`
  if nothing satisfies every hard constraint. Hard constraints are cited.
- **Soft** (`core/scoring.py`): a weighted penalty that ranks candidates
  against each other. A layout can violate a soft preference and still be
  returned — its score just reflects that.

| Constraint | Hard or soft | Where |
|---|---|---|
| Room minimum area / width | **Hard** | validator, cited per room type below |
| Exterior window access (habitable rooms) | **Hard** | validator, proxy for Rule 52(16)(a) — see below |
| Bathroom/toilet not opening onto kitchen | **Hard** | validator, cited (Rule 52(7)(c)(vi)) |
| Setback compliance | **Hard** | validator (defensive check — buildable area is derived from setbacks by construction) |
| Door widths | *(not enforced)* | uncited — see "Gaps" |
| Adjacency preference | Soft | scorer |
| Aspect ratio | Soft | scorer |
| Area error vs. target | Soft | scorer |
| Entrance placement | Soft | scorer |
| Other avoided adjacencies (bathroom/toilet ↔ dining) | Soft | scorer (uncited, so not promoted to hard) |

## Per-room space standards (TNCDBR_2019)

| Room | Min area (m²) | Min width (m) | Default target (m², soft) | Citation |
|---|---|---|---|---|
| Living room | 7.5 | 2.4 | 18.0 | Rule 52(5)(b) [habitable room] |
| Master bedroom | 7.5 | 2.4 | 14.0 | Rule 52(5)(b) [habitable room] |
| Bedroom | 7.5 | 2.4 | 11.0 | Rule 52(5)(b) [habitable room] |
| Study | 7.5 | 2.4 | 9.0 | Rule 52(5)(b) [habitable room] |
| Kitchen (separate dining exists) | 5.0 | 1.8 | 8.0 | Rule 52(6)(b) |
| Kitchen (doubles as dining) | 7.5 | 2.1 | 8.0 | Rule 52(6)(b) |
| Dining room | 7.5 | 2.4 | 10.0 | Rule 52(5)(b) [habitable room] |
| Bathroom | 1.4 | 1.0 | 3.5 | Rule 52(7)(b) |
| Toilet (WC) | 1.0 | 0.9 | 1.8 | Rule 52(7)(b) |
| Garage (private) | 18.0 | 3.0 | 18.0 | Rule 52(10)(a) [3.0m x 6.0m min] |
| Store room | 3.0 | 1.2* | 3.0 | Rule 52(9) [*width uncited] |
| Foyer | 2.5* | 1.2* | 4.0 | uncited placeholder |
| Corridor | 1.0* | 1.0 | 2.5 | Rule 42(i) [*area uncited, width only] |
| Staircase | 4.0* | 0.75 | 5.0 | Rule 52(17)(a)(i) [*area uncited, width only] |
| Utility | 2.5* | 1.2* | 3.5 | uncited placeholder |
| Balcony | 2.0* | 1.0* | 3.5 | uncited placeholder |

Values marked `*` are uncited (either the whole row, for rooms TNCDBR
doesn't specifically cover, or just that one dimension). The **kitchen
minimum is context-dependent**: `core/validator.py` checks whether the
layout also has a `DINING_ROOM` and applies the matching Rule 52(6)(b)
figure — `core/rules.py::kitchen_minimum()` is the single source of that
logic, not a static table lookup.

"Default target" is a **soft** generation target the layout search aims
for absent a user-specified area — a design choice, not part of any
citation, and never enforced as a minimum or maximum.

"Max aspect ratio" (not shown above, see `core/rules.py::RoomRule`) caps
how long-and-thin a room is allowed to get relative to its shorter side
before the *scorer* penalizes it — always soft, never code-derived.

## Exterior window access

Rule 52(16)(a): minimum aggregate window/ventilator opening area must be
at least **1/8 of floor area** (25% more for kitchens). `core/validator.py`
currently checks a simpler proxy — does the room have an exterior wall at
all — not the real area ratio; the full ratio calculation is planned for
`core/metrics.py` (`docs/prompts.md` Phase 2), which is why this line
item is listed as "hard" above but with an explicit caveat in its
`Violation.source` string.

## Construction standards

- External wall thickness: **0.23 m** (~9", typical masonry perimeter wall) — uncited
- Internal wall thickness: **0.115 m** (~4.5", half-brick partition) — uncited
- Door widths: main entrance **1.00 m**, internal **0.90 m**, bathroom
  **0.75 m** — **uncited**, not found in TNCDBR's general residential
  provisions (the only door widths in the source text are under Rule 43,
  differently-abled accessibility). Not enforced by the validator until a
  citation exists — see `docs/regulatory_sources.md` "Gaps".
- Window widths: habitable rooms **1.20 m**, kitchen **0.90 m** — uncited
- Minimum corridor/passage width: **1.00 m** — **Rule 42(i)**, residential
  buildings
- Openings are kept at least **0.30 m** clear of a wall's corner — uncited,
  a drafting convention

## Setbacks (TNCDBR_2019, Rule 35)

Keyed by **abutting road width** and **building height**, not plot area —
the "Other areas" column of Rule 35(1)(a)/(b), the applicable one for an
individual residential building (the CBA/EWS columns are area
classifications a single house doesn't fall under). Both inputs are
optional on `PlotSpec`; when omitted, `ASSUMED_ROAD_WIDTH_M` (9.0m) and
`num_floors * ASSUMED_FLOOR_HEIGHT_M` (3.0m/floor) are used as documented,
non-cited assumptions.

**Front**, by abutting road width:

| Road width | Front setback |
|---|---|
| ≤ 9.0 m | 1.5 m |
| 9.0 – 18.0 m | 3.0 m |
| 18.0 – 30.5 m | 4.5 m |
| > 30.5 m | 6.0 m |

**Side**, by building height and plot width (applied symmetrically on both
sides — see below):

| Height | Side setback |
|---|---|
| ≤ 7.0 m | 1.0 m |
| 7.0 – 12.0 m, plot width ≤ 6.0 m | 1.0 m |
| 7.0 – 12.0 m, plot width > 6.0 m | 1.5 m |
| 12.0 – 16.0 m | 2.5 m |
| 16.0 – 18.30 m | 3.0 m |

**Rear**, by building height:

| Height | Rear setback |
|---|---|
| ≤ 7.0 m | 0.0 m |
| 7.0 – 12.0 m | 1.5 m |
| 12.0 – 16.0 m | 2.5 m |
| 16.0 – 18.30 m | 3.0 m |

Simplification: TNCDBR's table permits a single-side-only setback for some
height/plot-width combinations (leaving the other side at zero, e.g. for a
party wall). Rivet always applies the setback symmetrically on both
sides — never less space than the code requires, only possibly more
conservative than strictly necessary. Heights above 18.30m fall outside
TNCDBR's Non-High-Rise Rule 35 entirely (High Rise rules aren't
implemented); Rivet clamps to the 16–18.30m tier rather than erroring.

**GENERIC ruleset**: falls back to the original uncited plot-area-tiered
heuristic (≤150/300/500 m² → 1.5/3.0/4.5/6.0 m front, etc.) — see
`core/rules.py::_GENERIC_SETBACK_TIERS`.

## Adjacency

**Preferred** (soft — the layout search rewards realizing these as a shared wall):

- Kitchen ↔ Dining room
- Dining room ↔ Living room
- Living room ↔ Foyer
- Foyer ↔ Corridor
- Corridor ↔ Bedroom / Master bedroom / Bathroom
- Kitchen ↔ Utility
- Garage ↔ Foyer
- Staircase ↔ Corridor / Foyer

A bedroom requested with `attached_bathroom=True` gets its own dedicated
en-suite bathroom node with a **required** (not just preferred) adjacency
edge to that specific bedroom — worth double the score weight of a
preferred edge, and the only bathroom that bedroom's en-suite is expected
to touch. There's deliberately no generic "bedroom prefers bathroom"
rule: combined with per-instance en-suite pairing, that would ask *every*
bedroom to sit next to *every* bathroom in the request, an edge count no
single-wall-per-room geometry could satisfy — it was an actual bug caught
during development (see `tests/test_rules.py::test_no_generic_bedroom_bathroom_preference`).

**Avoided**, split into hard and soft:

- **Hard** (validator rejects, cited — TNCDBR 2019, Rule 52(7)(c)(vi),
  "the door of the water closet or bath not to be directly opened to a
  kitchen"): Bathroom/toilet ↔ Kitchen
- **Soft** (scorer penalizes, uncited): Bathroom/toilet ↔ Dining room

## Entrance placement

Soft only. The plot-boundary wall the entrance orientation points at
should open into a foyer, living room, corridor, or garage — not directly
into a bedroom or bathroom.
