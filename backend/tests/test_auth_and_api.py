from datetime import timedelta

from app.core.database import SessionLocal, utcnow
from app.services import seed


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_register_validation_and_login(client, viewer_h):
    r = client.post("/api/auth/register", json={"email": "bad", "username": "x", "password": "short"})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={"email": "viewer@test.dev", "username": "Dup", "password": "Viewer1234"})
    assert r.status_code == 409
    r = client.post("/api/auth/login", json={"email": "viewer@test.dev", "password": "wrong"})
    assert r.status_code == 401
    me = client.get("/api/auth/me", headers=viewer_h).json()
    assert me["email"] == "viewer@test.dev" and me["role"] == "viewer"
    assert "hashed_password" not in me


def test_auth_required_and_rbac(client, viewer_h, operator_h, admin_h):
    assert client.get("/api/cameras").status_code == 401
    assert client.get("/api/cameras", headers={"Authorization": "Bearer garbage"}).status_code == 401
    payload = {"name": "RBAC cam", "source_type": "none"}
    assert client.post("/api/cameras", json=payload, headers=viewer_h).status_code == 403
    assert client.post("/api/cameras", json=payload, headers=operator_h).status_code == 403
    assert client.get("/api/logs/activity", headers=operator_h).status_code == 403
    assert client.put("/api/settings", json={}, headers=operator_h).status_code == 403
    assert client.post("/api/cameras", json=payload, headers=admin_h).status_code == 201


def test_camera_crud_and_validation(client, admin_h):
    bad = client.post("/api/cameras", json={"name": "Bad", "source_type": "stream", "source": "ftp://x"}, headers=admin_h)
    assert bad.status_code == 422
    bad = client.post("/api/cameras", json={"name": "Bad2", "source_type": "file", "source": "../../etc/passwd.mp4"}, headers=admin_h)
    assert bad.status_code == 422
    bad = client.post("/api/cameras", json={"name": "Bad3", "latitude": 123}, headers=admin_h)
    assert bad.status_code == 422
    cfg = {"counting_lines": [{"id": "a", "name": "A", "p1": [0.1, 0.5], "p2": [0.9, 0.5]}], "zones": []}
    r = client.post("/api/cameras", json={"name": "Gate 1", "location": "Test", "latitude": 28.6, "longitude": 77.2,
                                         "source_type": "webcam", "source": "0", "config": cfg}, headers=admin_h)
    assert r.status_code == 201
    cid = r.json()["id"]
    assert client.post("/api/cameras", json={"name": "Gate 1"}, headers=admin_h).status_code == 409
    r = client.put(f"/api/cameras/{cid}", json={"name": "Gate 1b", "source_type": "none", "config": {"counting_lines": [{"id": "x", "name": "x", "p1": [2, 0], "p2": [0, 0]}]}}, headers=admin_h)
    assert r.status_code == 422  # coordinates must be normalised
    r = client.put(f"/api/cameras/{cid}", json={"name": "Gate 1b", "source_type": "none"}, headers=admin_h)
    assert r.status_code == 200 and r.json()["name"] == "Gate 1b"
    assert client.delete(f"/api/cameras/{cid}", headers=admin_h).status_code == 204
    assert client.delete(f"/api/cameras/{cid}", headers=admin_h).status_code == 404


def test_monitoring_start_errors(client, admin_h, operator_h):
    cam = client.post("/api/cameras", json={"name": "No source", "source_type": "none"}, headers=admin_h).json()
    r = client.post("/api/monitoring/start", json={"camera_id": cam["id"]}, headers=operator_h)
    assert r.status_code == 400 and "no video source" in r.json()["detail"]
    assert client.post("/api/monitoring/start", json={"camera_id": 99999}, headers=operator_h).status_code == 404


def test_settings_roundtrip_and_validation(client, admin_h, viewer_h):
    s = client.get("/api/settings", headers=viewer_h).json()
    assert s["confidence"] == 0.35 and s["demo_mode"] is True
    s["confidence"] = 0.5
    s["demo_mode"] = False
    assert client.put("/api/settings", json=s, headers=admin_h).status_code == 200
    assert client.get("/api/settings", headers=viewer_h).json()["confidence"] == 0.5
    assert client.put("/api/settings", json={**s, "confidence": 3}, headers=admin_h).status_code == 422
    assert client.put("/api/settings", json={**s, "classes": []}, headers=admin_h).status_code == 422
    assert client.put("/api/settings", json={**s, "density_thresholds": [0.8, 0.5, 0.2]}, headers=admin_h).status_code == 422
    s["demo_mode"] = True
    s["confidence"] = 0.35
    client.put("/api/settings", json=s, headers=admin_h)


def test_demo_data_is_labelled_and_hideable(client, admin_h, viewer_h):
    with SessionLocal() as db:
        seed.seed_demo(db, days=3)
    st = client.get("/api/dashboard/stats?range=24h", headers=viewer_h).json()
    assert st["demo_rows"] is True and st["total_vehicles"] > 0 and st["total_cameras"] >= 5
    trends = client.get("/api/dashboard/traffic-trends?range=24h", headers=viewer_h).json()
    assert trends and {"t", "total", "car"} <= set(trends[0])
    dist = client.get("/api/dashboard/vehicle-distribution?range=7d", headers=viewer_h).json()
    assert {d["name"] for d in dist} == {"car", "motorcycle", "bus", "truck", "bicycle"}
    peak = client.get("/api/analytics/peak-hours?range=7d&tz=330", headers=viewer_h).json()
    assert len(peak["hourly"]) == 24 and peak["peaks"]
    dens = client.get("/api/analytics/density?range=24h", headers=viewer_h).json()
    assert dens["series"] and dens["series"][0]["level"] in ("Low", "Moderate", "High", "Critical")
    v = client.get("/api/violations?page_size=5", headers=viewer_h).json()
    assert v["total"] > 0 and all(i["is_demo"] for i in v["items"])
    first = v["items"][0]
    assert client.get(f"/api/violations/{first['id']}", headers=viewer_h).status_code == 200
    ev = client.get(f"/api/violations/{first['id']}/evidence", headers=viewer_h)
    assert ev.status_code == 200 and ev.headers["content-type"] == "image/jpeg"
    # filters + search
    only = client.get("/api/violations?category=overspeed", headers=viewer_h).json()
    assert only["total"] > 0 and all(i["category"] == "overspeed" for i in only["items"])
    assert client.get("/api/violations?search=zzzz", headers=viewer_h).json()["total"] == 0
    # reports
    csv_r = client.get("/api/reports/csv?type=violations", headers=viewer_h)
    assert csv_r.status_code == 200 and csv_r.text.startswith("id,timestamp_utc") and "DEMO (simulated)" in csv_r.text
    pdf = client.get("/api/reports/pdf?period=weekly", headers=viewer_h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    summ = client.get("/api/reports/summary", headers=viewer_h).json()
    assert summ["total_vehicles"] > 0
    # notifications panel
    n = client.get("/api/notifications", headers=viewer_h).json()
    assert n["items"] and n["unread"] > 0
    assert client.post("/api/notifications/read-all", headers=viewer_h).status_code == 200
    assert client.get("/api/notifications", headers=viewer_h).json()["unread"] == 0
    # turn demo mode off -> simulated rows disappear everywhere
    s = client.get("/api/settings", headers=viewer_h).json()
    client.put("/api/settings", json={**s, "demo_mode": False}, headers=admin_h)
    st = client.get("/api/dashboard/stats?range=24h", headers=viewer_h).json()
    assert st["total_vehicles"] == 0 and st["has_data"] is False
    assert client.get("/api/violations", headers=viewer_h).json()["total"] == 0
    client.put("/api/settings", json={**s, "demo_mode": True}, headers=admin_h)


def test_activity_log_and_system_health(client, admin_h, viewer_h):
    logs = client.get("/api/logs/activity", headers=admin_h).json()
    assert any(l["action"] == "camera_create" for l in logs)
    h = client.get("/api/system/health", headers=viewer_h).json()
    assert h["database"]["ok"] and "model" in h and "disk" in h
    users = client.get("/api/users", headers=admin_h).json()
    uid = next(u["id"] for u in users if u["email"] == "viewer@test.dev")
    assert client.put(f"/api/users/{uid}/role", json={"role": "operator"}, headers=admin_h).json()["role"] == "operator"
    client.put(f"/api/users/{uid}/role", json={"role": "viewer"}, headers=admin_h)
