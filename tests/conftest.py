"""Shared test fixtures.

The backend tests must never touch the repo's real ``data/atlas.db``: ``DB_PATH``
is bound at import time (``engine/db/models.py`` imports it from ``engine.paths``),
so the only reliable redirect is to set ``ATLAS_DATA_DIR`` *before* those modules
are imported and then reload them. The ``atlas_app`` fixture does exactly that and
hands back a freshly-imported FastAPI ``app`` pointed at a throwaway DB.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def atlas_app(tmp_path, monkeypatch):
    """Point the backend at a throwaway DB, then import the app fresh."""
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ATLAS_PROFILE", raising=False)
    # Reload the import-time-bound modules AFTER the env var is set so DB_PATH /
    # OUTBOX_DIR bind to tmp_path, not the repo's real data dir.
    import engine.db.models
    import engine.paths

    importlib.reload(engine.paths)
    # Force LEGACY mode so an ambient `profiles/registry.json` on the dev's machine can't
    # hijack the test into a real per-profile DB (profile mode ignores ATLAS_DATA_DIR). This
    # keeps `pytest` green whether or not the checkout has been through `atlas profiles init`.
    engine.paths._apply(None)
    importlib.reload(engine.db.models)
    from dashboard.backend import main as backend_main

    importlib.reload(backend_main)
    return backend_main.app
