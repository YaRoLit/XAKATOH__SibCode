FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["sh", "-c", "python scripts/wait_for_db.py && i=0 && until alembic upgrade head; do i=$((i+1)); [ \"$i\" -gt 20 ] && exit 1; sleep 3; done; python scripts/seed_demo.py || true; uvicorn app.main:app --host 0.0.0.0 --port 8000"]
