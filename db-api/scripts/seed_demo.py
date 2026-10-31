"""Демонстрационные данные. Повторный запуск удаляет только строки с is_demo=true."""
import asyncio
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.models import (
    AiReport,
    Batch,
    Checkpoint,
    CheckpointDateHistory,
    Object,
    ProblemAction,
    ProblemAlert,
    Survey,
    User,
)
from app.db.session import SessionLocal
from app.services.checkpoints import CHECKPOINT_DEFS, distribute_dates

TODAY = date.today()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


DEMO_OBJECTS = [
    {
        "id": "obj_demo_01",
        "name": "Коттедж «Берёзовая»",
        "cadastral_number": "54:35:091245:701",
        "address": "Новосибирская обл., Новосибирский район, ул. Берёзовая, уч. 12",
        "material": "кирпич",
        "credit": TODAY - timedelta(days=180),
        "plan": TODAY + timedelta(days=90),
        "corners": [
            {"lat": 54.98010, "lon": 82.89710},
            {"lat": 54.98018, "lon": 82.89740},
            {"lat": 54.97995, "lon": 82.89748},
            {"lat": 54.97988, "lon": 82.89718},
        ],
        "force_overdue": True,
        "report": {
            "overall_readiness_pct": 48,
            "overall_status": "red",
            "stages": [
                {"name": "Фундамент", "readiness_pct": 95, "status": "green"},
                {"name": "Стены", "readiness_pct": 40, "status": "red"},
                {"name": "Крыша", "readiness_pct": 0, "status": "red"},
            ],
            "comments": ["Кладка восточной стены отстаёт от графика"],
            "problems": [
                {
                    "code": "WALL_LAG",
                    "severity": "red",
                    "title": "Отставание по стенам",
                    "description": "Фактическая готовность стен около 40% при плановых 75%.",
                }
            ],
        },
        "alert_status": "new",
    },
    {
        "id": "obj_demo_02",
        "name": "Дом на Обской",
        "cadastral_number": "54:35:091245:702",
        "address": "Новосибирск, ул. Обская, 48",
        "material": "газобетон",
        "credit": TODAY - timedelta(days=120),
        "plan": TODAY + timedelta(days=60),
        "corners": [
            {"lat": 55.02110, "lon": 82.92110},
            {"lat": 55.02120, "lon": 82.92140},
            {"lat": 55.02100, "lon": 82.92150},
            {"lat": 55.02090, "lon": 82.92120},
        ],
        "complete_first": True,
        "report": {
            "overall_readiness_pct": 72,
            "overall_status": "yellow",
            "stages": [
                {"name": "Фундамент", "readiness_pct": 100, "status": "green"},
                {"name": "Стены", "readiness_pct": 80, "status": "green"},
                {"name": "Крыша", "readiness_pct": 20, "status": "yellow"},
            ],
            "comments": ["Фундамент принят, стены в графике"],
            "problems": [
                {
                    "code": "ROOF_START",
                    "severity": "yellow",
                    "title": "Крыша не начата",
                    "description": "На снимках нет конструкций кровли.",
                }
            ],
        },
        "alert_status": "in_progress",
        "alert_comment": "Запросили уточнение у подрядчика.",
    },
    {
        "id": "obj_demo_03",
        "name": "Таунхаус «Академ»",
        "cadastral_number": "54:35:061100:118",
        "address": "Новосибирск, Советский район, ул. Иванова, 15",
        "material": "каркас",
        "credit": TODAY - timedelta(days=30),
        "plan": TODAY + timedelta(days=150),
        "corners": [
            {"lat": 54.84310, "lon": 83.09610},
            {"lat": 54.84320, "lon": 83.09640},
            {"lat": 54.84300, "lon": 83.09650},
            {"lat": 54.84290, "lon": 83.09620},
        ],
    },
    {
        "id": "obj_demo_04",
        "name": "Коттедж у моря Обского",
        "cadastral_number": "54:19:150301:44",
        "address": "Новосибирская обл., Бердск, ул. Речная, 7",
        "material": "дерево",
        "credit": TODAY - timedelta(days=200),
        "plan": TODAY - timedelta(days=5),
        "corners": [
            {"lat": 54.75810, "lon": 83.09610},
            {"lat": 54.75822, "lon": 83.09645},
            {"lat": 54.75800, "lon": 83.09655},
            {"lat": 54.75790, "lon": 83.09620},
        ],
        "complete_all_but_last": True,
        "report": {
            "overall_readiness_pct": 91,
            "overall_status": "green",
            "stages": [
                {"name": "Фундамент", "readiness_pct": 100, "status": "green"},
                {"name": "Стены", "readiness_pct": 100, "status": "green"},
                {"name": "Крыша", "readiness_pct": 95, "status": "green"},
            ],
            "comments": ["Объект почти готов"],
            "problems": [],
        },
    },
    {
        "id": "obj_demo_05",
        "name": "Дом в Кольцово",
        "cadastral_number": "54:19:034501:209",
        "address": "Новосибирская обл., рп Кольцово, ул. Технопарковая, 3",
        "material": "кирпич",
        "credit": TODAY - timedelta(days=10),
        "plan": TODAY + timedelta(days=200),
        "corners": [
            {"lat": 54.94010, "lon": 83.18610},
            {"lat": 54.94022, "lon": 83.18640},
            {"lat": 54.94000, "lon": 83.18650},
            {"lat": 54.93990, "lon": 83.18620},
        ],
    },
    {
        "id": "obj_demo_06",
        "name": "Участок «Сосновая поляна»",
        "cadastral_number": "54:35:000000:880",
        "address": "Новосибирская обл., Мочище, ул. Сосновая, 2",
        "material": "газобетон",
        "credit": TODAY - timedelta(days=90),
        "plan": TODAY + timedelta(days=3),
        "corners": [
            {"lat": 55.16010, "lon": 82.76010},
            {"lat": 55.16020, "lon": 82.76040},
            {"lat": 55.16000, "lon": 82.76050},
            {"lat": 55.15990, "lon": 82.76020},
        ],
        "report": {
            "overall_readiness_pct": 88,
            "overall_status": "yellow",
            "stages": [
                {"name": "Фундамент", "readiness_pct": 100, "status": "green"},
                {"name": "Стены", "readiness_pct": 100, "status": "green"},
                {"name": "Крыша", "readiness_pct": 70, "status": "yellow"},
            ],
            "comments": ["На части снимков кровля закрыта не полностью"],
            "problems": [
                {
                    "code": "ROOF_GAP",
                    "severity": "yellow",
                    "title": "Пробел покрытия крыши",
                    "description": "Северо-западный скат не закрыт кровельным материалом.",
                }
            ],
        },
        "alert_status": "resolved",
        "alert_comment": "Подрядчик закрыл скат, повторная съёмка не требуется.",
    },
]


async def _ensure_users(session):
    for user_id, login, role, name in (
        ("user_manager", "manager", "manager", "Анна Кредитова"),
        ("user_operator", "operator", "operator", "Игорь Пилотов"),
    ):
        user = await session.get(User, user_id)
        if user is None:
            session.add(
                User(
                    id=user_id,
                    login=login,
                    password_hash=hash_password(login),
                    role=role,
                    display_name=name,
                    is_demo=True,
                )
            )


async def _wipe_demo(session):
    demo_ids = [row["id"] for row in DEMO_OBJECTS]
    alert_ids = list(
        (await session.execute(select(ProblemAlert.id).where(ProblemAlert.is_demo.is_(True)))).scalars()
    )
    if alert_ids:
        await session.execute(delete(ProblemAction).where(ProblemAction.alert_id.in_(alert_ids)))
    await session.execute(delete(ProblemAlert).where(ProblemAlert.is_demo.is_(True)))
    await session.execute(delete(AiReport).where(AiReport.is_demo.is_(True)))
    cp_ids = list(
        (await session.execute(select(Checkpoint.id).where(Checkpoint.object_id.in_(demo_ids)))).scalars()
    )
    if cp_ids:
        await session.execute(delete(CheckpointDateHistory).where(CheckpointDateHistory.checkpoint_id.in_(cp_ids)))
        await session.execute(delete(Checkpoint).where(Checkpoint.id.in_(cp_ids)))
    await session.execute(delete(Survey).where(Survey.batch_id == "batch_demo"))
    await session.execute(delete(Batch).where(Batch.id == "batch_demo"))
    await session.execute(delete(Object).where(Object.id.in_(demo_ids)))
    await session.flush()


async def _backfill_legacy(session):
    """Существующие obj_123/obj_124 дополняем полями менеджера, не помечая как demo."""
    for obj_id, name, material in (
        ("obj_123", "Тестовый участок Новосибирск", "кирпич"),
        ("obj_124", "Соседний тестовый участок", "газобетон"),
    ):
        obj = await session.get(Object, obj_id)
        if obj is None:
            continue
        obj.name = obj.name or name
        obj.material = obj.material or material
        obj.credit_issued_at = obj.credit_issued_at or (TODAY - timedelta(days=60))
        obj.planned_completion_at = obj.planned_completion_at or (TODAY + timedelta(days=120))
        existing = (
            await session.execute(select(Checkpoint.id).where(Checkpoint.object_id == obj.id))
        ).first()
        if existing is None and obj.credit_issued_at and obj.planned_completion_at:
            dates = distribute_dates(obj.credit_issued_at, obj.planned_completion_at)
            for order, ((title, readiness), planned) in enumerate(zip(CHECKPOINT_DEFS, dates, strict=True)):
                session.add(
                    Checkpoint(
                        id=_id("cp"),
                        object_id=obj.id,
                        title=title,
                        planned_date=planned,
                        expected_readiness=readiness,
                        sort_order=order,
                    )
                )


async def run() -> None:
    async with SessionLocal() as session:
        await _ensure_users(session)
        await _wipe_demo(session)
        await _backfill_legacy(session)

        session.add(Batch(id="batch_demo", operator_id="user_operator", status="confirmed"))
        survey_n = 1

        for spec in DEMO_OBJECTS:
            obj = Object(
                id=spec["id"],
                name=spec["name"],
                cadastral_number=spec["cadastral_number"],
                address=spec["address"],
                plot_corners=spec["corners"],
                status="active",
                material=spec["material"],
                credit_issued_at=spec["credit"],
                planned_completion_at=spec["plan"],
                is_demo=True,
            )
            session.add(obj)
            await session.flush()
            dates = distribute_dates(spec["credit"], spec["plan"])
            if spec.get("force_overdue"):
                dates[0] = TODAY - timedelta(days=10)
            cps = []
            for order, ((title, readiness), planned) in enumerate(zip(CHECKPOINT_DEFS, dates, strict=True)):
                cp = Checkpoint(
                    id=f"cp_{spec['id']}_{order}",
                    object_id=obj.id,
                    title=title,
                    planned_date=planned,
                    expected_readiness=readiness,
                    sort_order=order,
                )
                session.add(cp)
                cps.append(cp)
            await session.flush()

            complete_until = -1
            if spec.get("complete_first"):
                complete_until = 0
            if spec.get("complete_all_but_last"):
                complete_until = 2
            for idx, cp in enumerate(cps):
                if idx <= complete_until:
                    session.add(
                        Survey(
                            batch_id="batch_demo",
                            filename=f"{obj.id}_{cp.title}.jpg",
                            status="validated",
                            object_id=obj.id,
                            coverage=0.92,
                            validation_errors=[],
                            s3_key=f"raw/{obj.id}/batch_demo/{obj.id}_{idx}.jpg",
                        )
                    )
                    survey_n += 1

            if spec.get("report"):
                report = AiReport(
                    id=f"rep_{spec['id']}",
                    object_id=obj.id,
                    checkpoint_id=cps[0].id,
                    agent_run_id=f"demo-run-{spec['id']}",
                    raw_json=spec["report"],
                    is_demo=True,
                )
                session.add(report)
                await session.flush()
                for item in spec["report"].get("problems") or []:
                    alert = ProblemAlert(
                        id=f"al_{spec['id']}_{item.get('code', 'x')}",
                        object_id=obj.id,
                        report_id=report.id,
                        title=item["title"],
                        summary=item.get("description"),
                        severity=item.get("severity"),
                        status=spec.get("alert_status", "new"),
                        raw_item=item,
                        is_demo=True,
                    )
                    session.add(alert)
                    await session.flush()
                    if spec.get("alert_comment"):
                        session.add(
                            ProblemAction(
                                alert_id=alert.id,
                                actor_id="user_manager",
                                action="status_change",
                                comment=spec["alert_comment"],
                            )
                        )

        session.add(
            Survey(
                batch_id="batch_demo",
                filename="rejected_blur.jpg",
                status="rejected",
                object_id="obj_demo_03",
                validation_errors=["Размытое изображение (blur score 12.0 < 100.0)"],
            )
        )
        session.add(
            Survey(
                batch_id="batch_demo",
                filename="rejected_gps.jpg",
                status="rejected",
                validation_errors=["Объект не найден по координатам съемки"],
            )
        )

        await session.commit()
        print("demo seed: ok (is_demo=true only)")


if __name__ == "__main__":
    asyncio.run(run())
