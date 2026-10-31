# СибКонтур — мониторинг строительства

Стабильная версия 1. Банк ведёт залоговые объекты, оператор БПЛА загружает аэрофото, агент пишет отчёт по снимку.

Сервисы не вызывают друг друга по HTTP. Общая точка — PostgreSQL `dronemon` и сеть `dronemon_net`. У каждого сервиса свой compose, чтобы поднимать их по отдельности.

## Сервисы

| Каталог | Контейнер | Назначение |
|---|---|---|
| `Infra/` | `dronemon-db` | PostgreSQL, создаёт сеть `dronemon_net` |
| `photo-preprocessing/` | `dronemon-api` | Приём, проверка и хранение фото |
| `db-api/` | `dronemon-db-api` | Объекты, точки, алерты, задачи, импорт реестра |
| `web/` | `dronemon-web` | Кабинеты менеджера и оператора |
| `analysis-agent/` | `dronemon-analysis-agent` | Очередь → LLM → `analysis_reports` + HTML |

Порты только на `127.0.0.1`. Наружу — через nginx, пример vhost: `Infra/nginx-sibcode.conf`.

- UI: http://127.0.0.1:3000
- Photo API: http://127.0.0.1:8222
- db-api: http://127.0.0.1:8001

Демо-вход (регистрации нет):

- менеджер: `manager` / `manager`
- оператор: `operator` / `operator`

## Что умеет эта версия

Менеджер:

- объекты, контрольные точки, календарь, алерты;
- границы участка: **1 точка** (центроид) или **4+** (полигон); 2–3 точки нельзя;
- импорт банковского Excel-реестра (`Территория`, кадастр, плановая дата, залог и т.д.);
- план строительства свободным текстом для агента;
- AI-отчёт на карточке объекта: готовность, чек-лист, кропы с разметкой, ссылка на HTML;
- уведомление о новых фото оператора; объекты с свежими снимками сверху.

Оператор:

- в смену попадают только объекты с координатами;
- кнопка **Загрузить фото**;
- после проверки — миниатюра, метаданные, контур участка если точек ≥ 4;
- неудачная загрузка без битой миниатюры;
- согласование батча отправляет validated-фото в хранилище и в очередь агента;
- один warning на объект, если просрочено несколько контрольных точек.

Проверка фото:

- GPS-совпадение ±10 м (и для одной точки, и для полигона);
- проверка высоты временно отключена;
- одна GPS-точка объекта = центроид с буфером.

Агент:

- забирает `processing_queue` (`FOR UPDATE SKIP LOCKED`);
- режимы с планом и без;
- пишет `analysis_reports` и HTML в storage.

## Запуск

Сначала инфраструктура — она создаёт сеть и БД:

```bash
cd Infra
docker compose up -d
```

Дальше сервисы по отдельности:

```bash
cd photo-preprocessing
cp .env.example .env
docker compose up -d --build

cd ../db-api
cp .env.example .env
docker compose up -d --build

cd ../web
cp .env.example .env
# PHOTO_API_TOKEN = API_TOKEN photo-сервиса
docker compose up -d --build

cd ../analysis-agent
cp .env.example .env
docker compose up -d --build
```

Остановить один сервис, не трогая остальные:

```bash
cd db-api && docker compose down
```

Если alpine-сборка фронта ломается на `npm`, соберите standalone на хосте (Node 20) и поднимите `web/docker-compose.prebuilt.yml`:

```bash
cd web
export NEXT_PUBLIC_DB_API_URL=http://127.0.0.1:8001
npm ci
npm run build
mkdir -p .next/standalone/.next/static .next/standalone/public
cp -a .next/static/. .next/standalone/.next/static/
cp -a public/. .next/standalone/public/
docker compose -f docker-compose.prebuilt.yml up -d
```

## Фронт без Docker

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

Только у каждого сервиса, секреты в git не кладём:

- `photo-preprocessing/.env.example`
- `db-api/.env.example`
- `web/.env.example`
- `analysis-agent/.env.example`

Токен photo API живёт в Next.js BFF, не в браузерном бандле.

## Миграции

Две независимые истории Alembic на одну БД:

- `photo-preprocessing` — таблица `alembic_version`
- `db-api` — таблица `alembic_version_db_api`

Ревизии photo-сервиса не переписываем. Таблицы агента (`analysis_reports`, `construction_plans`) создаются через `create_all` без FK на фото.

## Демоданные и сброс теста

```bash
cd db-api && python scripts/seed_demo.py
```

Идемпотентно: трогает только `is_demo=true`.

Очистить боевые/тестовые данные, не ломая схему и пользователей входа:

```bash
./scripts/reset_test_db.sh          # только план
./scripts/reset_test_db.sh --yes
./scripts/reset_test_db.sh --yes --seed
./scripts/reset_test_db.sh --yes --seed --storage
```

`--storage` ещё чистит raw-снимки и HTML-отчёты в volume `dronemon-api_s3_storage`. На проде без явной просьбы не запускать.

## Потоки данных

1. Менеджер создаёт объект или импортирует реестр → db-api → PostgreSQL.
2. Координаты участка обязательны, иначе пилот задачу не видит.
3. Оператор загружает фото в photo-preprocessing.
4. Согласование батча → storage + `processing_queue` + уведомление менеджеру.
5. Агент читает очередь и storage, пишет `analysis_reports` и HTML.
6. Менеджер видит отчёт на карточке объекта.

## Photo API

Существующие endpoint-ы на месте. Для агента нужны:

- `POST /v1/batches/{batch_id}/confirm` — согласовать весь батч
- `POST /v1/batches/{batch_id}/objects/{object_id}/confirm` — согласовать объект
- `GET /api/v1/storage/{bucket}/{key}` — файлы и HTML-отчёты

## Импорт реестра

`POST /api/objects/import` (xlsx). Ожидаемые колонки:

- Территория → адрес
- Кадастровый номер
- Плановая дата
- Дата начала строительства / кредит
- остальные поля реестра сохраняются по возможности

Координат в банковском файле нет — границы добавляются позже в карточке объекта.

## Ограничения

- Нет карты и парсинга границ из документов
- Проверка высоты съёмки временно выключена
- 2–3 точки участка нельзя: только 1 или 4+
