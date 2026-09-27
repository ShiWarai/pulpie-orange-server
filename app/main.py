"""Точка входа: веб-сервер Pulpie Orange."""

import argparse
import sys

import torch

from app.config import load_config
from app.extraction import ExtractorPool, resolve_device
from app.web.server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pulpie Orange Small — извлечение контента из HTML",
    )
    parser.add_argument("--host", type=str, default=None, help="Хост (по умолчанию из config.yaml)")
    parser.add_argument("--port", type=int, default=None, help="Порт (по умолчанию из config.yaml)")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Путь к config.yaml",
    )
    parser.add_argument("--debug", action="store_true", help="Режим отладки Flask")
    parser.add_argument(
        "--warmup",
        action="store_true",
        help="Загрузить модель при старте (чтобы не ждать первый запрос)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    host = args.host or config.server.host
    port = args.port or config.server.port

    if args.warmup:
        device = resolve_device(config.extraction.default_device)
        pool = ExtractorPool(model_path=str(config.model.path))
        try:
            pool.get(device)
            print(f"Модель загружена ({device}).")
        except Exception as e:
            print("Не удалось загрузить модель:", e, file=sys.stderr)

    app = create_app(config)
    print(f"Сервер: http://{host}:{port}")
    print(f"Конфигурация: {args.config}")
    print(f"CUDA доступна: {torch.cuda.is_available()}")
    app.run(host=host, port=port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
