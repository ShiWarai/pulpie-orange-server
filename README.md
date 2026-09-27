# Pulpie Orange Small — HTML Content Extraction

Локальный сервис и Docker-образы для [feyninc/pulpie-orange-small](https://huggingface.co/feyninc/pulpie-orange-small) — 210M encoder для извлечения основного контента из HTML.

## Быстрый старт (Docker, CPU)

```powershell
copy .env.example .env
docker network create pulpie-services-network
docker compose up --build -d
docker compose run --rm pulpie-orange python /app/ci/download_model.py
```

Веб-UI: **http://localhost:5000**

## Установка и запуск

### Модель

Скачайте веса в каталог `model/`:

```powershell
.venv\Scripts\pip install huggingface-hub
.venv\Scripts\python.exe ci\download_model.py
```

### Варианты зависимостей

| Вариант | Команда |
|---------|---------|
| **CPU** | `pip install -r requirements-docker.txt` |
| **NVIDIA CUDA** | [PyTorch с CUDA](https://pytorch.org), затем `pip install -r requirements-cuda.txt` |

### Локально

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
| GHCR staging (`dev`) | `docker compose -f docker-compose.yml -f docker-compose.prod-dev.yml pull && ... up -d` |

Контейнер: `pulpie-orange`, порт **5000**. Модель — том `pulpie_model` → `/app/model`.

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

## config.yaml

```yaml
server:
  host: "0.0.0.0"
  port: 5000
model:
  path: "model"
extraction:
  max_input_bytes: 5000000
  default_max_tokens: 1024
  default_device: "auto"
api:
  key: ""
```

Переменная окружения `API_KEY` перекрывает `api.key`.

## Разработка

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm pulpie-orange-dev ruff check .
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm pulpie-orange-dev pytest tests/ -v --cov=app
```

## CI/CD

- **deploy.yml** — на push/PR в `main` и `dev`: ruff и pytest в Docker (CPU-образ).
- **publish.yml** — после успешного deploy: публикация образа `ghcr.io/<owner>/pulpie-orange` (`:main` или `:dev` и тег по SHA).

Перед первым push: в настройках репозитория разрешите **Read and write** для `GITHUB_TOKEN` (пакеты GHCR). Опционально: `TELEGRAM_TOKEN`, `TELEGRAM_TO`.

GPU-образ (`Dockerfile.cuda`) в registry не публикуется — только локальная сборка через `docker-compose.cuda.yml`.

## Структура

```
.
├── app/                    # python -m app.main | python -m app.cli
├── ci/download_model.py
├── config.yaml
├── model/                  # веса (не в git)
├── tests/
├── Dockerfile              # CPU → GHCR
├── Dockerfile.cuda         # GPU локально
└── docker-compose*.yml
```

## Лицензия

MIT

---

_Исходный код проекта написан домашней нейросетью (Qwen 3.8 27B)._
