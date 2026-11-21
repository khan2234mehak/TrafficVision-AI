import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="tv_tests_"))
os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    "DATA_DIR": str(_TMP / "data"),
    "SAMPLE_DIR": str(_TMP / "sample"),
    "MODEL_DIR": str(_TMP / "models"),
    "SECRET_KEY": "test-secret-key-test-secret-key-1234",
    "SEED_DEMO_DATA": "false",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.cv.detector import set_detector  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import ScriptedDetector  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _detector():
    set_detector(ScriptedDetector([]))
    yield
    set_detector(None)


def _login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_h(client):
    return _login(client, settings.demo_admin_email, settings.demo_admin_password)


@pytest.fixture(scope="session")
def operator_h(client):
    return _login(client, settings.demo_operator_email, settings.demo_operator_password)


@pytest.fixture(scope="session")
def viewer_h(client):
    r = client.post("/api/auth/register", json={"email": "viewer@test.dev", "username": "Viewer", "password": "Viewer1234"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
