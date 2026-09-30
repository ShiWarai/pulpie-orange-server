import time
from dataclasses import replace

from app.config import ApiConfig, load_config
from app.web import server as server_mod
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


def test_cancel_completed_job_has_no_cancel_requested():
    client = _client()
    with server_mod._jobs_lock:
        server_mod._jobs["ext_done"] = {
            "status": "done",
            "output": "ok",
            "format": "markdown",
            "kept": 1,
            "dropped": 0,
            "device": "cpu",
            "proc_ms": 1,
            "progress": [1, 1],
            "aborted": False,
            "finished_at": time.time(),
        }
    try:
        resp = client.post("/v1/extractions/ext_done/cancel")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "completed"
        assert "cancel_requested" not in body
    finally:
        with server_mod._jobs_lock:
            server_mod._jobs.pop("ext_done", None)


def test_stale_finished_jobs_are_purged():
    client = _client()
    with server_mod._jobs_lock:
        server_mod._jobs["ext_old"] = {
            "status": "done",
            "output": "x",
            "finished_at": time.time() - server_mod._JOB_TTL_SECONDS * 2,
        }
    try:
        assert client.get("/v1/health").status_code == 200
        with server_mod._jobs_lock:
            assert "ext_old" not in server_mod._jobs
    finally:
        with server_mod._jobs_lock:
            server_mod._jobs.pop("ext_old", None)


def test_running_job_is_not_purged():
    client = _client()
    with server_mod._jobs_lock:
        server_mod._jobs["ext_running"] = {"status": "running"}
    try:
        assert client.get("/v1/health").status_code == 200
        with server_mod._jobs_lock:
            assert "ext_running" in server_mod._jobs
    finally:
        with server_mod._jobs_lock:
            server_mod._jobs.pop("ext_running", None)
