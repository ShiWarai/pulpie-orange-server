# Pulpie Orange Small

[![Lint and test](https://github.com/ShiWarai/pulpie-orange-server/actions/workflows/deploy.yml/badge.svg)](https://github.com/ShiWarai/pulpie-orange-server/actions/workflows/deploy.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux%2Famd64%20%C2%B7%20arm64-orange.svg)
![Docker](https://img.shields.io/badge/docker-GHCR-blue.svg)

Локальный сервис и Docker-образы для [feyninc/pulpie-orange-small](https://huggingface.co/feyninc/pulpie-orange-small) — 210M encoder для извлечения основного контента из HTML.

Репозиторий: [github.com/ShiWarai/pulpie-orange-server](https://github.com/ShiWarai/pulpie-orange-server)

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

| Раздел | Содержание |
|--------|------------|
| [Быстрый старт](#быстрый-старт) | Сеть, `.env`, compose |
| [Установка и запуск](#установка-и-запуск) | Локально, CLI, Docker, GPU |
| [Модель](#модель) | Веса в `model/` |
| [API](#api) | `/v1`, ключ, статусы |
| [Структура проекта](#структура-проекта) | Дерево каталогов |
| [Тестирование](#тестирование) | ruff, pytest в dev-контейнере |
| [CI/CD](#cicd) | GHCR, Telegram |
| [Лицензия](#лицензия) | MIT |

---

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

---

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

### CLI

```powershell
# Файл
.venv\Scripts\python.exe -m app.cli page.html

# URL
.venv\Scripts\python.exe -m app.cli https://example.com

# stdin
Get-Content page.html | .venv\Scripts\python.exe -m app.cli

.venv\Scripts\python.exe -m app.cli page.html --device cuda
.venv\Scripts\python.exe -m app.cli page.html --time
.venv\Scripts\python.exe -m app.cli page.html -o output.md
.venv\Scripts\python.exe -m app.cli page.html --html
```

### Docker

| Сценарий | Команда |
|----------|---------|
| CPU (прод / GHCR) | `docker compose up --build -d` |
| NVIDIA GPU | `docker compose -f docker-compose.yml -f docker-compose.cuda.yml up --build -d` |
| GHCR prod (`main`) | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` |
| GHCR staging (`dev`) | `docker compose -f docker-compose.yml -f docker-compose.prod-dev.yml pull && docker compose -f docker-compose.yml -f docker-compose.prod-dev.yml up -d` |

`config.yaml`: хост `0.0.0.0`, порт `5000`, модель в `model/`, лимит входа 5 МБ, чанк 1024 токена, устройство `auto`. Переменная `API_KEY` перекрывает `api.key`.

---

## Модель

Скачайте веса [feyninc/pulpie-orange-small](https://huggingface.co/feyninc/pulpie-orange-small) в каталог `model/` (в git не входит):

```powershell
.venv\Scripts\pip install huggingface-hub
.venv\Scripts\python.exe ci\download_model.py
```

В контейнере тот же скрипт: `docker compose run --rm pulpie-orange python /app/ci/download_model.py`.

---

## API

Базовый префикс: `/v1`. Если задан `API_KEY`, все маршруты кроме `GET /v1/health` требуют заголовок `Authorization: Bearer <ключ>`. Пустой ключ оставляет API открытым — так удобно запускать сервис локально.

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

Тело запроса: ровно одно из полей `html` или `url`, плюс необязательные `device` (`auto` / `cpu` / `cuda`), `max_tokens` и `format` (`markdown` или `html`). Статусы задачи: `running`, `completed`, `cancelled`, `failed`.

---

## Структура проекта

```
pulpie-orange-server/
├── app/                    # python -m app.main | python -m app.cli
├── ci/download_model.py
├── tests/
├── .github/workflows/
│   ├── deploy.yml
│   └── publish.yml
├── config.yaml
├── model/                  # веса (не в git)
├── Dockerfile              # CPU → GHCR
├── Dockerfile.cuda         # GPU локально
├── Dockerfile.dev
└── docker-compose*.yml
```

---

## Тестирование

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm pulpie-orange-dev ruff check .
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm pulpie-orange-dev pytest tests/ -v --cov=app
```

---

## CI/CD

- **deploy.yml** — на push/PR в `main` и `dev`: ruff и pytest в Docker (CPU-образ). Workflow в Actions называется **Lint and test**.
- **publish.yml** — после успешных проверок: образ `ghcr.io/<owner>/pulpie-orange` (`:main` или `:dev` и тег по SHA). В Telegram уходит статус проверок и, после публикации, имя образа и теги.

Перед первым push: в настройках репозитория разрешите **Read and write** для `GITHUB_TOKEN` (пакеты GHCR). Опционально: `TELEGRAM_TOKEN`, `TELEGRAM_TO`.

GPU-образ (`Dockerfile.cuda`) в registry не публикуется — только локальная сборка через `docker-compose.cuda.yml`.

---

## Лицензия

MIT — см. [LICENSE](LICENSE).

_Исходный код проекта написан домашней нейросетью (Qwen 3.8 27B)._
