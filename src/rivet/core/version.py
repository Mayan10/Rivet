"""Versioning for the two things that change what a stored generation
means, independent of the installed package version (``rivet.__version__``,
which tracks releases of the whole codebase including the API/CLI/web UI).

Both are plain integers, bumped by hand:

- ``RULEBOOK_VERSION``: bump on any change to ``core/rules.py`` (a room
  minimum changes, a ruleset's setback table changes, an adjacency rule
  changes). A persisted generation should store this alongside its request
  and seed, so "why did my plan come out different this time" has a real
  answer instead of a guess.
- ``ENGINE_VERSION``: bump on any change to the generation algorithm itself
  (``core/layout_engine.py``, ``core/scoring.py``, ``core/openings.py``)
  that could change output for a request that previously succeeded.

Version 1 of each is the implicit baseline this project shipped with
before either was tracked. RULEBOOK_VERSION 2 is the Phase 1 rewrite that
introduced cited hard minimums and the TNCDBR_2019/GENERIC ruleset split.

RULEBOOK_VERSION 3 (Phase 8 correction): Phase 3 added the circulation
constants (CIRCULATION_CORRIDOR_WIDTH_M, CIRCULATION_SINGLE_LOAD_THRESHOLD,
MIN_DOOR_CLEAR_WALL_M) and Phase 5 added the POOJA room rule to
core/rules.py -- neither bumped this at the time. Corrected once, here,
rather than carrying the drift into the first phase that actually reads
this value.

ENGINE_VERSION 2 (Phase 8 correction, same reasoning): Phase 3's
circulation-aware rewrite of core/layout_engine.py, core/scoring.py, and
core/openings.py is exactly the kind of change this constant exists to
flag -- every previously-succeeding request now produces categorically
different geometry (an inserted corridor tree). Phase 5's vastu addition
to core/scoring.py did not get its own bump: it's opt-in and byte-identical
when disabled (see tests/test_vastu.py), so it doesn't change output for
a request that previously succeeded.
"""

from __future__ import annotations

RULEBOOK_VERSION = 3
ENGINE_VERSION = 2
