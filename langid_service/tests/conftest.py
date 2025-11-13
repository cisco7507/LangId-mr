# langid_service/tests/conftest.py
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from langid_service.app import metrics as m

# IMPORTANT: set mock before importing app so workers inherit it
os.environ["USE_MOCK_DETECTOR"] = "1"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

@pytest.fixture(autouse=True)
def fresh_metrics_registry(monkeypatch):
    # Give each test a clean, isolated registry
    reg = CollectorRegistry(auto_describe=True)
    m._swap_registry_for_tests(reg)
    yield reg

@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
