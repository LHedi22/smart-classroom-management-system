import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, attendance, control, courses, enrollment, sensors, sessions, websocket
from app.models.schemas import HealthResponse, MoodleConnectionStatus
from app.redis_client import close_redis, get_redis_pool
from app.services.alert_engine import alert_engine
from app.services.mqtt_bridge import start_mqtt_bridge, stop_mqtt_bridge

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# ─────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────

async def _drain_queue(queue: asyncio.Queue) -> None:
    """Consume events from a queue and broadcast to WebSocket clients."""
    from app.api.websocket import connection_manager
    while True:
        event: dict = await queue.get()
        room_id = event.get("room_id")
        try:
            if room_id:
                await connection_manager.broadcast(room_id, event)
            else:
                await connection_manager.broadcast_all(event)
        except Exception as exc:
            logger.warning("Broadcast error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.event_queues import alert_event_queue, attendance_event_queue, sensor_event_queue

    # Startup
    _run_migrations()
    await start_mqtt_bridge()
    alert_engine.start()
    broadcaster_tasks = [
        asyncio.create_task(_drain_queue(sensor_event_queue),    name="sensor_broadcaster"),
        asyncio.create_task(_drain_queue(attendance_event_queue), name="attendance_broadcaster"),
        asyncio.create_task(_drain_queue(alert_event_queue),      name="alert_broadcaster"),
    ]
    yield
    # Shutdown
    for task in broadcaster_tasks:
        task.cancel()
    alert_engine.stop()
    await stop_mqtt_bridge()
    await close_redis()
    from app.services.moodle_client import moodle_client
    await moodle_client.close()


def _run_migrations() -> None:
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).parent.parent
    # Prefer the installed alembic CLI binary over python -m (avoids local dir shadowing)
    alembic_bin = shutil.which("alembic") or str(Path(sys.executable).parent / "alembic")
    try:
        result = subprocess.run(
            [alembic_bin, "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info("Alembic migrations applied")
        else:
            logger.warning("Alembic migration failed: %s", result.stderr.strip())
    except Exception as exc:
        logger.warning("Alembic migration failed (DB may not be available): %s", exc)


# ─────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart Classroom API",
    description="IoT-based smart classroom management system — SMU MedTech",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(sensors.router,    prefix="/api/sensors",    tags=["sensors"])
app.include_router(courses.router,    prefix="/api/courses",    tags=["courses"])
app.include_router(sessions.router,   prefix="/api/sessions",   tags=["sessions"])
app.include_router(attendance.router, prefix="/api",            tags=["attendance"])
app.include_router(control.router,    prefix="/api/control",    tags=["control"])
app.include_router(enrollment.router, prefix="/api",            tags=["enrollment"])
app.include_router(alerts.router,     prefix="/api/alerts",     tags=["alerts"])
app.include_router(websocket.router,  prefix="/ws",             tags=["websocket"])


# ─────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    redis_ok = False
    db_ok = False

    try:
        r = get_redis_pool()
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    try:
        from sqlalchemy import text
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    return HealthResponse(status="ok", redis=redis_ok, db=db_ok)


@app.get("/api/moodle-test", response_model=MoodleConnectionStatus, tags=["moodle"])
async def moodle_test() -> MoodleConnectionStatus:
    from app.services.moodle_client import moodle_client
    connected = await moodle_client.test_connection()
    return MoodleConnectionStatus(connected=connected, moodle_url=settings.moodle_url)
