# Regulatory source material for the rulebook rewrite (Phase 1)

Raw extracted material for `core/rules.py`'s upcoming hard-constraint
rewrite (see `docs/prompts.md` Phase 1, point 5). This is *source
material to build the ruleset from*, not the ruleset itself — values here
still need to be transcribed into `core/rules.py` with the same citation
comments before Phase 1 can use them. Kept separate from
`docs/design_rules.md` (which documents what's actually shipped) so the
two never get confused.

## Source

**Tamil Nadu Combined Development and Building Rules, 2019** (base text,
February 2019 edition), fetched from the official Chennai Corporation
mirror: <https://chennaicorporation.gov.in/images/TNCDRBR-2019.pdf>
(252 pages, text-extractable, retrieved 2026-08-12). Also mirrored by
CMDA at <https://www.cmdachennai.gov.in/TNCDBR2019.html>, which is the
canonical index page and amendment list.

**Not yet checked for conflicts:** CMDA's index page lists 14 amendment
G.O.s to the base 2019 text, most recent 30 Oct 2025:

```
G.O.(Ms).No.171  30.10.2025      G.O.(Ms).No.107  16.07.2025
G.O.(Ms).No.161  15.10.2025      G.O.(Ms).No.225  26.11.2024
G.O.(Ms).No.156  10.10.2025      G.O.(Ms).No.70   11.03.2024
G.O.(Ms).No.155  08.10.2025      G.O.(Ms).No.69   11.03.2024
G.O.(Ms).No.154  07.10.2025      G.O.(Ms).No.58   05.03.2024
                                  G.O.(Ms).No.15   14.01.2024
                                  G.O.(Ms).No.152  18.08.2022
                                  G.O.(Ms).No.51   11.05.2020
                                  G.O.(Ms).No.16   31.01.2020
```

Setback tables are a common amendment target. Before Phase 1 ships,
someone should check whether any of these touch Rule 35 (setbacks) or
Rule 52 (room minimums) — none of that has been done yet, this extract is
from the unamended base text only.

## Setback table — Rule 35 (Planning Parameters for Non High Rise Buildings)

Maps directly onto the `abutting_road_width_m` + `proposed_height_m`
fields Phase 1 adds to `PlotSpec`.

### Rule 35(1)(a): ≤16 dwellings or ≤300m² commercial, height ≤18.30m

Three area classes: Continuous Building Areas (CBA), Economically Weaker
Section (EWS) areas, and Other areas.

| | CBA | EWS | Other |
|---|---|---|---|
| Min road width | 3.0 m | 3.0 m | 3.0–6.0 m, or ≥6.0 m |
| Max height | GF+2F or Stilt+3F, ≤12m | GF+1F or Stilt+2F, ≤9m | GF+2F or Stilt+3F, ≤12m |
| Max dwellings | 16, or 300m² commercial | 16 | 8 (road <6m) / 16 or 300m² (road ≥6m) |
| Max FSI | 2.0 | 2.0 | 2.0 |

Front setback:
- CBA: 1.5m
- EWS: 1.0m
- Other, road ≥6.0m, by **abutting road width**: ≤9.0m → 1.5m; 9.0–18m → 3.0m; 18–30.5m → 4.5m; >30.5m → 6.0m

Side setback (CBA — "Nil" stated, but qualified by building height and plot width elsewhere in the rule; Other areas), by **building height** and **plot width**:
- Height ≤7m: plot width ≤9m → 1.0m one side; plot width >9m → 1.0m both sides
- Height 7–12m: plot width ≤6m → 1.0m one side; 6–9m → 1.5m one side; >9m → 1.5m both sides

Rear setback, by **building height**:
- ≤7m: Nil
- 7–12m: 1.5m

### Rule 35(1)(b): >16 dwellings or >300m² commercial, height ≤18.30m

- Min road width: 9.0m
- Max FSI: 2.0
- Front setback by **abutting road width**: 9–18m → 3.0m; 18–30.5m → 4.5m; >30.5m → 6.0m
- Side/rear setback by **building height**: ≤7m → 1.0m; 7–12m → 1.5m; 12–16m → 2.5m; 16–18.30m → 3.0m

### Passage width (Rule 35(1)(c)) — for sites without direct road frontage

Non High Rise ≤12m height: 1m (CBA/EWS) or 3m (other) for ≤8 dwellings.
Non High Rise 12–18.30m or >16 dwellings, by dwelling/commercial-area
count and passage length: 3.6m / 4.8m / 6m / 7.2m / 9m tiers (see source
for exact breakpoints — Rule 35(1)(c)(B)(i)–(v)).

## Room minimums — Rule 52 ("Requirements of parts of buildings")

| Room | Citation | Min area | Min width | Min height |
|---|---|---|---|---|
| Habitable room (living/bedroom) | Rule 52(5) | 7.5 m² | 2.4 m | 2.75 m (clear head room under beam: 2.4m) |
| Kitchen, with separate dining | Rule 52(6) | 5.0 m² (4.5 m² if separate store also provided) | 1.8 m | 2.75 m |
| Kitchen, doubling as dining | Rule 52(6) | 7.5 m² | 2.1 m | 2.75 m |
| Bathroom | Rule 52(7) | 1.4 m² | 1.0 m | 2.1 m |
| Water closet (WC) | Rule 52(7) | 1.0 m² | 0.9 m | 2.1 m |
| Bath + WC combined | Rule 52(7) | 2.4 m² | 1.2 m | 2.1 m |
| Store room | Rule 52(9) | 3.0 m² | — | 2.2 m |
| Mezzanine (if used as living room) | Rule 52(8) | 9.5 m² | — | 2.2 m |
| Private garage | Rule 52(10) | 3.0m × 6.0m minimum | — | 2.4 m |

Notes worth preserving in code comments:
- Rule 52(5)(b): "Pooja room, or store room shall not be taken as a habitable room" — explicit exclusion, relevant to which `RoomType`s Phase 1's validator should treat as habitable.
- Rule 52(7)(c)(vi): "the door of the water closet or bath not to be directly opened to a kitchen" — this is a real code citation for the `ADJACENCY_AVOID` pair Rivet already has between `BATHROOM`/`TOILET` and `KITCHEN` (currently uncited in `core/rules.py`). Promote this one to hard in the validator, not just a soft scoring penalty, since it's citable.

## Ventilation — Rule 52(16) (relevant to Phase 2's metrics, not just Phase 1)

- Rule 52(16)(a): minimum aggregate opening area (windows/ventilators, excluding doors) ≥ **1/8 of floor area**.
- Increased by **25%** for kitchens (still Rule 52(16)(a) note iii).
- Open-to-sky ventilation alternative: minimum 1.5m × 2.5m (applies to kitchens/store rooms, not bath/WC, which instead need ≥0.5 m² window/ventilator per Rule 52(16)(a) note iv).

## Gaps — not sourced yet

1. **Door widths.** Not specified in TNCDBR's general residential
   provisions. The only door widths found (900mm clear opening) are under
   Rule 43 (differently-abled accessibility), not general dwelling doors.
   Rivet's current placeholders (main 1.0m, internal 0.9m, bath 0.75m) in
   `core/rules.py::DOOR_WIDTH_*` need either an NBC 2016 citation or a
   deliberately-chosen practice value before Phase 1 promotes them to hard
   constraints.
2. **NBC 2016 Part 3** (for the `GENERIC` fallback ruleset) — not yet
   extracted. Located but not pulled:
   - Official: BIS page, <https://bis.gov.in/?page_id=117159&lang=en> (SP 7:2016, paid 2-volume set)
   - Free, appears to be the full text: Internet Archive, Volume 1 (contains Part 3) at <https://archive.org/details/nationalbuilding01>, Volume 2 at <https://archive.org/details/nationalbuilding02>
3. **Amendment cross-check** — see the G.O. list above. Not yet done.
