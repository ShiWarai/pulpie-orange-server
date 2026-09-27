"""Пайплайн извлечения контента через pulpie."""

from __future__ import annotations

import gc
import threading
import time
from typing import Any

import torch
from pulpie import Extractor
from pulpie.chunker import extract_blocks, pack_chunks, tokenize_blocks
from pulpie.markdown import to_markdown
from pulpie.model_utils import extract_item_ids, predictions_to_labels
from pulpie.reconstruct import extract_main_html
from pulpie.simplify import simplify

from app.config import AppConfig


class ExtractorPool:
    """Один экстрактор на устройство; при смене device пересоздаётся."""

    def __init__(self, model_path: str) -> None:
        self._model_path = model_path
        self._extractor: Extractor | None = None
        self._device: str | None = None
        self._lock = threading.Lock()

    def get(self, device: str) -> Extractor:
        with self._lock:
            if self._extractor is None or self._device != device:
                if self._extractor is not None:
                    del self._extractor
                    self._extractor = None
                    if self._device == "cuda":
                        torch.cuda.empty_cache()
                    gc.collect()
                self._extractor = Extractor(model=self._model_path, device=device)
                self._device = device
            return self._extractor

    @property
    def loaded(self) -> bool:
        return self._extractor is not None

    @property
    def device(self) -> str | None:
        return self._device


def resolve_device(requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return requested


def _forward_chunk(extractor: Extractor, chunk_ids: list[int]) -> list[int]:
    input_ids = torch.tensor([chunk_ids], dtype=torch.long, device=extractor.device)
    attention_mask = torch.ones_like(input_ids)
    with torch.no_grad():
        logits = extractor.model(input_ids=input_ids, attention_mask=attention_mask).logits[0]
    sep_positions = (input_ids[0] == extractor.sep_token_id).nonzero(as_tuple=True)[0]
    return logits[sep_positions].argmax(dim=-1).cpu().tolist()


def run_extraction(
    html: str,
    extractor: Extractor,
    stop_event: threading.Event,
    job: dict[str, Any],
    max_tokens: int,
    as_html: bool,
) -> None:
    device = str(extractor.device)
    t0 = time.perf_counter()
    job["device"] = device
    job["progress"] = [0, 0]
    aborted = False
    try:
        simplified, map_html = simplify(html)
        blocks = extract_blocks(simplified)
        if not blocks:
            job.update(
                status="done",
                output="",
                kept=0,
                dropped=0,
                proc_ms=round((time.perf_counter() - t0) * 1000),
                progress=[0, 0],
                aborted=False,
            )
            return
        item_ids = extract_item_ids(blocks)
        block_token_ids = tokenize_blocks(blocks, extractor.tokenizer)
        chunks = pack_chunks(
            block_token_ids,
            max_tokens=max_tokens,
            sep_token_id=extractor.sep_token_id,
            bos_token_id=extractor.tokenizer.bos_token_id,
            eos_token_id=extractor.tokenizer.eos_token_id,
        )
        total = len(chunks)
        predictions = [0] * len(blocks)
        processed = 0
        for chunk_ids, block_indices in chunks:
            if stop_event.is_set():
                aborted = True
                labels = predictions_to_labels(item_ids, predictions)
                main_html = extract_main_html(map_html, labels)
                md = to_markdown(main_html)
                kept = sum(1 for v in labels.values() if v == "main")
                dropped = sum(1 for v in labels.values() if v == "other")
                job.update(
                    status="done",
                    output=(main_html if as_html else md),
                    html=main_html,
                    format="html" if as_html else "markdown",
                    kept=kept,
                    dropped=dropped,
                    proc_ms=round((time.perf_counter() - t0) * 1000),
                    progress=[processed, total],
                    aborted=True,
                )
                return
            try:
                preds = _forward_chunk(extractor, chunk_ids)
                for i, block_idx in enumerate(block_indices):
                    if i < len(preds):
                        predictions[block_idx] = preds[i]
            except Exception as e:
                msg = str(e).lower()
                is_oom = (
                    "out of memory" in msg
                    or "cudaoom" in msg
                    or ("oom" in msg and "memory" in msg)
                )
                if not is_oom:
                    job["error"] = f"{type(e).__name__}: {e}"
                    job["aborted"] = aborted
                    job.update(status="error", proc_ms=round((time.perf_counter() - t0) * 1000))
                    return
                job["error"] = (
                    f"OutOfMemory: страница слишком большая (max_tokens={max_tokens}). "
                    "Уменьшите размер чанка."
                )
                job["aborted"] = aborted
                job.update(status="error", proc_ms=round((time.perf_counter() - t0) * 1000))
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass
                return
            processed += 1
            job["progress"] = [processed, total]
        labels = predictions_to_labels(item_ids, predictions)
        main_html = extract_main_html(map_html, labels)
        md = to_markdown(main_html)
        job.update(
            status="done",
            output=main_html if as_html else md,
            html=main_html,
            format="html" if as_html else "markdown",
            kept=sum(1 for v in labels.values() if v == "main"),
            dropped=sum(1 for v in labels.values() if v == "other"),
            proc_ms=round((time.perf_counter() - t0) * 1000),
            progress=[processed, total],
            aborted=False,
        )
    except Exception as e:
        job["error"] = f"{type(e).__name__}: {e}"
        job["aborted"] = aborted
        job.update(status="error", proc_ms=round((time.perf_counter() - t0) * 1000))


def extract_sync(
    html: str,
    pool: ExtractorPool,
    device: str,
    max_tokens: int,
    as_html: bool,
) -> dict[str, Any]:
    """Синхронное извлечение для CLI."""
    stop_event = threading.Event()
    job: dict[str, Any] = {"status": "running"}
    run_extraction(html, pool.get(device), stop_event, job, max_tokens, as_html)
    return job
