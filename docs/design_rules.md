# Design rules

This is the human-readable version of [`packages/engine/rivet/core/rules.py`](../packages/engine/rivet/core/rules.py)
and [`packages/engine/rivet/core/validator.py`](../packages/engine/rivet/core/validator.py), which
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
| Every room reachable from the entrance | **Hard** | validator (Phase 3, belt-and-suspenders — see "Circulation" below) |
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
| Pooja | 1.0* | 0.9* | 2.5 | Rule 52(5)(b) [explicitly excluded from the habitable-room minimum; no separate minimum found] |

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
still checks only the simpler proxy — does the room have an exterior wall
at all — **not** the real area ratio, even though `core/metrics.py` (added
in Phase 2) now computes that ratio. This is deliberate, not an oversight:
computing a real opening *area* needs an assumed window *height* that
TNCDBR doesn't specify anywhere (the only place TNCDBR gives a direct area
figure is the bath/WC minimum — 0.5 m² — which needs no height assumption
at all). Hinging a hard rejection on an invented height would violate the
same principle this rulebook exists to enforce, just one level removed —
so the real ratio is reported as **informational metrics only**
(`RoomMetric.ventilation_passes` etc., surfaced through every renderer/
exporter/API consumer), and the validator's hard check stays the Phase 1
proxy. See "Metrics and quantity takeoff" below.

Note the interaction with the room table above: `DINING_ROOM` is
"habitable" (gets a ventilation figure computed) but has
`exterior_wall_required=False` in its `RoomRule` — so a dining room that
doesn't happen to land on an exterior wall will legitimately report
`ventilation_passes=False` with zero window area. That's an honest
reflection of the current rulebook's living/dining-as-one-zone design
choice, not a bug in the metric.

## Metrics and quantity takeoff (`core/metrics.py`, Phase 2)

Single source of truth for every geometry-derived number — before this
module, renderers, the DXF exporter, and the API each computed
`sum(r.rect.area for r in layout.rooms)` (and similar) independently.
`Layout.ruleset` records which ruleset a layout was generated against, so
downstream consumers compute metrics against the right one.

**Cited** (traceable to TNCDBR 2019):
- Ventilation ratio (Rule 52(16)(a)) — see above for why it's
  informational, not a hard check.
- **FSI cap = 2.0** (Rule 35(1)(a)/(b), row D — both the ≤16-dwelling and
  >16-dwelling "Other areas" tables cite the same figure for the
  residential case Rivet generates). `core/rules.py::fsi_permitted()`
  returns `None` for the `GENERIC` ruleset, which has no cited cap.

**Uncited assumptions** (`core/rules.py`, all explicitly flagged as
placeholders, none used to reject a layout):
- `WINDOW_HEIGHT_M` (1.20 m) and `DOOR_HEIGHT_M` (2.10 m) — needed to turn
  an opening's width into an area.
- `WALL_HEIGHT_M` (3.0 m) — floor-to-ceiling height for plaster/wall-area
  takeoff.
- `BLOCK_LENGTH_M` / `BLOCK_HEIGHT_M` / `MORTAR_JOINT_M` /
  `BLOCK_COUNT_WASTAGE_FACTOR` — a common Indian standard concrete block
  size and a +5% wastage allowance for the block-count estimate.

**Carpet vs. built-up vs. plinth area** — three genuinely different
numbers, not synonyms:
- *Carpet area*: each room's rect inset by half the thickness of whichever
  wall (external 0.23m or internal 0.115m) bounds each of its four edges.
  Net usable floor area.
- *Built-up area*: the buildable rect (bounded at the external wall
  *centerline*) expanded outward by half the external wall thickness on
  every side — area within the *outer face* of the external wall.
- *Plinth area*: currently equal to built-up area. Rivet doesn't model
  verandahs/porches (plinth-only projections beyond the building line)
  yet, so there's nothing to add on top of built-up — not an
  approximation so much as "nothing else exists in scope."

These three don't reconcile to an exact identity via simple wall-length x
thickness arithmetic for a real multi-room layout — each interior
T-junction double-counts a thickness² sliver slightly differently between
the per-room carpet inset and the running-length wall footprint
approximation. Measured at ~0.2% of built-up area for a 10-room layout;
`tests/test_metrics.py` asserts conservation within a deliberately
generous 1% bound, and additionally proves an *exact* match (to floating-
point precision) for the corner-simple single-room case where this effect
vanishes.

**Setback compliance table**: reports required vs. provided per face
(front/rear/left/right). Since `buildable` is always derived directly from
`setbacks_for()`, provided always exactly equals required today — an
honest reflection of the current architecture, not a bug; it'll become a
real check once something (e.g. a future asymmetric-placement feature)
can position a building within its buildable envelope rather than filling
it exactly.

**Quantity takeoff** relies on `core/walls.py::deduplicate_wall_segments`
/ `total_wall_length_by_class`: `compute_wall_segments()` deliberately
double-counts a shared interior wall (once per room, harmless for
rendering — two overlapping lines draw as one), which would double the
block count on every interior wall if used directly for a takeoff. The
dedup pass merges coincident/overlapping per-room segments into their true
unique runs first.

## Circulation (`core/layout_engine.py`, Phase 3)

Every generated layout carries one or more auto-generated corridor
segments (`RoomType.CORRIDOR` instances with IDs `circulation_1`,
`circulation_2`, ...) so that **every room is reachable from the entrance
through doors** — the Phase 0 audit's most severe finding was that nothing
enforced this. This is entirely automatic: a request never has to ask for
a `CORRIDOR` room to get one (an explicitly requested `CORRIDOR`/`FOYER`
still works, but becomes an *extra* named room alongside the auto-spine,
not a replacement for it).

- **`CIRCULATION_CORRIDOR_WIDTH_M` = 1.20 m** — built corridor width.
  Comfortably above the cited 1.0 m minimum (Rule 42(i)); not itself a
  separate citation.
- **`CIRCULATION_SINGLE_LOAD_THRESHOLD` = 3** — the max "primary" rooms
  (an en-suite bathroom nests with its bedroom and doesn't count
  separately) a single corridor-bordering cluster may hold before the
  splitter inserts another corridor branch instead of placing them
  directly. Keeps the auto-generated branching tree from producing an
  unrealistically deep sliver of a room.
- **`CIRCULATION_TARGET_PCT_MIN`/`MAX`** = 10–15% of built-up area — a
  **soft** scoring target band (`core/scoring.py`), never a hard
  rejection; the corridor-width construction above already guarantees the
  hard minimum by construction.
- **`min_door_clear_wall_m(room_type)`** — the real per-room-type hard
  floor: the shortest wall that room's own door (`door_width_for`) needs
  once corner clearances (`MIN_OPENING_EDGE_CLEARANCE_M`, 0.30 m) are
  subtracted from both ends. The circulation splitter enforces this as a
  floor on every room's stacking-axis span so a room is never cut so thin
  its only connecting wall can't actually take a door — a bathroom's own
  door only needs 1.35 m, but a bedroom's internal door needs 1.5 m, so a
  flat constant undercounted every non-bathroom room type (the actual bug
  the reachability hard check below caught during Phase 3).

**Reachability is guaranteed two ways, deliberately redundant:**

1. **By construction**: the splitter's corridor-insertion rule is
   monotonic top-down (any corridor inserted below the root implies every
   ancestor split up to the root was also a corridor split), so the whole
   corridor tree is transitively connected back to the entrance, and every
   leaf room touches whichever corridor immediately bounds it.
2. **By validation**: `core/validator.py`'s reachability check walks the
   *actual* door graph (`Layout.openings`), BFS from whichever room the
   main entrance door opens into, and hard-rejects any layout where a room
   isn't reachable. This is the check that actually caught real bugs
   during Phase 3 that construction alone didn't prevent: a floating-point
   edge case in `geometry.py::shared_wall`'s length comparison, a missing
   opening between two corridor segments meeting at a junction
   (`core/openings.py`), and the door-fit floor described above.

En-suite bathrooms are the one deliberate exception: they connect only via
their own bedroom's door, never directly to circulation — both
`core/openings.py::_place_corridor_doors` and the reachability check treat
this the same way (a reachable bedroom makes its en-suite reachable too).

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

## Vastu (`core/vastu.py`, Phase 5 — optional, uncited, soft-only)

**Disabled by default.** Vastu shastra is a traditional Indian
architectural belief system, not a building code — nothing in this
section is cited, none of it is enforced by `core/validator.py`, and it
is never mixed into the hard/soft code-compliance table above. Enable it
per-request via `GenerationRequest.vastu = VastuOptions(enabled=True,
weight=..., plot_north=...)`; `Layout.vastu_preferences` (a separate list,
never merged into `Layout.score_breakdown`'s plain float dict) and the
API's `vastu_preferences` field report exactly which preferences were
satisfied or violated, always kept structurally apart from anything code-
compliance-related so a result can never be misread as "violates NBC/
TNCDBR" when it's really "violates a vastu preference."

**`plot_north` is required whenever vastu is enabled** — there is no
default. `core/models.py`'s coordinate convention ("x → east, y → north")
is a drawing-space assumption of convenience, not necessarily a given
plot's real surveyed orientation; vastu is the one place in this codebase
where that distinction changes an answer, so it's never silently
inherited. `plot_north` names which *drawing* axis actually points at
true north for this specific plot (reusing the same `Orientation` enum as
`PlotSpec.entrance`); every direction check rotates into a true-north-
aligned frame before classifying a room (see `core/vastu.py::true_compass_zone`).

Rooms are classified into one of 8 compass sectors (45° each) by the
bearing from the buildable rectangle's center to the room's own center —
the standard simplified division most practical vastu tools use, not the
finer vastu-purusha-mandala grid. Preferences checked:

| Preference | Rule | Room type |
|---|---|---|
| `kitchen_southeast` | should be in the SE (Agni) zone | Kitchen |
| `master_bedroom_southwest` | should be in the SW (Nairutya) zone | Master bedroom |
| `pooja_northeast` | should be in the NE (Ishanya) zone | Pooja |
| `toilet_avoid_northeast` | should avoid the NE (Ishanya) zone | Bathroom, Toilet |
| `entrance_orientation` | main entrance should face N, NE, or E | — |

Each violated preference adds a fixed penalty (`vastu.W_VASTU_VIOLATION`,
uncited by construction) scaled by `VastuOptions.weight`, added to
`score_breakdown["vastu"]` — present only when vastu is enabled, so a
disabled request's breakdown is byte-identical to before this module
existed.
