"""Flask-приложение: UI и REST API извлечения."""

from __future__ import annotations

import hmac
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import torch
from flask import Flask, jsonify, render_template, request

from app.config import AppConfig
from app.extraction import ExtractorPool, resolve_device, run_extraction
from app.html_loader import load_html

_PKG_DIR = Path(__file__).resolve().parent.parent

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()

_DEVICES = {"auto", "cpu", "cuda"}
_FORMATS = {"markdown", "html"}
_MAX_TOKENS_LIMIT = 32768
_JOB_TTL_SECONDS = 3600


def _purge_jobs_locked() -> None:
    now = time.time()
    stale = [
        job_id
        for job_id, job in _jobs.items()
        if job["status"] != "running"
        and now - float(job.get("finished_at", now)) > _JOB_TTL_SECONDS
    ]
    for job_id in stale:
        del _jobs[job_id]


def _purge_jobs() -> None:
    with _jobs_lock:
        _purge_jobs_locked()


def _run_job(
    html: str,
    extractor: Any,
    stop_event: threading.Event,
    job: dict[str, Any],
    max_tokens: int,
    as_html: bool,
) -> None:
    run_extraction(html, extractor, stop_event, job, max_tokens, as_html)
    if job["status"] != "running":
        job["finished_at"] = time.time()


def _error(message: str, status: int, error_type: str):
    return jsonify({"error": {"message": message, "type": error_type}}), status


def _authorized(expected: str) -> bool:
    if not expected:
        return True
    header = request.headers.get("Authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token or len(token) != len(expected):
        return False
    return hmac.compare_digest(token, expected)


def _public_job(job_id: str, job: dict[str, Any]) -> dict[str, Any]:
    status = job["status"]
    if status == "done":
        status = "cancelled" if job.get("aborted") else "completed"
    elif status == "error":
        status = "failed"
    progress = job.get("progress") or [0, 0]
    body: dict[str, Any] = {
        "id": job_id,
        "object": "extraction",
        "status": status,
        "progress": {"processed": progress[0], "total": progress[1]},
    }
    if status in ("completed", "cancelled"):
        body.update(
            output=job.get("output", ""),
            format=job.get("format", "markdown"),
            kept=job.get("kept", 0),
            dropped=job.get("dropped", 0),
            device=job.get("device"),
            proc_ms=job.get("proc_ms", 0),
        )
    elif status == "failed":
        body["error"] = {
            "message": job.get("error") or "unknown",
            "type": "server_error",
        }
    return body


def create_app(config: AppConfig, pool: ExtractorPool | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_PKG_DIR / "templates"),
        static_folder=str(_PKG_DIR / "static"),
        static_url_path="/static",
    )
    if pool is None:
        pool = ExtractorPool(model_path=str(config.model.path))

    @app.before_request
    def require_api_key():
        if not request.path.startswith("/v1/") or request.path == "/v1/health":
            return None
        if _authorized(config.api.key):
            return None
        return _error("Нужен API-ключ: Authorization: Bearer <key>", 401, "authentication_error")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/v1/health")
    def health():
        _purge_jobs()
        with _jobs_lock:
            running = sum(1 for j in _jobs.values() if j["status"] == "running")
        info: dict[str, Any] = {
            "status": "ok",
            "auth_required": bool(config.api.key),
            "model_path": str(config.model.path),
            "model_exists": config.model.path.is_dir(),
            "extractor_loaded": pool.loaded,
            "running_jobs": running,
        }
        if pool.loaded and pool.device:
            info["device"] = pool.device
            if pool.device == "cuda":
                try:
                    info["alloc_mb"] = round(torch.cuda.memory_allocated(0) / 1024**2, 1)
                    info["reserved_mb"] = round(torch.cuda.memory_reserved(0) / 1024**2, 1)
                except Exception:
                    pass
        return jsonify(info)

    @app.route("/v1/extractions", methods=["POST"])
    def create_extraction():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _error("Ожидается JSON-объект", 400, "invalid_request_error")

        html_value = data.get("html")
        url_value = data.get("url")
        has_html = isinstance(html_value, str) and bool(html_value.strip())
        has_url = isinstance(url_value, str) and bool(url_value.strip())
        if has_html == has_url:
            return _error("Укажите ровно одно из полей: html или url", 400, "invalid_request_error")

        device_name = data.get("device", config.extraction.default_device)
        if device_name not in _DEVICES:
            return _error("device: auto, cpu или cuda", 400, "invalid_request_error")

        output_format = data.get("format", "markdown")
        if output_format not in _FORMATS:
            return _error("format: markdown или html", 400, "invalid_request_error")

        max_tokens = data.get("max_tokens", config.extraction.default_max_tokens)
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
            return _error("max_tokens: целое число", 400, "invalid_request_error")
        if not 1 <= max_tokens <= _MAX_TOKENS_LIMIT:
            return _error(
                f"max_tokens: от 1 до {_MAX_TOKENS_LIMIT}",
                400,
                "invalid_request_error",
            )

        source = url_value if has_url else html_value
        source_type = "url" if has_url else "string"
        try:
            html = load_html(source, source_type, config.http.ssl_verify)
        except Exception as e:
            return _error(f"Не удалось загрузить источник: {e}", 400, "invalid_request_error")

        if len(html.encode("utf-8")) > config.extraction.max_input_bytes:
            return _error("HTML больше max_input_bytes", 413, "invalid_request_error")

        try:
            extractor = pool.get(resolve_device(device_name))
        except Exception as e:
            return _error(f"Не удалось загрузить модель: {e}", 500, "server_error")

        job_id = "ext_" + uuid.uuid4().hex
        job: dict[str, Any] = {
            "status": "running",
            "output": "",
            "html": "",
            "kept": 0,
            "dropped": 0,
            "proc_ms": 0,
            "progress": [0, 0],
            "aborted": False,
            "error": None,
            "format": output_format,
        }
        stop_event = threading.Event()
        job["stop_event"] = stop_event
        with _jobs_lock:
            _purge_jobs_locked()
            _jobs[job_id] = job
        threading.Thread(
            target=_run_job,
            args=(html, extractor, stop_event, job, max_tokens, output_format == "html"),
            daemon=True,
        ).start()
        return jsonify(_public_job(job_id, job)), 202

    @app.route("/v1/extractions/<job_id>")
    def get_extraction(job_id: str):
        _purge_jobs()
        with _jobs_lock:
            job = _jobs.get(job_id)
        if not job:
            return _error("Задача не найдена", 404, "not_found")
        return jsonify(_public_job(job_id, job))

    @app.route("/v1/extractions/<job_id>/cancel", methods=["POST"])
    def cancel_extraction(job_id: str):
        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return _error("Задача не найдена", 404, "not_found")
            stop_event = job.get("stop_event")
            cancelled = False
            if stop_event and job["status"] == "running":
                stop_event.set()
                cancelled = True
            body = _public_job(job_id, job)
        if cancelled:
            body["cancel_requested"] = True
        return jsonify(body)

    return app
