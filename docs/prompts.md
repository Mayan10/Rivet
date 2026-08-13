# Rivet: the complete Claude Code prompt set

## How to use this

1. Save `rivet-saas-buildout.md` to `docs/saas-buildout.md` in the repo.
2. Save this file to `docs/prompts.md`.
3. Create `CLAUDE.md` at the repo root with the content in section 1 below.
   Claude Code reads it automatically at the start of every session, so you
   never re-paste the constraints.
4. Run Phase 0 first. Its output will correct several assumptions in the
   later phases. Update the phases before running them.
5. One phase per session. `/clear` between phases. Review the diff and
   commit before starting the next one.

Do not paste phases 1 through 12 at once.

---

## 1. `CLAUDE.md` (create this file first, copy verbatim)

```markdown
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
```

---

## 2. Phase 0: orientation and audit

Run this first. Do not skip it. Everything below was written from the README
and architecture doc, so some of it will be wrong about the actual code.

```
Read CLAUDE.md, then read the codebase. Do not write any code this session.

Produce an audit answering these, with file and line references:

ENGINE
1. Where does scoring happen, and is every check a soft weighted penalty or
   are any of them hard rejections? List every constraint currently checked
   and classify each as hard or soft.
2. Does any generated layout currently include circulation space (corridor,
   foyer, landing)? If not, confirm that the guillotine tiling means 100% of
   the buildable rectangle is assigned to program rooms.
3. In `openings.place_openings`, how is the door graph decided? Can a bedroom
   currently be reachable only by passing through another bedroom? Show me a
   seed and room program where that happens, or prove it cannot.
4. How are setbacks computed? Quote the function. Does the request object
   carry abutting road width or proposed building height?
5. Where are room minimum dimensions defined, and is there a source citation
   for any of the values?
6. Is there a version constant for the rulebook or engine? If not, say so.

EXPORT
7. In `export/dxf.py`: what units are coordinates written in? Is `$INSUNITS`
   set? What is text height and is there a DIMSCALE?
8. Are doors, windows, fixtures, and the north arrow written as BLOCK
   definitions with INSERT, or as inline geometry in modelspace? List every
   entity type the exporter currently emits.
9. Are dimensions real DIMENSION entities, or lines plus TEXT?
10. Is there a paper space LAYOUT, a viewport, or a title block?
11. Are HATCH entities used anywhere? Are lineweights or linetypes set per
    layer?

AREA AND METRICS
12. Every place in the codebase that computes an area, a percentage, or a
    count from layout geometry. I expect duplication between the renderers,
    the exporter, and the API. List each occurrence.

TESTS
13. What does the test suite actually cover? Is there any test that opens a
    generated DXF and asserts its contents? Is there a determinism test that
    spans two processes?

Then list, in your own judgement, the five changes that would most improve
output quality, and tell me where you disagree with my priorities in
docs/prompts.md.
```

**Before running Phase 1, edit the phases below to match what the audit
found.**

---

## 2a. Phase 0 audit results (2026-08-11) and how it changed the plan

Phase 0 was run against the actual codebase (not the README/architecture
docs it was written from) and confirmed most of the plan's assumptions, with
one finding serious enough to reorder the phases below. Full audit is in the
session history; the parts that change what you should do are:

- **The engine's floor plans are frequently not navigable at all, not just
  "bedroom reachable through another bedroom."** Reproduced with
  `plot=12m x 15m`, rooms `[living_room, master_bedroom+ensuite,
  bedroom:2+ensuite, kitchen, dining_room, bathroom]`, `seed=42` (no
  corridor/foyer requested, the common case): the living room ends up with
  a front door and **zero interior doors**; each bedroom has a door to
  **only its own en-suite**, none to anything else; the plain requested
  bathroom gets **no door at all**. `openings.place_openings()` only draws
  a door where a graph edge exists, and the rulebook has no
  `LIVING_ROOM <-> BEDROOM`/`KITCHEN` preference — only corridor-mediated
  ones — so without a requested corridor/foyer, most rooms are sealed.
  This is a functional defect above the "code minimums are unenforced"
  defect the original plan targeted with Phase 1.
- **Consequence: circulation (originally Phase 4) now runs before the DXF
  export overhaul (originally Phase 3).** Producing a beautifully blocked,
  AIA-layered, mm-accurate DXF of a house nobody can walk through is wasted
  effort right before the room topology changes shape. The phases below are
  renumbered accordingly — circulation is now **Phase 3**, DXF export is
  now **Phase 4**. The service phase numbers (6-12) are unaffected.
- **The audit corrected one assumption in the original Phase 3 (DXF) brief**:
  dimensions are already real `DIMENSION` entities with `.render()` already
  called (not lines-plus-TEXT as assumed), so that specific item is smaller
  than scoped — see the note inside the phase below. Everything else in
  that phase (units in meters not mm, no BLOCK/INSERT, no HATCH, no paper
  space, non-AIA layer names) was confirmed as a real gap.
- **No automated test currently spans a process boundary.** The existing
  `test_same_seed_is_deterministic` calls `generate()` twice in the same
  pytest process, which would not have caught the real cross-process
  `PYTHONHASHSEED` determinism bug this codebase hit earlier (fixed by
  swapping a `set()` for an insertion-ordered `dict` in
  `layout_engine._graph_guided_order`; see `docs/architecture.md`). Phase 1
  below now explicitly asks for a new subprocess-spanning test rather than
  just "the determinism test still passes."
- No disagreement with anything else in this document — rulebook citation
  requirements, validator shape, metrics contents, and circulation design
  constraints all matched what the code needed.

---

## 3. Engine phases

### Phase 1: split hard constraints from soft scoring

**Status: done (2026-08-12).** `core/validator.py`, cited `TNCDBR_2019`
ruleset, `Ruleset`/`InfeasibleResult` end-to-end through CLI and API,
cross-process determinism test. 91 tests passing. Carried forward, not
done in this phase:

- Door widths remain uncited and unenforced (see
  `docs/regulatory_sources.md` "Gaps") -- needed before Phase 4 (DXF
  export) can size door BLOCK definitions off anything but a placeholder.
- The web UI form doesn't expose `ruleset`/road-width/height inputs yet
  (CLI and API do); `app.js` only handles the new infeasible-result
  response shape without crashing.
- TNCDBR's 14 post-2019 amendment G.O.s still haven't been checked
  against Rule 35/52 -- the cited values are from the unamended base text.
- The exterior-window-access hard check is a has-exterior-wall proxy, not
  the real Rule 52(16)(a) 1/8-of-floor-area ratio -- that's Phase 2
  (metrics) work.

```
Read CLAUDE.md. Implement Phase 1 only.

Goal: building code minimums become hard constraints that reject a layout,
separate from the soft penalty score that ranks surviving layouts.

1. Add `core/validator.py` with a `validate_layout(layout, rules) ->
   ValidationResult` returning a list of structured violations
   (constraint_id, severity, room_id, message, actual, required, source).
2. Move every hard check out of the scorer into the validator: minimum
   habitable room area and width, minimum kitchen and bathroom area,
   exterior window access for habitable rooms, minimum door widths,
   setback compliance. Leave adjacency preference, aspect ratio, area error
   and entrance placement in the scorer as soft penalties.
3. `generate()` filters out invalid candidates. If every candidate is
   invalid, return an `InfeasibleResult` carrying the violations that were
   hardest to satisfy, not a bad layout. The CLI and API must surface this
   as a real, explainable outcome, not an exception.
4. Add `RULEBOOK_VERSION` and `ENGINE_VERSION` constants. Bump RULEBOOK
   on any rule change.
5. Extend `PlotSpec` with `abutting_road_width_m` and
   `proposed_height_m` (both optional, with documented defaults), and
   rewrite `setbacks_for()` to key off road width and height rather than
   plot area. Make the setback table a named, swappable ruleset so a
   different jurisdiction can be plugged in later; ship
   `TNCDBR_2019` and a `GENERIC` fallback.

Every dimensional value you write must carry a source comment naming the
code and clause. I will supply the clause values. Ask me for any number you
do not have a citation for. Do not invent one, and do not copy one from a
blog result.

Tests: a layout that violates a minimum must never be returned; the
infeasible path returns violations; setbacks change correctly with road
width and height; the existing determinism test still passes.

Also add a NEW test that spans an actual process boundary: run the same
GenerationRequest + seed through `python -m subprocess` (or
`multiprocessing` with the `spawn` start method, not `fork`, so it doesn't
inherit the parent's hash seed) at least twice and assert byte-identical
output. The current suite only proves determinism within one pytest
process, which previously missed a real `set()`-iteration-order bug in
`layout_engine._graph_guided_order` that only showed up across separate
`python3` invocations. Put this test somewhere it will run for every future
change to `core/layout_engine.py` and `core/scoring.py`, not just this one.
```

### Phase 2: single source of truth for metrics

**Status: done (2026-08-12).** `core/metrics.py` (`compute_metrics`,
`LayoutMetrics`), `core/walls.py` gained a wall-segment dedup pass
(`deduplicate_wall_segments`/`total_wall_length_by_class`) since quantity
takeoff needs each physical wall counted once, not once per room touching
it. `Layout` gained a `ruleset` field so consumers that only see the
layout (not the original request) still compute metrics against the right
ruleset. All four duplicate-computation sites found in the Phase 0 audit
(raster.py, svg.py, dxf.py, api/schemas.py) now read `LayoutMetrics`
instead of computing their own `sum(r.rect.area ...)`; the API also
gained a full `metrics` payload (carpet/built-up/plinth area, circulation
%, ground coverage, FSI, setback table, door/window schedules, quantity
takeoff). 102 tests passing (11 new in `test_metrics.py`, including a
hand-checked exact-value case and an explicit renderer/exporter/API
consistency check).

One design decision made explicit and recorded in
`docs/design_rules.md`: the real ventilation ratio (Rule 52(16)(a)) is
**informational only** -- `core/validator.py` keeps the Phase 1
has-exterior-wall proxy as its actual hard check, rather than hinging a
rejection on the uncited window-height assumption the real ratio needs.

Carried forward: window/door/wall height and block-dimension constants
remain uncited placeholders (flagged in `core/rules.py`, same treatment as
Phase 1's door widths); Rivet still doesn't model verandah/porch area, so
plinth area is currently identical to built-up area, not a distinct
figure.

```
Read CLAUDE.md. Implement Phase 2 only.

Add `core/metrics.py` with `compute_metrics(layout, plot, rules) ->
LayoutMetrics`. It computes, once:

- carpet area per room; total carpet, built-up and plinth area
- circulation area and circulation as a percentage of built-up area
- ground coverage percentage; FSI consumed and FSI permitted
- setback compliance table: required vs provided per face
- per habitable room, window opening area as a percentage of that room's
  floor area, with pass/fail against the ventilation clause
- door and window schedule: tag, type, size, count, total opening area
- quantity takeoff: running metres of exterior and interior wall by
  thickness, plaster area, block count estimate, floor finish area by room

Then remove every duplicate area or count calculation you found in the
Phase 0 audit from the renderers, the exporter and the API, and have them
all read `LayoutMetrics`. This is a refactor: no consumer should compute
geometry-derived numbers itself any more.

Quantity takeoff assumptions (wastage factor, block size, mortar joint)
must be named constants in one place with comments, not magic numbers
inline.

Tests: metrics on a known fixed layout match hand-checked values; areas of
all rooms plus circulation plus wall footprint equal built-up area within a
stated tolerance; renderers and exporter produce identical numbers.
```

### Phase 3: circulation

**Status: done (2026-08-12).** Chosen approach: circulation as a
first-class element woven directly into the slicing-tree recursion
(`layout_engine.build_circulation_layout`), not a pre-reserved spine or a
post-search carve — see the design discussion this session for the
tradeoffs against the other two options. Three explicit decisions made and
confirmed before writing code: a spine is *always* generated (never
conditional on room count), an explicitly-requested `CORRIDOR`/`FOYER`
room becomes an extra named room alongside the auto-spine rather than
replacing it, and full branching support was built now rather than a
single-spine MVP. `core/validator.py` gained the hard reachability check
(BFS over the actual door graph from the entrance); `tests/test_reachability.py`
stress-tests it (73 cases: 3 room programs x 2 plot sizes x 4 entrance
orientations x 3 seeds, none requesting an explicit `CORRIDOR`, the exact
scenario the original bug was found in) plus one concrete always-feasible
positive case. 175 tests passing.

Construction alone (the monotonic top-down corridor-insertion rule)
guarantees connectivity, but three real bugs surfaced only once the
validator's reachability check went in and started rejecting its own
output — worth recording since none were hypothetical:

1. **Ensuite-pair splitting could cost either the bedroom or its ensuite
   exterior access** (an earlier version split along the corridor-facing
   axis to steer the bedroom toward the corridor, which reliably gave up
   the *other* end of that axis). Fixed by forcing the same cut axis at
   every recursion depth (`layout_engine._slice_tree_forced_axis`), so a
   room retains the full span of whichever dimension isn't being cut, all
   the way down.
2. **A room's corridor-facing wall could be shorter than any door needs**:
   the splitter divided a wing's stacking axis proportionally by target
   area, and a small-target room (e.g. a standalone bathroom) could get
   squeezed under the door-fit minimum — reproducible even on generously
   sized plots, not just tight ones. Fixed with a hard floor
   (`rules.min_door_clear_wall_m`, per room type since a bathroom's own
   door needs less clearance than an internal door) enforced at every
   split in the circulation splitter.
3. **Two supporting fixes the above exposed**: `geometry.shared_wall`'s
   `min_length` comparison had no floating-point tolerance, so a wall cut
   to *exactly* the floor value could fail the check by a few ULPs; and
   `openings._place_corridor_doors`'s junction opening (where two corridor
   segments meet) reused the room-door helper, which subtracts corner
   clearance from both ends of a width that's already sized to the *whole*
   wall — always failing to fit. Both fixed; see `core/geometry.py` and
   `core/openings.py`.

Carried forward: circulation area is checked against Rule 42(i)'s 1.0m
minimum width only by construction (`CIRCULATION_CORRIDOR_WIDTH_M` builds
at 1.20m, comfortably above it); the 10-15% built-up-area target band is
soft/uncited, an engineering choice not a code figure.

```
Read CLAUDE.md. Implement Phase 3 only. This is the largest change in the
project. Present your design and wait for my approval before writing code.

Problem, confirmed against the actual engine during the Phase 0 audit: the
guillotine slicing tree tiles the buildable rectangle completely, so 100%
of area is program rooms, and doors are only placed where the adjacency
graph has an edge. With no corridor/foyer requested (the common case),
most rooms end up with NO door to anything but their own en-suite, and a
plain requested bathroom can end up with no door at all. Reproduced with
plot 12m x 15m, rooms [living_room, master_bedroom+ensuite, bedroom:2+ensuite,
kitchen, dining_room, bathroom], seed 42: the living room has a front door
and zero interior doors. This is worse than "bedroom reachable only through
another bedroom" — it's frequently "room unreachable, full stop." No
architect will accept it.

Goal: circulation becomes a first-class element that rooms attach to.

Design constraints:
- Every room must be reachable from the main entrance without passing
  through another program room. En-suite bathrooms are the only permitted
  exception, and only from their own bedroom. Make this a HARD constraint in
  the validator from Phase 1.
- Circulation should land in a configurable band (roughly 10 to 15 percent
  of built-up area) with minimum corridor width from the code. Over and
  under target are soft penalties; below minimum width is a hard reject.
- Determinism must survive. This is non-negotiable.

Present at least two approaches with tradeoffs before choosing. Options
worth considering: reserving a circulation spine in the buildable rectangle
before the room search runs; treating circulation as a pseudo-room in the
slicing tree with special adjacency handling; or a post-search corridor
carve with re-validation. Tell me which you recommend and why, including the
effect on search time and on how much of the existing layout_engine
survives.

Then rewrite `openings.place_openings` so doors open onto circulation by
default, and add a reachability test asserting the hard constraint above
across a large randomised set of room programs and seeds -- specifically
including room programs with no corridor/foyer requested, since that's the
case that currently fails.
```

### Phase 4: DXF export overhaul

**Status: done (2026-08-13).** Targeted the installed ezdxf 1.4.4 API
(stable since ~1.0/1.1 for everything this phase needed, so the
`ezdxf>=1.1.0` pin didn't change). `src/rivet/export/dxf.py` became a
package (`src/rivet/export/dxf/`: `core.py`, `units.py`, `layers.py`,
`blocks.py`, `walls_geometry.py`, `dimensions.py`, `sheet.py`) — the
public import path (`from rivet.export.dxf import export_dxf`) is
unchanged. All 8 items shipped:

1. Millimetre coordinates (`$INSUNITS=4`); every conversion happens once,
   in `units.py`, at the point a coordinate is written into an ezdxf
   call — core/render stay in metres, untouched.
2-3. BLOCK/INSERT for doors, windows, north arrow, title block, and
   schematic sanitary/kitchen fixtures, with ATTDEF/ATTRIB
   (TAG/TYPE/WIDTH_MM/HEIGHT_MM/ROOM) on doors and windows. One
   definition per type; doors/windows scale and rotate per instance
   (rotation + mirrored y-scale from a single canonical quarter-circle
   block — only 4 discrete orientations are possible, see
   `blocks.py::_DOOR_ORIENTATION`).
4. Per-room dimension chains added alongside the existing overall
   width/length dimensions, rescaled for millimetres with a dedicated
   `RIVET` dimstyle (`DIMSCALE` tied to the fixed 1:100 print scale).
5. Masonry hatch (`ANSI31`, ezdxf's built-in pattern — no external `.pat`
   file needed) on true rectangular wall-boundary polylines (not the old
   `const_width` centerline trick), with per-layer lineweights (heaviest
   on cut walls, lightest on annotation).
6. AIA CAD Layer Guidelines names (`A-WALL-EXTR`, `A-DOOR`, `A-GLAZ`,
   ...) are now the **default** layer scheme; the original names are
   still selectable via `layer_scheme="legacy"`.
7. A paper-space `Sheet` layout with a viewport locked at 1:100
   (`VSF_LOCK_ZOOM`), sized to exactly fit the plot rather than a named
   ISO sheet (every sheet is generated per-request, so there's no fixed
   physical target to round to). Title block metadata (project/client/
   date/sheet/revision) are new **export-time keyword arguments**
   (`TitleBlockInfo`), never threaded into `GenerationRequest` or
   `Layout` — matches CLAUDE.md's rule that core/ never knows about
   anything service- or user-facing. The disclaimer text is baked into
   the block as static MTEXT (genuinely fixed, not a per-drawing value),
   not an ATTRIB.
8. Door/window/room schedules are drawn as plain paper-space TEXT rows
   sourced from `core/metrics.py`'s `LayoutMetrics` at export time, not
   FIELD entities (which don't recalculate outside AutoCAD, per the
   phase's own instruction).

Fixture placement is explicitly schematic (one representative block per
relevant room at a fixed anchor point) — this codebase has no
wall-adjacency-aware fixture-layout algorithm, and building one is a
substantially larger feature than the block/attribute plumbing this phase
is actually about. Flagged and confirmed with the user before
implementing, along with the layer-scheme default and title-block
metadata questions above.

`tests/test_dxf_export.py` was rewritten for all of the phase's own
testing requirements (round-tripped through `ezdxf.readfile`/`ezdxf.read`
for every assertion): block definitions exist, INSERT count matches
door/window count, every wall boundary polyline is closed, layers exist
with the right color/lineweight ordering, `$INSUNITS` is set, dimension
geometry was generated, the paper-space layout and locked viewport exist,
schedules reflect `LayoutMetrics`, and a golden-file entity-type-census
test (`tests/fixtures/dxf_golden_census.json`, regenerate deliberately
with `scripts/regenerate_dxf_golden.py`) guards against unintended
structural regressions. 187 tests passing.

One honest finding, not fixed: raw DXF bytes are not byte-identical
across repeated exports of the *same* `Layout` -- but only in 4 lines out
of ~33,900 (two ezdxf-generated header GUIDs and two save timestamps),
never geometry or entity content. This is standard DXF file hygiene (real
CAD tools regenerate these on every save too), not a violation of
CLAUDE.md's determinism contract, which is about the search/layout result
being reproducible -- and it is, verified directly by the golden-file
entity-census test using a fixed seed.

```
Read CLAUDE.md. Implement Phase 4 only. Read the ezdxf documentation before
you start and tell me which version's API you are targeting.

Rewrite `export/dxf.py` so the output is a real CAD deliverable, not layered
polylines.

1. UNITS. Write coordinates in millimetres. Set $INSUNITS explicitly. Size
   text heights and DIMSCALE so annotation prints legibly at 1:100. This is
   the highest priority item: metre-unit output makes the file unusable for
   every Indian practice.
2. BLOCKS. Doors, windows, sanitary fixtures, kitchen units, north arrow,
   and title block become BLOCK definitions placed with INSERT. One
   definition per type, scaled and rotated per instance. Not inline
   geometry.
3. ATTRIBUTES. ATTDEF on the definitions and ATTRIB on each insert carrying
   tag, type, width, height, and host room, so AutoCAD DATAEXTRACTION can
   build a schedule from the file.
4. DIMENSIONS. Audit finding: overall-width and overall-length DIMENSION
   entities already exist (`export/dxf.py`, `add_linear_dim(...).render()`
   is already called, so the associated geometry block is already
   generated -- the "dimensions invisible in some viewers" failure mode
   this item originally warned about is already avoided). What's still
   missing: per-room dimension chains, not just the two overall dimensions.
   Add those, reusing the existing DIMSTYLE, and rescale it for the new
   millimetre coordinates from item 1.
5. HATCH, LINETYPE, LINEWEIGHT. Masonry hatch on cut walls with proper
   boundary paths. Load every linetype you reference into the LTYPE table.
   Set per-layer lineweights: heaviest on cut walls, lightest on annotation.
6. LAYERS. Switch to AIA CAD Layer Guidelines naming (A-WALL-EXTR, A-DOOR,
   A-GLAZ, A-ANNO-DIMS and so on). Make the layer scheme a named,
   configurable mapping, keeping the current names available as a legacy
   scheme.
7. PAPER SPACE. Add a LAYOUT with a viewport locked at a real scale, the
   title block as a block with attributes (project, client, date, sheet
   number, revision), and the legal disclaimer text as a fixed attribute.
8. SCHEDULES. Emit the door/window schedule and the room area schedule from
   `LayoutMetrics` as annotation on the sheet. Do not use FIELD entities;
   they do not recalculate outside AutoCAD.

Tests, all round-trip (export, then re-open with ezdxf and assert):
expected block definitions exist; INSERT count equals door and window count;
every wall boundary polyline is closed; layers exist with correct colour and
lineweight; $INSUNITS is set; dimension geometry blocks were generated;
layout and viewport exist. Add a golden-file test that fails if the entity
type census of a fixed reference plan changes.

Do not implement IFC or DWG in this phase.
```

### Phase 5: vastu as an optional soft module

**Status: done (2026-08-13).** `core/vastu.py`, disabled by default via
`GenerationRequest.vastu: VastuOptions` (`enabled`, `weight`,
`plot_north`). Three questions resolved before writing code (this phase
touches scoring, so per CLAUDE.md's rule the design was presented and
confirmed first):

1. **Pooja room type**: added `RoomType.POOJA`, since the spec's "pooja
   northeast" preference needs a real room type to attach to. Turned out
   TNCDBR 2019, Rule 52(5)(b) itself names pooja room as explicitly
   excluded from the habitable-room minimum -- so the uncited-placeholder
   treatment in `core/rules.py` isn't a gap, it's what the code actually
   says.
2. **`plot_north` modeling**: reused the existing `Orientation` enum
   (same as `PlotSpec.entrance`) rather than a numeric degree field --
   vastu's own zones are quadrant-based, not degree-precise, so the extra
   precision wouldn't change any classification. Required (no default)
   whenever `vastu.enabled` -- `core/models.py`'s "x -> east, y -> north"
   convention is a drawing-space assumption, not necessarily a given
   plot's real survey orientation, and this is the one place that
   distinction actually matters.
3. **API/CLI wiring**: threaded through both in this same phase (JSON
   `vastu: {enabled, weight, plot_north}`, CLI `--vastu`/
   `--vastu-weight`/`--plot-north`), matching how every other
   `GenerationRequest` field already reaches both surfaces.

Rooms are classified into 8 compass sectors by bearing from the buildable
rect's center, rotated into a true-north-aligned frame first (see
`vastu.py::true_compass_zone` and `docs/design_rules.md` "Vastu" for the
rotation derivation). Five preferences: kitchen SE, master bedroom SW,
pooja NE, toilet/bathroom avoid NE, entrance faces N/NE/E. Each violated
preference is a fixed, uncited penalty scaled by `weight`, surfaced as
`score_breakdown["vastu"]` (present only when enabled) and
`Layout.vastu_preferences` -- a dedicated list, never merged into the
plain-float `score_breakdown` dict, so a result can never be misread as
code compliance. `tests/test_vastu.py` covers the rotation math for all
four `plot_north` values, preference evaluation, the `VastuOptions`
validation (`plot_north` required when enabled, weight >= 0), and the
phase's own stated requirement: with vastu disabled, `generate()` output
is byte-identical to the Phase 3/4 baseline for the same seed (verified
directly, not just inferred from the rest of the suite still passing).
Cross-process determinism was re-verified with vastu *enabled* too (not
just disabled), since it introduces a new code path inside the annealing
loop. 219 tests passing.

```
Read CLAUDE.md. Implement Phase 5 only.

Add `core/vastu.py` as a self-contained, optional scoring module,
disabled by default and enabled by a flag on GenerationRequest with a
weight parameter.

It scores directional placement preferences (kitchen southeast, master
bedroom southwest, pooja northeast, avoiding toilet in northeast, entrance
orientation) and returns a breakdown naming each satisfied and violated
preference.

Requirements:
- It is SOFT. Nothing in it may reject a layout or enter the validator.
- The score breakdown returned to the user must keep vastu preferences
  visually and structurally separate from code compliance, so a user can
  never confuse "violates NBC" with "violates a vastu preference".
- Plot north orientation must be an explicit input, not assumed.

Tests: with the module disabled, output is byte-identical to Phase 3
(circulation) for the same seed -- Phase 4 only touched DXF export, so
Phase 3's output is the correct baseline to diff against here.
```

---

## 4. Service phases

These are specified in full in `docs/saas-buildout.md`. Run them after the
engine phases, because Phase 3 (circulation) changes what a saved plan
regenerates as, and you do not want that happening to customers' stored
projects.

For each, use this template:

```
Read CLAUDE.md and docs/saas-buildout.md.

Implement Phase <N> only: <goal line from the table below>.

Before writing code:
1. List the files you will create or modify.
2. Show me the schema changes and the migration plan.
3. Flag anything in the spec that is wrong, ambiguous, or that you would do
   differently, and wait for my answer.

Constraints:
- Do not modify src/rivet/core, src/rivet/render, or src/rivet/export.
- Tests for everything new, in the same commit.
- pytest green before you tell me you are done.
- Do not start the next phase.
```

| Phase | Goal line |
|---|---|
| 6 | FastAPI skeleton, config, Postgres and Alembic, docker-compose with all services, healthz and readyz, existing generate endpoint ported to /api/v1 unauthenticated, CI extended and green. Nothing else. |
| 7 | Auth: users, organizations, memberships, sessions, email verification, password reset, API keys, /me, and the single current_context dependency. |
| 8 | Persistence and jobs: projects, generations, candidates, artifacts; RQ queue and worker; storage adapter with local and S3 implementations; async generate flow with polling and the entitlement-checked download endpoint. |
| 9 | Entitlements and quota: plans table, entitlements_for, usage_events, enforcement at validation, enqueue and download; watermarking passed in as a render parameter. |
| 10 | Billing: checkout session, customer portal, webhook handler with signature verification and billing_events idempotency, subscription state machine, past_due degradation to free limits. |
| 11 | Hardening: rate limits, CORS, CSRF, Sentry, structured JSON logging with request ids, absolute input clamps, ToS acceptance with version and timestamp, real account deletion including object storage. |
| 12 | Deploy: production Dockerfile, migrations as a release step, staging environment, smoke test script, runbook in docs/. |

### Phase 6 status

**Status: done (2026-08-13).** Four decisions confirmed before writing
code (per the template above):

1. **Flask stays running as-is.** `src/rivet/api/` (Flask) and `web/` are
   untouched; the new FastAPI service grows alongside it phase by phase
   and Flask gets removed once FastAPI reaches parity (room-types, rules,
   download -- expected around Phase 8-9), not this phase. Avoids a flag
   day that breaks the working demo mid-buildout.
2. **Sync SQLAlchemy + psycopg**, not async -- one session style shared
   identically by the API and the Phase 8 RQ workers (RQ is inherently
   sync), rather than maintaining both an async ORM path and a separate
   sync one for the worker anyway.
3. **Empty migration for Phase 6.** The full section 4 data model is
   *not* created yet -- nothing in this phase reads or writes a table.
   The first migration (`72f6e03cec88`) is a genuine no-op, proving the
   Alembic harness works end to end and giving Phase 7 a real
   `down_revision` to chain onto. Each later phase adds its own tables in
   its own migration, when its own code first needs them.
4. **New dependencies approved**: `fastapi`, `uvicorn[standard]`,
   `sqlalchemy>=2`, `alembic`, `pydantic-settings`, `psycopg[binary]` --
   all in a new `service` extra (`pip install -e ".[service]"`), not the
   base install, so the engine/CLI stays lightweight. `httpx2` was also
   added (dev-only) after `httpx` printed a hard deprecation warning
   against the installed `starlette`/FastAPI versions -- newer than
   expected, not pinned before now.

Shipped: `src/rivet_service/` (`main.py` app factory, `config.py`
pydantic-settings, `db/` sync engine+session+Alembic harness, `api/`
with a consistent error envelope and one ported endpoint,
`POST /api/v1/generate` -- same behavior as the Flask version, just
FastAPI/Pydantic-validated, no persistence or auth yet). `/healthz`
(liveness only) and `/readyz` (pings Postgres, returns 503 when
unreachable). `docker-compose.yml` stands up all 5 services from section
10 (api, worker, postgres, redis, minio) even though jobs/storage don't
exist until Phase 8 -- the worker container runs an explicit placeholder
rather than pretending to process jobs. CI gained a second job
(`service-test`): a single-Python-version run (3.12, not the full engine
matrix -- FastAPI/SQLAlchemy compatibility across 3.10-3.12 isn't what
that job is for) with a real `postgres:16` service container, running
migrations, the new `tests/service/` suite, and a Docker image build.

`tests/service/` skips cleanly (not fails) when no `DATABASE_URL` is
reachable, so a contributor running the plain engine suite locally with
no Postgres running still sees a fully green `pytest -q` -- verified
directly, including with Postgres stopped entirely.

Not verified: `docker compose up` end to end -- Docker isn't available
in the environment this phase was built in. The Dockerfile and compose
file were reviewed carefully and CI now builds the image, but nobody has
actually run the full local compose stack yet.

### Phase 7 status

**Status: done (2026-08-13).** Four decisions confirmed before writing
code (per CLAUDE.md's rule for anything touching auth, and the phase
template):

1. **A `sessions` table, even though section 4 doesn't list one.**
   Section 5 requires a real session token, and `POST /auth/logout` (a
   named endpoint) needs something to revoke -- a stateless signed
   cookie can't be truly invalidated before its own expiry without
   reinventing this table as a blocklist anyway. `sessions.token_hash`
   stores a hash of a random opaque token (`secrets.token_urlsafe`), not
   a signed value -- the DB row is the source of truth, the same pattern
   `api_keys.key_hash` already used.
2. **Hand-rolled HMAC for email-verification/password-reset tokens**
   (`auth/tokens.py`), not a new `itsdangerous` dependency -- a small,
   well-understood ~70-line pattern (base64url payload + HMAC-SHA256
   signature + expiry), reusing the same `secret_key` sessions don't need.
3. **No email provider wired up.** `/auth/verify-email` and
   `/auth/request-password-reset` generate real tokens and log the
   value server-side (never in the HTTP response body -- a worse leak
   surface than a real email would be); nothing sends an actual email.
   Picking a provider (SES, SendGrid, ...) is a distinct decision
   deferred to whenever that's actually wanted.
4. **`argon2-cffi` approved** (section 11 names Argon2id explicitly;
   there's no stdlib alternative). Added to the `service` extra.

Shipped: `db/models/` (User, Organization, Membership, ApiKey, Session)
and their migration (`e977392f7403`, chained onto Phase 6's empty one;
creates the `citext` extension for case-insensitive email); `auth/`
(`passwords.py` argon2id, `tokens.py` signed tokens, `sessions.py`,
`api_keys.py`, `dependencies.py`); and the routes from section 9's API
surface table: `/auth/register|login|logout|verify-email|
request-password-reset|reset-password`, `/me`, `/api-keys` (list/create/
revoke).

`current_context`/`require_context` (`auth/dependencies.py`) is the one
shared resolution point every protected route depends on, exactly as
section 5 asks -- session cookie or `Authorization: Bearer rvt_live_...`,
resolved identically. It returns `(user, org, role, auth_method)` rather
than the spec's literal `(user, org, entitlements)`, since Entitlements
doesn't exist until Phase 9; that phase adds a field here, not a
call-site rewrite at every route. API-key auth resolves an `org` with no
`user` (keys are org-scoped, not user-scoped) -- creating a *new* key
still requires session auth specifically, since `api_keys.created_by` is
a real user reference an API key doesn't have. Every user starts solo
per section 4; there's no org-switching/invite flow anywhere in the
7-phase plan, so `current_context` resolves a user's first membership as
their org context. Password reset revokes every existing session for
that user, not just the one that requested it. Login and registration
return the identical generic message for "no such user" and "wrong
password" (section 5), and `/auth/request-password-reset` always returns
200 regardless of whether the account exists -- neither is an
enumeration oracle.

Not implemented (explicitly out of scope per the phase table, not
overlooked): rate limiting on login/register/reset (Phase 11), CSRF
protection on cookie-authenticated routes (Phase 11), API key paid-tier
gating (Phase 9, no entitlements yet).

`tests/service/conftest.py` gained a `_clean_auth_tables` autouse
fixture -- Phase 7's tests commit real rows to the shared dev/CI
Postgres (no per-test transaction rollback, since routes commit their
own sessions), so tables are wiped before every test rather than relying
on unique-per-test data. 249 tests passing (219 engine + 30 service).

---

## 5. Things to decide before you start

Claude Code will ask about these. Have answers ready, because guessing wrong
costs a rewrite.

1. **Billing entity and currency.** Indian entity pricing in INR means
   Razorpay Subscriptions and the RBI e-mandate flow. International in USD
   means Stripe Checkout. This changes the integration shape, not just the
   keys.
2. **Deploy target.** Railway or Fly for speed, AWS ECS plus RDS plus
   ElastiCache to use your SAA knowledge. Not a single VM running Postgres
   next to the app.
3. **Jurisdiction for the rulebook.** TNCDBR 2019 plus NBC 2016 as the
   fallback is the sensible default given where you are, but the ruleset
   must be swappable from day one or you cannot sell outside Tamil Nadu.
4. **Where the code numbers come from.** You need the actual NBC 2016 Part 3
   and TNCDBR 2019 documents open while running Phases 1 and 2. Do not let
   Claude Code source clause values from search results.

### Decided (2026-08-12)

1. **Billing: international, USD.** Stripe Checkout + Customer Portal.
2. **Deploy: AWS.** ECS Fargate + RDS + ElastiCache.
3. **Jurisdiction: TNCDBR 2019 primary, NBC 2016 Part 3 fallback**, as a
   named swappable ruleset (`TNCDBR_2019`, `GENERIC`) per Phase 1 point 5.

**Setback table and room minimums: sourced.** Extracted directly from the
official TNCDBR 2019 base text (Rule 35 for setbacks, Rule 52 for room
minimums) and written up with exact citations in
[`docs/regulatory_sources.md`](regulatory_sources.md) — read that before
starting Phase 1, it has the values ready to transcribe into
`core/rules.py`.

Still outstanding, per that document's "Gaps" section: door widths (not in
TNCDBR's general residential rules — need an NBC 2016 citation or a
deliberate practice value), the NBC 2016 Part 3 extract for the `GENERIC`
fallback ruleset, and a check of whether any of TNCDBR's 14 amendment
G.O.s (most recent Oct 2025) touch Rule 35 or Rule 52 — the sourced values
are from the unamended 2019 base text only.

## 6. Not in scope for these phases

Deliberately deferred, so Claude Code does not scope-creep into them:

- IFC export (IfcOpenShell). Real differentiator, much larger job, later
  premium tier.
- DWG output via ODA File Converter. Check its licence before commercial use.
- Multi-storey stacking. Depends on Phase 3 (circulation) landing first,
  since staircases are circulation.
- Natural language brief parsing via an LLM. Low risk, high polish, but it
  is a service-layer feature and belongs after Phase 8.
- Learning the scoring weights from architect preference data. Needs data
  you do not have yet.
