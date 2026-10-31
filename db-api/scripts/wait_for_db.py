import os
import socket
import time
from urllib.parse import urlparse

dsn = os.getenv("DB_DSN", "postgresql+asyncpg://admin:secret@db:5432/dronemon")
parsed = urlparse(dsn)
host, port = parsed.hostname, parsed.port or 5432

for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"db {host}:{port} is ready")
            raise SystemExit(0)
    except OSError:
        time.sleep(2)
raise SystemExit(f"db {host}:{port} not available after 120s")
