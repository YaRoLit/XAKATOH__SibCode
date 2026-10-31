from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AgentBase, AnalysisReport, ConstructionPlan
from app.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def init_db() -> None:
    AgentBase.metadata.create_all(engine, tables=[ConstructionPlan.__table__, AnalysisReport.__table__])
