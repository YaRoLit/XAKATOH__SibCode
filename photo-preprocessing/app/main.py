from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends

from app.api.routes import batches, health, surveys
from app.core.logging import get_logger
from app.db import repositories as repo
from app.db.session import SessionLocal
from app.services import storage
from app.workers import validation_worker
from app.api.deps import check_auth
import asyncio

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.ensure_bucket()
    async with SessionLocal() as session:
        for batch in await repo.processing_batches(session):
            log.debug("startup: resuming batch %s", batch.id)
            asyncio.create_task(validation_worker.run_validation(batch.id))
    yield


app = FastAPI(
    title="Photo Preprocessing Service", 
    lifespan=lifespan,
    root_path="/drones",          # Говорит Swagger UI генерировать ссылки с /drones/
    docs_url="/docs",             # Слушает запрос, который пришел от Nginx (уже без префикса)
    openapi_url="/openapi.json",  # Слушает запрос, который пришел от Nginx (уже без префикса)
    redoc_url="/redoc",
)

app.include_router(health.router)

batches.router.dependencies.append(Depends(check_auth))
surveys.router.dependencies.append(Depends(check_auth))

app.include_router(batches.router)
app.include_router(surveys.router)