# СибКонтур — мониторинг строительства

MVP для банка: менеджер ведёт объекты и контрольные точки, оператор БПЛА загружает фото, AI-агент позже сам пишет отчёты в ту же PostgreSQL.

Сервисы **не вызывают друг друга по HTTP**. Общая точка — база `dronemon` и сеть `dronemon_net`.

Общего корневого `docker-compose.yml` нет: у каждого сервиса свой файл, чтобы поднимать и тестировать их по отдельности. Агента встраиваем, когда он будет готов.

## Сервисы

| Каталог | Compose | Контейнер | Назначение |
|---|---|---|---|
| `Infra/` | свой | `dronemon-db` | PostgreSQL, создаёт сеть `dronemon_net` |
| `photo-preprocessing/` | свой | `dronemon-api` | Приём и проверка фото |
| `db-api/` | свой | `dronemon-db-api` | Объекты, точки, алерты, задачи оператора |
| `web/` | свой | `dronemon-web` | Кабинеты менеджера и оператора |
| агент | позже | — | Читает storage, пишет `ai_reports` в ту же БД |

## Запуск по сервисам

Сначала инфраструктура — она создаёт сеть и БД:

```bash
cd Infra
docker compose up -d
```

Дальше любой сервис независимо:

```bash
cd photo-preprocessing
docker compose up -d --build

cd ../db-api
docker compose up -d --build

cd ../web
cp .env.example .env          # PHOTO_API_TOKEN = API_TOKEN photo-сервиса
docker compose up -d --build
```

Остановить один сервис, не трогая остальные:

```bash
cd db-api && docker compose down
```

Интерфейс: http://127.0.0.1:3000  
Photo API: http://127.0.0.1:8222  
db-api: http://127.0.0.1:8001  
Postgres: `127.0.0.1:5432`

Демо-вход (регистрации нет):

- менеджер: `manager` / `manager`
- оператор: `operator` / `operator`

## Фронт без Docker

Удобно, пока крутятся только Infra + photo + db-api:

```bash
cd web
cp .env.example .env.local
# PHOTO_API_URL=http://127.0.0.1:8222
# PHOTO_API_TOKEN из photo-preprocessing/.env
# NEXT_PUBLIC_DB_API_URL=http://127.0.0.1:8001
npm install
npm run dev
```

## db-api без Docker

```bash
cd db-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DB_DSN=postgresql+asyncpg://admin:secret@127.0.0.1:5432/dronemon
alembic upgrade head
python scripts/seed_demo.py
uvicorn app.main:app --reload --port 8001
```

## Переменные окружения

Только у каждого сервиса:

- `photo-preprocessing/.env.example`
- `db-api/.env.example`
- `web/.env.example`

Секреты не кладём во frontend-бандл. Токен photo API живёт в Next.js BFF.

## Миграции

Две независимые истории Alembic на одну БД:

- `photo-preprocessing` — таблица `alembic_version`, revision `0001`
- `db-api` — таблица `alembic_version_db_api`, revision `0001_platform`

`0001` photo-сервиса не меняем.

## Демоданные

```bash
cd db-api && python scripts/seed_demo.py
```

Идемпотентно: трогает только `is_demo=true`.

## Потоки данных

1. Менеджер создаёт объект в db-api → PostgreSQL.
2. Оператор читает задачи из db-api.
3. Оператор грузит пачку в photo-preprocessing.
4. Confirm по объекту → storage + `processing_queue`.
5. Когда агент будет готов: читает storage, пишет `ai_reports` / `problem_alerts`.
6. Менеджер читает отчёты через db-api.

## Контракт для будущего AI-агента

Агент не вызывается из наших FastAPI. Свой compose добавим отдельно, когда сервис появится. Пишет в ту же PostgreSQL.

Таблица `ai_reports`:

- `id` — строка, например `rep_<hex>`
- `object_id` — существующий объект
- `checkpoint_id` — опционально
- `agent_run_id` — идемпотентность запуска
- `raw_json` JSONB — исходный ответ, предыдущие запуски не перезаписывать
- `is_demo` — false для боевых прогонов
- каждый запуск = новая строка

Ожидаемые, но не обязательные ключи `raw_json`:

```json
{
  "overall_readiness_pct": 72,
  "overall_status": "yellow",
  "stages": [
    {"name": "Фундамент", "readiness_pct": 100, "status": "green"}
  ],
  "comments": ["текстовые замечания"],
  "problems": [
    {
      "code": "ROOF_GAP",
      "severity": "yellow",
      "title": "Пробел покрытия крыши",
      "description": "..."
    }
  ]
}
```

Иначе фронт покажет сырой JSON. Проблемы можно сразу класть в `problem_alerts`.

## Photo API

Существующие endpoint-ы на месте. Добавлен per-object confirm:

`POST /v1/batches/{batch_id}/objects/{object_id}/confirm`

## Ограничения MVP

- Нет карты и парсинга границ из документов
- Нет импорта Excel/CSV
- Агент ещё не встроен
- Нет сложной дисциплины оператора и уведомлений
