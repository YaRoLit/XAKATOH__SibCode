#!/usr/bin/env bash
# Очищает данные dronemon для тестового прогона. Схему и миграции не трогает.
# Пользователи manager/operator остаются.
#
#   ./scripts/reset_test_db.sh --yes
#   ./scripts/reset_test_db.sh --yes --seed
#   ./scripts/reset_test_db.sh --yes --seed --storage
set -euo pipefail

YES=0
SEED=0
STORAGE=0
DB_CONTAINER="${DB_CONTAINER:-dronemon-db}"
DB_USER="${DB_USER:-admin}"
DB_NAME="${DB_NAME:-dronemon}"
API_CONTAINER="${API_CONTAINER:-dronemon-db-api}"
VOLUME="${STORAGE_VOLUME:-dronemon-api_s3_storage}"

usage() {
  cat <<'EOF'
Очистка базы dronemon для теста.

  --yes       обязательно: без этого флага скрипт только показывает план
  --seed      после очистки заново накатить demo (seed_demo.py)
  --storage   ещё стереть raw/ и agent_reports/ в docker-volume фотохранилища

Не удаляет таблицы, alembic-версии и пользователей входа.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --yes) YES=1 ;;
    --seed) SEED=1 ;;
    --storage) STORAGE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Неизвестный аргумент: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if ! docker inspect "$DB_CONTAINER" >/dev/null 2>&1; then
  echo "Контейнер $DB_CONTAINER не найден" >&2
  exit 1
fi

echo "База: $DB_CONTAINER / $DB_NAME"
echo "Будут очищены таблицы данных (схема останется):"
echo "  analysis_reports, construction_plans, problem_actions, problem_alerts,"
echo "  ai_reports, checkpoint_date_history, checkpoints,"
echo "  processing_queue, surveys, batches, objects"
echo "Не трогаем: users, alembic_version, alembic_version_db_api"
if [ "$SEED" -eq 1 ]; then
  echo "Потом: seed_demo.py в $API_CONTAINER"
fi
if [ "$STORAGE" -eq 1 ]; then
  echo "Потом: очистка $VOLUME (raw/, agent_reports/)"
fi

if [ "$YES" -ne 1 ]; then
  echo
  echo "Это разрушительная операция. Чтобы выполнить, повтори с --yes"
  exit 3
fi

if docker inspect -f '{{.State.Running}}' dronemon-analysis-agent 2>/dev/null | grep -qx true; then
  echo "Внимание: analysis-agent сейчас запущен. Если он держит задачу, сначала останови его."
fi

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" <<'SQL'
BEGIN;
TRUNCATE TABLE
  problem_actions,
  problem_alerts,
  analysis_reports,
  construction_plans,
  ai_reports,
  checkpoint_date_history,
  checkpoints,
  processing_queue,
  surveys,
  batches,
  objects
RESTART IDENTITY CASCADE;
COMMIT;
SQL

echo "Данные очищены."

if [ "$SEED" -eq 1 ]; then
  if ! docker inspect -f '{{.State.Running}}' "$API_CONTAINER" 2>/dev/null | grep -qx true; then
    echo "Контейнер $API_CONTAINER не запущен, seed пропущен" >&2
    exit 1
  fi
  docker exec "$API_CONTAINER" python scripts/seed_demo.py
  echo "Demo-данные накатили."
fi

if [ "$STORAGE" -eq 1 ]; then
  docker run --rm -v "${VOLUME}:/data" alpine:3.20 \
    sh -ec 'rm -rf /data/dronemon/raw /data/dronemon/agent_reports; mkdir -p /data/dronemon'
  echo "Хранилище raw/ и agent_reports/ очищено."
fi

echo "Готово. Вход: manager / manager, operator / operator"
