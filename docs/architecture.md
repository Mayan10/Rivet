# Architecture

## Request flow

```mermaid
flowchart TD
    A["GenerationRequest\n(plot + room program)"] --> C["graph.expand_room_requirements\nRoomRequirement -> RoomNode[]\n(en-suite bathrooms auto-created)"]
    C --> D["graph.build_adjacency_graph\nweighted graph from rules.ADJACENCY_PREFERRED\n+ required en-suite edges"]
    A --> E["generator.compute_buildable_rect\nplot minus rules.setbacks_for(...)"]
    D --> F
    E --> F["layout_engine.search_layouts\nmulti-start simulated annealing\nover room orderings,\nover-generates a candidate pool"]
    F --> G["layout_engine.build_circulation_layout\ncirculation-aware guillotine subdivision\n(auto-inserted corridor tree,\ndeterministic given an order)"]
    G --> H["scoring.evaluate\npenalty: area error, min-width,\naspect ratio, adjacency, exterior\naccess, entrance placement, circulation %"]
    H -->|"best-of per restart,\ntop N distinct kept"| F
    F --> I["openings.place_openings\ndoors on room/corridor shared walls,\nmain door, windows"]
    I --> N["validator.validate_layout\nhard: min area/width, exterior access,\nhard-avoided adjacency, setbacks,\nreachability from entrance"]
    N -->|"first N valid candidates"| J["Layout[]\n(rooms + openings + score)"]
    N -->|"zero valid out of the pool"| O["InfeasibleResult\n(closest attempt's violations, cited)"]
    J --> K["render/raster.py -> PNG"]
    J --> L["render/svg.py -> SVG"]
    J --> M["export/dxf.py -> DXF"]
```

## Why a slicing tree + simulated annealing

A **guillotine slicing tree** (recursively cut a rectangle in two, recurse
into each half) has one useful property for this problem: *any* ordering of
rooms produces a valid tiling — no overlaps, full coverage of the buildable
rectangle, by construction. That means the search never has to reject or
repair invalid geometry; every candidate the optimizer considers is already
a legal floor plan. It only has to get *better*.

That reduces "design a floor plan" to "find a good permutation of rooms,"
which is a well-trodden problem — slicing-tree optimization via simulated
annealing is a classic technique in floorplanning literature (originally
VLSI chip layout, since applied to architectural space planning). Rivet:

1. Seeds several initial orderings per generation request — sorted by
   target area, a graph-guided traversal that keeps adjacency-linked rooms
   near each other in sequence (living room as hub, then its neighbors,
   etc.), and pure random shuffles for diversity.
2. Runs simulated annealing on each (swap two rooms' positions, or reverse
   a sub-range of the ordering; accept improving moves always, worse moves
   with probability `exp(-Δpenalty / temperature)`, cooling geometrically).
3. Scores every candidate ordering by rebuilding its slice tree and running
   it through `scoring.evaluate` — see [`design_rules.md`](design_rules.md)
   for what's actually being scored.
4. Keeps the best result across all restarts, de-duplicates near-identical
   geometries, and returns the top N distinct candidates.

The split axis at each recursion is always the rectangle's *longer* side,
and the split point is the prefix whose cumulative target area is closest
to half the group's total — both bias the search toward squarer, more
usable rooms without needing to be told to.

## Circulation

A plain slicing tree guarantees a valid *tiling* (no overlaps, full
coverage) but says nothing about whether the result is a *navigable
house* — the Phase 0 audit's most severe finding was that a generated
layout could place a room with no door-reachable route back to the
entrance. `layout_engine.build_circulation_layout` extends the same
permutation-driven recursion with one added rule: a corridor is always
inserted at the root (oriented toward the entrance wall), and again
wherever a sub-cluster still holds more than
`CIRCULATION_SINGLE_LOAD_THRESHOLD` primary rooms — otherwise the cluster
is placed directly, with every split forced to run parallel to the
corridor-facing edge so every resulting room touches it. Because a
subtree's room count can never exceed its parent's, this rule is
monotonic top-down: any corridor inserted below the root implies every
ancestor split up to the root was *also* a corridor split, so the whole
corridor tree is transitively connected back to the entrance by
construction — reachability doesn't depend on the search finding it, only
on this rule always being applied the same way for a given room ordering.
The search itself needed zero new move types to support this: the
corridor tree, like room geometry always was, is a pure function of the
room ordering being annealed over.

Construction alone wasn't the whole story, though — see
[`design_rules.md`](design_rules.md#circulation) for the belt-and-suspenders
validator check this needed anyway, and the real geometry/floating-point
bugs it caught that construction didn't prevent.

## Determinism

`GenerationRequest.seed` is expected to make two calls with identical
inputs produce byte-identical output — including across separate process
invocations, not just within one Python session. That guarantee was broken
once during development by an innocuous-looking `set(...)` in the ordering
search: Python randomizes string-hash seeding per process by default
(`PYTHONHASHSEED`), so a `set`'s iteration order — and therefore which
`rng.random()` draw landed on which room — differed between runs even with
the same explicit seed. Fixed by using an insertion-ordered `dict` instead
(see `core/layout_engine.py::_graph_guided_order`). If you add a new
collection to anything in the search hot path, prefer `list`/`dict` over
`set` unless you're certain nothing downstream depends on iteration order.

## Why no dataset, no ML model

The original prototype (see `CHANGELOG.md`) matched user requirements
against CubiCasa5K floor plan images via nearest-neighbor lookup on room
counts/areas, then traced the closest *existing* image with OpenCV contour
detection. It never designed anything new, and the output quality was
capped by how close the dataset happened to have something similar.

A learned model (e.g. a graph-conditioned GAN, in the spirit of the
House-GAN research this repo used to carry unused template code for) is a
reasonable longer-term direction, but training one needs a labeled dataset,
a training pipeline, and GPU infrastructure that a repository like this
doesn't have out of the box. The constraint-based search here has no such
dependency, runs in well under a second on a laptop CPU, and — because the
rulebook is explicit, readable Python rather than weights in a checkpoint
— every design decision it makes is traceable to a named rule.
