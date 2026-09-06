"""Pytest configuration: project root on sys.path + shared fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SAMPLE_XBRL = PROJECT_ROOT / "data" / "sample_xbrl" / "huaxia_q2_2026.xbrl"


@pytest.fixture()
def sample_xbrl() -> Path:
    assert SAMPLE_XBRL.exists(), f"sample file missing: {SAMPLE_XBRL}"
    return SAMPLE_XBRL


@pytest.fixture()
def portal(tmp_path, monkeypatch):
    """Flask test client with OUTPUT_ROOT / UPLOAD_ROOT redirected to a temp dir."""
    import web_portal

    out_root = tmp_path / "web_runs"
    up_root = tmp_path / "web_uploads"
    monkeypatch.setattr(web_portal, "OUTPUT_ROOT", out_root)
    monkeypatch.setattr(web_portal, "UPLOAD_ROOT", up_root)
    app = web_portal.create_app()
    return app.test_client(), out_root
