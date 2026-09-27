"""Flask-приложение: UI и REST API извлечения."""

from __future__ import annotations

import threading
import time
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


def create_app(config: AppConfig) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_PKG_DIR / "templates"),
        static_folder=str(_PKG_DIR / "static"),
        static_url_path="/static",
    )
    pool = ExtractorPool(model_path=str(config.model.path))

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/extract", methods=["POST"])
    def extract():
        data = request.get_json(force=True)
        source = data.get("html") or data.get("url")
        device = resolve_device(data.get("device", config.extraction.default_device))
        max_tokens = int(data.get("max_tokens", config.extraction.default_max_tokens))
        as_html = bool(data.get("as_html", False))
        source_type = "url" if data.get("url") else "string"

        if not source:
            return jsonify({"error": "Укажите html или url"}), 400

        try:
            html = load_html(source, source_type, config.http.ssl_verify)
        except Exception as e:
            return jsonify({"error": f"Failed to load source: {e}"}), 400

        if len(html) > config.extraction.max_input_bytes:
            html = html[: config.extraction.max_input_bytes]

        try:
            extractor = pool.get(device)
        except Exception as e:
            return jsonify({"error": f"Не удалось загрузить модель: {e}"}), 500

        job_id = str(int(time.time() * 1000))
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
            "format": "markdown",
        }
        stop_event = threading.Event()
        job["stop_event"] = stop_event
        with _jobs_lock:
            _jobs[job_id] = job
        threading.Thread(
            target=run_extraction,
            args=(html, extractor, stop_event, job, max_tokens, as_html),
            daemon=True,
        ).start()
        return jsonify({"job_id": job_id, "status": "running"}), 202

    @app.route("/api/status/<job_id>")
    def status(job_id: str):
        with _jobs_lock:
            job = _jobs.get(job_id)
        if not job:
            return jsonify({"error": "Unknown job"}), 404
        out: dict[str, Any] = {"status": job["status"], "progress": job["progress"]}
        if job["status"] == "done":
            out.update(
                output=job["output"],
                kept=job["kept"],
                dropped=job["dropped"],
                device=job.get("device"),
                proc_ms=job["proc_ms"],
                aborted=job.get("aborted", False),
                format=job.get("format", "markdown"),
            )
        elif job["status"] == "error":
            out.update(error=job.get("error"), aborted=job.get("aborted", False))
        return jsonify(out)

    @app.route("/api/abort/<job_id>", methods=["POST"])
    def abort(job_id: str):
        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"error": "Unknown job"}), 404
            stop_event = job.get("stop_event")
            if stop_event:
                stop_event.set()
            return jsonify({"aborted": job["status"] == "running"})

    @app.route("/api/health")
    def health():
        with _jobs_lock:
            running = sum(1 for j in _jobs.values() if j["status"] == "running")
        info: dict[str, Any] = {
            "status": "ok",
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

    return app
