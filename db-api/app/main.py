from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import alerts, auth, checkpoints, dashboard, objects, operator
from app.config import settings

app = FastAPI(title="SibCode DB API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(objects.router)
app.include_router(checkpoints.router)
app.include_router(dashboard.router)
app.include_router(alerts.router)
app.include_router(operator.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
