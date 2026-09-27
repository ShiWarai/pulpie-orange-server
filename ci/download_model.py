"""Скачать feyninc/pulpie-orange-small в каталог model/."""

import argparse
import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

REPO_ID = "feyninc/pulpie-orange-small"


def main() -> None:
    parser = argparse.ArgumentParser(description="Загрузка модели Pulpie Orange Small")
    parser.add_argument(
        "--dest",
        default="model",
        help="Каталог назначения (по умолчанию: model)",
    )
    parser.add_argument("--repo-id", default=REPO_ID, help="ID репозитория на Hugging Face")
    args = parser.parse_args()

    dest = Path(args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    print(f"Загрузка {args.repo_id} → {dest}")
    snapshot_download(
        repo_id=args.repo_id,
        local_dir=str(dest),
        token=token,
    )
    print("Готово.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
