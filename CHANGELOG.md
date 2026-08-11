# Changelog

All notable changes to this project are documented in this file.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-08-11

### Changed — complete rebuild

Rivet replaces the original DraftEase prototype: a Flask app that matched a
user's room requirements against the CubiCasa5K dataset via nearest-neighbor
lookup, then traced the closest matching *dataset image* into a DXF with
OpenCV contour detection and Tesseract OCR. That approach never designed
anything — it retrieved and traced.

This release is a ground-up procedural generation engine:

### Added

- `core/`: a constraint-based layout engine — room adjacency graph, guillotine
  slicing-tree subdivision, multi-start simulated annealing, and a scored
  design rulebook (minimum room dimensions, wall thickness, door/window
  sizing, setback tiers, adjacency preferences and hard avoidances, exterior
  access requirements).
- `render/`: PNG and SVG renderers that draw a generated layout directly —
  walls, door swing arcs, window breaks, dimensions, north arrow, title
  block. No dataset imagery anywhere in the path.
- `export/dxf.py`: real layered DXF export (`WALLS-EXTERIOR`,
  `WALLS-INTERIOR`, `DOORS`, `WINDOWS`, `TEXT`, `DIMENSIONS`, `ROOMS`,
  `PLOT-BOUNDARY`) with true wall thickness and openings correctly cut out
  of wall geometry, replacing the old raster-contour tracer.
- `cli.py`: scriptable `rivet generate` / `rivet rules` / `rivet room-types`.
- `api/`: a Flask API (`/api/v1/generate`, `/rules`, `/room-types`,
  `/health`, `/download/<token>.dxf`).
- `web/`: a functional generator UI (plot + room program form, ranked
  candidate cards with inline previews and downloads).
- Test suite (`tests/`) covering the rulebook, layout engine invariants,
  scoring behavior, DXF structural validity, and the API.

### Removed

- `floorplan_app/` (the KNN-matching Flask app and OpenCV/Tesseract tracer).
- `src/utils/utils.py` (an unused House-GAN template file — never imported
  by the app; pulled in `torch`/`pygraphviz` for nothing).
- `room_vectors_with_area.json`, `rendered_pngs.zip`, `preprocessing.ipynb`
  (dataset-matching artifacts).
- `torch`, `torchvision`, `pygraphviz`, `pytesseract` dependencies.
