"""Rivet's service layer: auth, persistence, billing, and the FastAPI
surface that wraps the pure ``rivet`` engine.

Hard boundary (CLAUDE.md): this package may import from ``rivet.core``,
``rivet.render``, and ``rivet.export`` (calling the engine is the whole
point), but nothing in those three ever imports back from here, touches a
database, reads an environment variable, or knows that users/orgs/plans
exist. If a feature seems to need that, the fix is a parameter on
``GenerationRequest`` or a check here before calling the engine -- never
a change to the engine itself.
"""
