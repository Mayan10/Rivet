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
"""

from __future__ import annotations

RULEBOOK_VERSION = 2
ENGINE_VERSION = 1
