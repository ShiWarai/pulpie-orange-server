from dataclasses import replace

from app.config import ApiConfig, load_config
from app.web.server import create_app


def _client(key: str = ""):
    cfg = replace(load_config(), api=ApiConfig(key=key))
    return create_app(cfg).test_client()


def test_health_stays_open_when_key_is_set():
    client = _client("secret")
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.get_json()["auth_required"] is True


def test_extract_requires_key():
    client = _client("secret")
    resp = client.post("/v1/extractions", json={"html": "<p>x</p>"})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["type"] == "authentication_error"


def test_extract_rejects_bad_key():
    client = _client("secret")
    resp = client.post(
        "/v1/extractions",
        json={"html": "<p>x</p>"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


def test_extract_accepts_bearer_key():
    client = _client("secret")
    resp = client.post(
        "/v1/extractions",
        json={},
        headers={"Authorization": "Bearer secret"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["type"] == "invalid_request_error"


def test_extract_requires_html_or_url():
    resp = _client().post("/v1/extractions", json={})
    assert resp.status_code == 400


def test_extract_rejects_both_sources():
    resp = _client().post(
        "/v1/extractions",
        json={"html": "<p>x</p>", "url": "https://example.com"},
    )
    assert resp.status_code == 400


def test_extract_rejects_bad_device_before_model_load():
    resp = _client().post("/v1/extractions", json={"html": "<p>x</p>", "device": "tpu"})
    assert resp.status_code == 400


def test_unknown_extraction():
    resp = _client().get("/v1/extractions/ext_missing")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["type"] == "not_found"


def test_cancel_unknown_extraction():
    resp = _client().post("/v1/extractions/ext_missing/cancel")
    assert resp.status_code == 404
