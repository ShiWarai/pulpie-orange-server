# Pulpie Orange Small

[![Lint and test](https://github.com/ShiWarai/pulpie-orange-server/actions/workflows/deploy.yml/badge.svg)](https://github.com/ShiWarai/pulpie-orange-server/actions/workflows/deploy.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux%2Famd64%20%C2%B7%20arm64-orange.svg)
![Docker](https://img.shields.io/badge/docker-GHCR-blue.svg)

Локальный сервис и Docker-образы для [feyninc/pulpie-orange-small](https://huggingface.co/feyninc/pulpie-orange-small) — 210M encoder для извлечения основного контента из HTML.

## Стек технологий

| Категория | Технологии |
|-----------|------------|
| Inference | PyTorch, `pulpie`, EuroBERT encoder 210M |
| API | Flask, REST `/v1` |
| Интерфейс | Веб-UI, CLI |
| Инфраструктура | Docker, Docker Compose, GHCR |
| CI | GitHub Actions, ruff, pytest |
| Платформа | **linux/amd64** и **linux/arm64** (CPU); NVIDIA CUDA — локальная сборка |

## Оглавление

- [Быстрый старт](#быстрый-старт)
- [Установка и запуск](#установка-и-запуск)
- [Модель](#модель)
- [API](#api)
- [Структура проекта](#структура-проекта)
- [Тестирование](#тестирование)
- [CI/CD](#cicd)
- [Лицензия](#лицензия)

## Быстрый старт

1. Создайте Docker-сеть (один раз):

   ```powershell
   docker network create pulpie-services-network
   ```

2. Настройте `.env`:

   ```powershell
   copy .env.example .env
   # HF_TOKEN, API_KEY — см. .env.example
   ```

3. Соберите и запустите:

   ```powershell
   docker compose up --build -d
   docker compose run --rm pulpie-orange python /app/ci/download_model.py
   ```

Веб-UI: **http://localhost:5000**. Контейнер: `pulpie-orange`, порт **5000**. Модель — том `pulpie_model` → `/app/model`.

## Установка и запуск

### Зависимости

| Вариант | Команда |
|---------|---------|
| **CPU** | `pip install -r requirements-docker.txt` |
| **NVIDIA CUDA** | [PyTorch с CUDA](https://pytorch.org), затем `pip install -r requirements-cuda.txt` |

Локальный сервер:

```powershell
.venv\Scripts\python.exe -m app.main --warmup
```

Опции: `--host`, `--port`, `--config`, `--debug`, `--warmup`.

### Docker

| Сценарий | Команда |
|----------|---------|
| CPU (прод / GHCR) | `docker compose up --build -d` |
| NVIDIA GPU | `docker compose -f docker-compose.yml -f docker-compose.cuda.yml up --build -d` |
| GHCR prod (`main`) | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` |
| GHCR staging (`dev`) | `docker compose -f docker-compose.yml -f docker-compose.prod-dev.yml pull && docker compose -f docker-compose.yml -f docker-compose.prod-dev.yml up -d` |

`config.yaml`: хост `0.0.0.0`, порт `5000`, модель в `model/`, лимит входа 5 МБ, чанк 1024 токена, устройство `auto`. Переменная `API_KEY` перекрывает `api.key`.

## Модель

Скачайте веса [feyninc/pulpie-orange-small](https://huggingface.co/feyninc/pulpie-orange-small) в каталог `model/` (в git не входит):

```powershell
.venv\Scripts\pip install huggingface-hub
.venv\Scripts\python.exe ci\download_model.py
```

В контейнере тот же скрипт: `docker compose run --rm pulpie-orange python /app/ci/download_model.py`.

## API

Базовый префикс: `/v1`. Все маршруты кроме `GET /v1/health` требуют заголовок `Authorization: Bearer <ключ>`. Ключ обязателен: при пустом `API_KEY`/`api.key` сервер не стартует.

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/v1/health` | Статус сервиса и модели, без ключа |
| POST | `/v1/extractions` | Запуск извлечения, ответ `202` и `id` |
| GET | `/v1/extractions/<id>` | Прогресс и результат |
| POST | `/v1/extractions/<id>/cancel` | Отмена задачи |

```powershell
curl -s http://localhost:5000/v1/extractions `
  -H "Authorization: Bearer $env:API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"html\": \"<html><body><p>Привет</p></body></html>\", \"format\": \"markdown\"}"
```

Тело запроса: поле `html` (готовый HTML), плюс необязательные `device` (`auto` / `cpu` / `cuda`), `max_tokens` и `format` (`markdown` или `html`). Статусы задачи: `running`, `completed`, `cancelled`, `failed`.

## Структура проекта

```
pulpie-orange-server/
├── app/                    # python -m app.main
├── ci/download_model.py
├── tests/
├── .github/workflows/
│   ├── deploy.yml          # гейт: ruff + pytest на push
│   ├── release-please.yml  # режет тег на мерже в main
│   └── publish.yml         # публикует образы по тегу
├── release-please-config.json
├── .release-please-manifest.json
├── config.yaml
├── model/                  # веса (не в git)
├── Dockerfile              # CPU → GHCR
├── Dockerfile.cuda         # GPU локально
├── Dockerfile.dev
└── docker-compose*.yml
```

## Тестирование

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm pulpie-orange-dev ruff check .
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm pulpie-orange-dev pytest tests/ -v --cov=app
```

## CI/CD

Три workflow, каждый отвечает за свой этап — без дублирующих запусков:

- **deploy.yml** (**Lint and test**) — гейт. На каждый `push` в `main` и `dev`: ruff и pytest в Docker. Публикацию не делает. `pull_request` намеренно не триггерит (иначе push в `dev` + открытый PR `dev→main` гоняли пайплайн дважды).
- **release-please.yml** — на `push` в `main` (то есть на мерж) режет тег по conventional-коммитам: обычный → `v1.2.3`, с маркером `[prerelease]` в коммите → `v1.2.3-pre.N`. Ведёт версию (`0.1.0` в `.release-please-manifest.json`) и `CHANGELOG.md`.
- **publish.yml** — публикует образы **только по тегу** `v*`. Prerelease-тег → `:dev` (+ `:<версия>`, `-cuda`), обычный тег → `:main` + `:latest` (+ `:<версия>`, `-cuda`). В Telegram — одно сводное сообщение со статусами CPU и CUDA.

Схема тегов образов:

| Тег | CPU | CUDA |
|-----|-----|------|
| `v1.2.3` (release) | `:1.2.3`, `:main`, `:latest` | `:1.2.3-cuda`, `:main-cuda`, `:latest-cuda` |
| `v1.2.3-pre.1` (prerelease) | `:1.2.3-pre.1`, `:dev` | `:1.2.3-pre.1-cuda`, `:dev-cuda` |

Перед первым push: в настройках репозитория разрешите **Read and write** для `GITHUB_TOKEN` (пакеты GHCR + тег). Опционально: `TELEGRAM_TOKEN`, `TELEGRAM_TO`.

GPU-образ (`Dockerfile.cuda`) публикуется вместе с CPU тем же тегом; базовый `pytorch/*cuda*` существует только для `linux/amd64`, поэтому без arm64-варианта.

## Лицензия

Проект распространяется по лицензии [MIT](https://opensource.org/licenses/MIT).

## Авторские права

Copyright (c) 2026 Shi Warai. Подробности — в [LICENSE](LICENSE).
