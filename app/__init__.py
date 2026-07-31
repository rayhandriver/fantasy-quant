"""The Fantasy-Quant draft app (Phase 14.1) — a UI over the finished engine.

Deliberately a **top-level package, outside** ``src/fantasy_quant``: the engine is a library that
knows nothing about how it is displayed, and the app is one of two renderers over it (the other is
``steps/mock_draft.py``). Both read :mod:`fantasy_quant.draft.session`, which is where the derived
frames are computed exactly once.

    uv sync --extra ui
    uv run streamlit run app/main.py
"""
