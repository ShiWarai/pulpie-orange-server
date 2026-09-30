"""Загрузка HTML из строки, файла или URL."""

from __future__ import annotations

import ssl
import urllib.request
from pathlib import Path

_URL_TIMEOUT = 30


def load_html(source: str, source_type: str | None, ssl_verify: bool, timeout: float = _URL_TIMEOUT) -> str:
    if source_type in (None, "string"):
        return source
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0"})
        ctx = None if ssl_verify else ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get("Content-Type", "")
            if "charset=" in charset.lower():
                enc = charset.split("charset=")[1].split(";")[0].strip()
            else:
                head = raw[:2048].decode("ascii", errors="ignore")
                enc = "utf-8"
                if "charset=" in head.lower():
                    enc = head.lower().split("charset=")[1].split(";")[0].split('"')[0].strip()
            return raw.decode(enc, errors="replace")
    return Path(source).read_text(encoding="utf-8")
