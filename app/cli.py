"""CLI: извлечение контента из HTML без веб-сервера."""

import argparse
import sys
import time

from app.config import load_config
from app.extraction import ExtractorPool, extract_sync, resolve_device
from app.html_loader import load_html


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pulpie Orange Small — CLI извлечения HTML → Markdown",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Путь к HTML, URL, или '-' для stdin",
    )
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("-o", "--output", help="Сохранить результат в файл")
    parser.add_argument("--html", action="store_true", help="Вывод в HTML вместо Markdown")
    parser.add_argument("--time", action="store_true", help="Показать время в stderr")
    parser.add_argument("--max-tokens", type=int, default=None, help="Размер чанка (токены)")
    parser.add_argument("--config", default="config.yaml", help="Путь к config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    max_tokens = args.max_tokens or config.extraction.default_max_tokens
    device = resolve_device(args.device)

    if args.input == "-":
        html = sys.stdin.read()
        source_type = "string"
        source = html
    else:
        source = args.input
        if source.startswith(("http://", "https://")):
            source_type = "url"
        elif source.endswith((".html", ".htm")) or "/" in source or "\\" in source:
            source_type = "file"
        else:
            source_type = "string"
        html = load_html(source, source_type, config.http.ssl_verify)

    if len(html) > config.extraction.max_input_bytes:
        html = html[: config.extraction.max_input_bytes]

    pool = ExtractorPool(model_path=str(config.model.path))
    t0 = time.perf_counter()
    job = extract_sync(html, pool, device, max_tokens, args.html)
    elapsed = time.perf_counter() - t0

    if job.get("status") == "error":
        print(job.get("error", "unknown error"), file=sys.stderr)
        sys.exit(1)

    out = job.get("output", "")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)

    if args.time:
        proc = job.get("proc_ms", round(elapsed * 1000))
        print(f"proc={proc}ms device={job.get('device', device)}", file=sys.stderr)


if __name__ == "__main__":
    main()
