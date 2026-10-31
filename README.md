# СибКонтур — мониторинг строительства

Версия 3.5. Банк ведёт залоговые объекты, оператор БПЛА загружает несколько ракурсов за один день, агент пишет один отчёт по всей группе снимков, менеджер может запросить демонстрационную оценку стоимости.

Сервисы не вызывают друг друга по HTTP. Общая точка — PostgreSQL `dronemon` и сеть `dronemon_net`. У каждого сервиса свой compose, чтобы поднимать их по отдельности.

## Адреса

Боевой контур:

| Назначение | Адрес |
|---|---|
| Кабинет менеджера и оператора | https://app.yarolit.ru |
| db-api | https://app.yarolit.ru/db-api |
| Photo API | https://api.yarolit.ru/drones/ |

Локально порты только на `127.0.0.1`. Наружу — через nginx, пример vhost: `Infra/nginx-sibcode.conf`.

| Назначение | Адрес |
|---|---|
| UI | http://127.0.0.1:3000 |
| Photo API | http://127.0.0.1:8222 |
| db-api | http://127.0.0.1:8001 |

Демо-вход (регистрации нет):

- менеджер: `manager` / `manager`
- оператор: `operator` / `operator`

## Сервисы

| Каталог | Контейнер | Назначение |
|---|---|---|
| `Infra/` | `dronemon-db` | PostgreSQL, создаёт сеть `dronemon_net` |
| `photo-preprocessing/` | `dronemon-api` | Приём, проверка, ручная привязка и хранение фото |
| `db-api/` | `dronemon-db-api` | Объекты, точки, алерты, задачи, импорт реестра |
| `web/` | `dronemon-web` | Кабинеты менеджера и оператора |
| `analysis-agent/` | `dronemon-analysis-agent` | Очередь → LLM → `analysis_reports` + HTML |
| `price-mock-agent/` | `dronemon-price-mock-agent` | Мок-оценка стоимости по готовому отчёту анализа |

## Что умеет эта версия

Менеджер:

- объекты, контрольные точки, календарь, алерты;
- границы участка: **1 точка** (центроид) или **4+** (полигон); 2–3 точки нельзя;
- импорт банковского Excel-реестра (`Территория`, кадастр, плановая дата, залог и т.д.);
- план строительства свободным текстом для агента;
- AI-отчёт на карточке объекта: готовность, чек-лист, кропы с разметкой, галерея фото, ссылка на HTML;
- **Сделать оценку** — демо-диапазон цены по последнему completed-отчёту анализа (бейдж ДЕМО / МОК);
- уведомление о новых фото оператора; объекты со свежими снимками сверху.

Оператор:

- в смену попадают только объекты с координатами;
- кнопка **Загрузить фото** — несколько ракурсов одного или разных объектов за раз;
- после проверки: миниатюра, метаданные, контур участка если точек ≥ 4;
- если GPS не нашёл объект — **ручная привязка** поиском по адресу или кадастру;
- неудачная загрузка без битой миниатюры;
- **Отправить в работу** кладёт все уникальные validated-фото в хранилище и одну задачу агента на `(загрузка, объект)`;
- один warning на объект, если просрочено несколько контрольных точек.

Проверка фото:

- GPS-совпадение ±50 м (полигон с буфером или одна точка-центроид);
- несколько разных ракурсов одного объекта не схлопываются: в хранилище уходят все уникальные файлы;
- режется только полный дубликат по SHA-256 и снимок **прошлого дня** относительно уже принятого периода или более позднего дня в этой же загрузке;
- проверка высоты временно отключена.

Агент (мультифото):

- забирает `processing_queue` (`FOR UPDATE SKIP LOCKED`), статусы загрузки `ready` или `confirmed`;
- единица анализа — все фото объекта за максимальную дату съёмки в этой загрузке, не больше 8 кадров;
- одно фото: только `crop_photo_tool`, до 4 кропов;
- несколько фото: миниатюры + `select_photo_tool` (до 4 полных) + `crop_photo_tool` (до 6 кропов);
- если по объекту уже есть более новый завершённый отчёт, группа пропускается;
- пишет `analysis_reports` и HTML в storage (`text/html`).

Мок-оценка стоимости:

- кнопка активна только если есть completed-отчёт анализа;
- db-api агрегирует объект, план и отчёт в `price_search_tasks.spec_json`, LLM на дашборде нет;
- повторный клик при `pending`/`processing` новую задачу не создаёт;
- `price-mock-agent` поллит задачи, один LLM-вызов, пишет `price_reports`;
- в карточке: диапазон, точка, обоснование, 3–6 выдуманных аналогов и явное предупреждение, что это демо;
- это не парсинг рынка и не официальная оценка.

## Потоки данных

1. Менеджер создаёт объект или импортирует реестр → db-api → PostgreSQL.
2. Координаты участка обязательны, иначе пилот задачу не видит.
3. Оператор загружает фото в photo-preprocessing. Автопривязка по GPS или ручной выбор объекта.
4. Отправка в работу грузит **все** уникальные validated-фото в storage и ставит одну задачу на `(batch_id, object_id)`:
   фото максимальной даты съёмки, обложка = ближайшее к центроиду, статус загрузки `ready`.
5. Агент берёт группу и пишет один отчёт на объект.
6. Менеджер видит отчёт на карточке объекта.
7. По кнопке «Сделать оценку» db-api ставит `price_search_tasks`, мок-агент пишет `price_reports`.

## Запуск

Сначала инфраструктура — она создаёт сеть и БД:

```bash
cd Infra
docker compose up -d
```

На сервере, где порт 5432 уже занят другим Postgres, новый контейнер БД не поднимать: использовать уже существующий `dronemon-db`.

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
# NEXT_PUBLIC_DB_API_URL=https://app.yarolit.ru/db-api   # на проде
docker compose up -d --build

cd ../analysis-agent
cp .env.example .env
docker compose up -d --build

cd ../price-mock-agent
cp .env.example .env
# LLM_* те же, что у analysis-agent
docker compose up -d --build
```

Остановить один сервис, не трогая остальные:

```bash
cd db-api && docker compose down
```

Если alpine-сборка фронта ломается на `npm`, соберите standalone на хосте (Node 20) и поднимите `web/docker-compose.prebuilt.yml`:

```bash
cd web
export NEXT_PUBLIC_DB_API_URL=https://app.yarolit.ru/db-api
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
- `price-mock-agent/.env.example`

Токен photo API живёт в Next.js BFF, не в браузерном бандле.

GPS-буфер: `VALIDATION__GPS_BUFFER_M` и `VALIDATION__CENTROID_BUFFER_M`, по умолчанию 50 м.

## Миграции

Две независимые истории Alembic на одну БД:

- `photo-preprocessing` — таблица `alembic_version` (ревизия `0002_multi_photo`: группа очереди)
- `db-api` — таблица `alembic_version_db_api` (ревизия `0002_price_mock`: `price_search_tasks`, `price_reports`)

Ревизии photo-сервиса не переписываем. Таблицы агента (`analysis_reports`, `construction_plans`) создаются через `create_all` без FK на фото.

Идемпотентный SQL на уже живую БД:

```bash
psql "$DSN" -f scripts/migrate_v2_multiphoto.sql
```

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

## Photo API

Существующие endpoint-ы на месте. Для кабинета и агента важны:

- `POST /v1/batches` + `.../upload` + `.../process` — загрузить и проверить
- `POST /v1/surveys/{id}/assign` — ручная привязка к объекту
- `POST /v1/batches/{batch_id}/confirm` — отправить всю загрузку в работу
- `POST /v1/batches/{batch_id}/objects/{object_id}/confirm` — отправить один объект
- `GET /api/v1/storage/{bucket}/{key}` — файлы и HTML-отчёты

Оценка стоимости (db-api, только менеджер на POST):

- `GET /api/objects/{id}/price-estimate` — статус задачи и последний мок-отчёт
- `POST /api/objects/{id}/price-estimate` — создать задание или вернуть уже активное

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
- Без даты в EXIF период съёмки не угадываем — такой файл по «прошлому дню» не режем
