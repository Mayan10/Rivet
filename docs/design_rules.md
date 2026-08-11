# Design rules

This is the human-readable version of [`src/rivet/core/rules.py`](../src/rivet/core/rules.py),
which is the single source of truth — if this document and the code
disagree, the code is right and this file needs an update.

These are commonly-referenced residential space-planning defaults (values
found, in the same neighborhood, across national building codes and
standard architectural handbooks for single-family homes). Rivet uses them
as scoring targets for an automated design *assistant*. They are **not** a
substitute for a licensed engineer's stamped drawings or your local
building code, which always takes precedence.

## Per-room space standards

| Room | Min area (m²) | Default area (m²) | Min width (m) | Max aspect ratio | Needs exterior wall |
|---|---|---|---|---|---|
| Living room | 11.0 | 18.0 | 2.7 | 2.2 | yes |
| Master bedroom | 11.0 | 14.0 | 2.7 | 2.0 | yes |
| Bedroom | 9.5 | 11.0 | 2.4 | 2.0 | yes |
| Kitchen | 5.0 | 8.0 | 1.8 | 2.4 | yes |
| Dining room | 7.5 | 10.0 | 2.4 | 2.0 | no |
| Bathroom | 2.2 | 3.5 | 1.2 | 2.2 | no |
| Toilet | 1.5 | 1.8 | 0.9 | 2.2 | no |
| Study | 6.5 | 9.0 | 2.1 | 2.0 | yes |
| Garage | 15.0 | 18.0 | 2.7 | 2.2 | no |
| Store | 2.0 | 3.0 | 1.2 | 2.2 | no |
| Foyer | 2.5 | 4.0 | 1.2 | 2.5 | no |
| Corridor | 1.5 | 2.5 | 1.0 | 6.0 | no |
| Staircase | 4.0 | 5.0 | 1.0 | 3.0 | no |
| Utility | 2.5 | 3.5 | 1.2 | 2.4 | no |
| Balcony | 2.0 | 3.5 | 1.0 | 3.0 | yes |

"Max aspect ratio" caps how long-and-thin a room is allowed to get relative
to its shorter side before the scorer penalizes it — a comfort constraint,
not a code requirement.

## Construction standards

- External wall thickness: **0.23 m** (~9", typical masonry perimeter wall)
- Internal wall thickness: **0.115 m** (~4.5", half-brick partition)
- Door widths: main entrance **1.00 m**, internal **0.90 m**, bathroom **0.75 m**
- Window widths: habitable rooms **1.20 m**, kitchen **0.90 m**
- Minimum corridor/passage width: **1.00 m**
- Openings are kept at least **0.30 m** clear of a wall's corner

## Setbacks

A simplified tiered rule as a function of plot area — real setback
requirements are jurisdiction-specific; treat these as reasonable
placeholders, not a permit-ready value:

| Plot area | Front | Rear | Side |
|---|---|---|---|
| ≤ 150 m² | 1.5 m | 1.0 m | 0.9 m |
| ≤ 300 m² | 3.0 m | 2.0 m | 1.5 m |
| ≤ 500 m² | 4.5 m | 3.0 m | 2.0 m |
| > 500 m² | 6.0 m | 4.0 m | 3.0 m |

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

**Avoided** (hard — penalized even if it happens by chance, not just when requested):

- Bathroom/toilet ↔ Kitchen
- Bathroom/toilet ↔ Dining room

## Entrance placement

The plot-boundary wall the entrance orientation points at should open into
a foyer, living room, corridor, or garage — not directly into a bedroom or
bathroom.
