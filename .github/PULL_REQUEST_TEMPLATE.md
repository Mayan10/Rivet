## Summary

<!-- What does this change, and why? -->

## Testing

<!-- `pytest -q` and `ruff check packages apps tests` output, plus anything
     specific to this change (e.g. a `rivet generate` command you ran
     to sanity-check a layout-engine change). -->

- [ ] `pytest -q` passes
- [ ] `ruff check packages apps tests` passes
- [ ] If this touches `core/layout_engine.py` or `core/scoring.py`, ran the
      suite against a few different seeds locally, not just once
- [ ] If this touches `export/dxf.py`, confirmed `ezdxf.readfile(...).audit()`
      still reports 0 errors on the output

## Notes for reviewers

<!-- Anything non-obvious: tradeoffs, follow-ups intentionally left out, etc. -->
