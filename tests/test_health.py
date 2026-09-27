from app.config import load_config
from app.web.server import create_app


def test_health_endpoint(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    app = create_app(load_config())
    client = app.test_client()
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "model_path" in data
    assert data["auth_required"] is False
