from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="prize-bond-tests-"))
os.environ["PBS_DB_PATH"] = str(_TMP / "test.db")
os.environ["PBS_EXPORTS_DIR"] = str(_TMP / "exports")
os.environ["PBS_CAPTURES_DIR"] = str(_TMP / "captures")
os.environ["PBS_TARGET"] = "2000"
os.environ["PBS_FRAME_DEDUPE_SECONDS"] = "2.5"
os.environ["PBS_OCR_LANG"] = "ben+eng"

import pytest

from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def tmp_root() -> Path:
    return _TMP


@pytest.fixture(scope="session")
def ocr_available(client) -> bool:
    return bool(client.get("/api/health").json()["ocr"]["available"])
