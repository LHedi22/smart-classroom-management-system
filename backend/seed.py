"""
Seed script for SMU Smart Classroom Management System.
Run:  python seed.py               (from backend/ with DATABASE_URL set)
      docker compose exec backend python seed.py

Idempotent: all inserts use ON CONFLICT DO NOTHING with deterministic UUIDs.
Safe to run multiple times — will never crash or duplicate data.
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.db_models import (
    Alert,
    AlertType,
    AttendanceRecord,
    AttendanceStatus,
    Course,
    Professor,
    ProfessorRole,
    SensorReading,
    SensorType,
    Session,
    SessionStatus,
    Student,
    course_students,
)
from app.services.auth import hash_password

# ── Deterministic UUID generation ──────────────────────────────────────────
# Same input → same UUID → ON CONFLICT DO NOTHING correctly skips duplicates.
_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def uid(*parts: str) -> str:
    return str(uuid.uuid5(_NS, ":".join(parts)))


# ── Professors ────────────────────────────────────────────────────────────
# Passwords are hashed at seed time; plain-text shown only in the summary.

PROFESSORS = [
    {"email": "admin@smu.tn",       "name": "Admin",                 "role": ProfessorRole.admin,     "password": "admin123"},
    {"email": "s.trabelsi@smu.tn",  "name": "Prof. Sami Trabelsi",   "role": ProfessorRole.professor, "password": "prof123"},
    {"email": "l.chaabane@smu.tn",  "name": "Prof. Leila Chaabane",  "role": ProfessorRole.professor, "password": "prof123"},
    {"email": "m.gharbi@smu.tn",    "name": "Prof. Mohamed Gharbi",  "role": ProfessorRole.professor, "password": "prof123"},
    {"email": "i.bouaziz@smu.tn",   "name": "Prof. Ines Bouaziz",    "role": ProfessorRole.professor, "password": "prof123"},
]

# Maps course code → professor email (used to set professor_id FK on courses)
COURSE_PROFESSOR = {
    "CS301":  "s.trabelsi@smu.tn",
    "CS415":  "s.trabelsi@smu.tn",
    "CS402":  "m.gharbi@smu.tn",
    "NET301": "l.chaabane@smu.tn",
    "SE302":  "l.chaabane@smu.tn",
    "AI501":  "i.bouaziz@smu.tn",
}

# ── Courses ────────────────────────────────────────────────────────────────

COURSES = [
    ("CS301",  "Algorithms & Data Structures",  "Prof. Sami Trabelsi"),
    ("CS402",  "Operating Systems",             "Prof. Mohamed Gharbi"),
    ("CS415",  "Internet of Things",            "Prof. Sami Trabelsi"),
    ("NET301", "Computer Networks",             "Prof. Leila Chaabane"),
    ("AI501",  "Machine Learning Fundamentals", "Prof. Ines Bouaziz"),
    ("SE302",  "Software Engineering",          "Prof. Leila Chaabane"),
]

# ── Students ───────────────────────────────────────────────────────────────

STUDENT_NAMES = [
    "Yassine Trabelsi",  "Mariem Chaabane",   "Khalil Mansouri",  "Sarra Belhaj",
    "Adem Riahi",        "Nour Hammami",       "Fares Jelassi",    "Lina Khelifi",
    "Mehdi Oueslati",    "Rania Ayari",        "Tarek Ben Salem",  "Dorra Bouzid",
    "Aymen Mbarki",      "Ghofrane Saidani",   "Skander Jebali",   "Amira Dridi",
    "Houssem Laabidi",   "Salma Gharbi",       "Zied Ezzine",      "Hana Boughanmi",
    "Bilel Nasri",       "Ons Ferchichi",      "Walid Triki",      "Asma Zouari",
    "Nizar Hamrouni",    "Rim Chermiti",       "Oussama Turki",    "Fatma Boukraa",
    "Seif Saidi",        "Meriem Ben Amor",    "Hatem Souissi",    "Cyrine Mahmoud",
    "Chaker Belhaj",     "Imen Trabelsi",      "Sabrine Karray",
]

# ── Course enrollment per student (3-4 courses each) ──────────────────────
# Indices 0-20 → good attendance profile  (≈60 % of cohort)
# Indices 21-31 → average profile         (≈31 %)
# Indices 32-34 → at-risk profile         (≈9 %)  — will visibly stand out

STUDENT_COURSES = [
    ["CS301", "CS415", "NET301", "AI501"],   # 0  good  (4)
    ["CS301", "CS402", "SE302"],             # 1  good
    ["CS301", "CS415", "AI501"],             # 2  good
    ["CS402", "NET301", "SE302"],            # 3  good
    ["CS301", "CS402", "NET301"],            # 4  good
    ["CS415", "AI501", "SE302"],             # 5  good
    ["CS301", "NET301", "SE302"],            # 6  good
    ["CS402", "CS415", "AI501"],             # 7  good
    ["CS301", "CS402", "SE302"],             # 8  good
    ["CS415", "NET301", "AI501"],            # 9  good
    ["CS301", "CS402", "CS415"],             # 10 good
    ["NET301", "AI501", "SE302"],            # 11 good
    ["CS301", "CS415", "SE302"],             # 12 good
    ["CS402", "NET301", "AI501"],            # 13 good
    ["CS301", "SE302", "AI501"],             # 14 good
    ["CS402", "CS415", "NET301", "SE302"],   # 15 good  (4)
    ["CS301", "AI501", "NET301"],            # 16 good
    ["CS402", "SE302", "CS415"],             # 17 good
    ["CS301", "CS402", "AI501"],             # 18 good
    ["CS415", "NET301", "SE302"],            # 19 good
    ["CS301", "CS415", "NET301", "AI501"],   # 20 good  (4)
    ["CS402", "SE302", "NET301"],            # 21 average
    ["CS301", "AI501", "SE302"],             # 22 average
    ["CS402", "CS415", "NET301"],            # 23 average
    ["CS301", "CS402", "SE302", "AI501"],    # 24 average (4)
    ["CS415", "NET301", "AI501"],            # 25 average
    ["CS301", "SE302", "NET301"],            # 26 average
    ["CS402", "CS415", "AI501", "SE302"],    # 27 average (4)
    ["CS301", "NET301", "SE302"],            # 28 average
    ["CS402", "AI501", "CS415"],             # 29 average
    ["CS301", "CS402", "NET301", "SE302"],   # 30 average (4)
    ["CS415", "AI501", "SE302"],             # 31 average
    ["CS301", "NET301", "AI501"],            # 32 at-risk
    ["CS402", "CS415", "SE302"],             # 33 at-risk
    ["CS301", "AI501", "NET301", "SE302"],   # 34 at-risk (4)
]

# ── Session schedule ────────────────────────────────────────────────────────
# (course_code, weeks_ago, weekday 0=Mon…4=Fri, start_hour, start_min, dur_min)
# All sessions end before 18:30 Tunis time; all dates land in the past.

SESSION_SPECS = [
    # CS301 — Monday 08:00–09:30
    ("CS301",  8, 0,  8,  0, 90),
    ("CS301",  7, 0,  8,  0, 90),
    ("CS301",  5, 0,  8,  0, 90),
    ("CS301",  4, 0,  8,  0, 90),
    ("CS301",  2, 0,  8,  0, 90),
    # CS402 — Tuesday 09:45–11:15
    ("CS402",  8, 1,  9, 45, 90),
    ("CS402",  7, 1,  9, 45, 90),
    ("CS402",  5, 1,  9, 45, 90),
    ("CS402",  3, 1,  9, 45, 90),
    ("CS402",  2, 1,  9, 45, 90),
    # CS415 — Wednesday 11:30–13:00
    ("CS415",  8, 2, 11, 30, 90),
    ("CS415",  6, 2, 11, 30, 90),
    ("CS415",  5, 2, 11, 30, 90),
    ("CS415",  3, 2, 11, 30, 90),
    ("CS415",  1, 2, 11, 30, 90),
    # NET301 — Thursday 14:00–15:30
    ("NET301", 8, 3, 14,  0, 90),
    ("NET301", 7, 3, 14,  0, 90),
    ("NET301", 5, 3, 14,  0, 90),
    ("NET301", 3, 3, 14,  0, 90),
    ("NET301", 2, 3, 14,  0, 90),
    # AI501 — Friday 15:45–17:15
    ("AI501",  8, 4, 15, 45, 90),
    ("AI501",  6, 4, 15, 45, 90),
    ("AI501",  5, 4, 15, 45, 90),
    ("AI501",  3, 4, 15, 45, 90),
    ("AI501",  1, 4, 15, 45, 90),
    # SE302 — Monday 16:00–17:30
    ("SE302",  7, 0, 16,  0, 90),
    ("SE302",  6, 0, 16,  0, 90),
    ("SE302",  4, 0, 16,  0, 90),
    ("SE302",  3, 0, 16,  0, 90),
    ("SE302",  1, 0, 16,  0, 90),
]

# ── Alert definitions ───────────────────────────────────────────────────────
# (type, float_value_or_None, message, acknowledged, days_ago)
# 5 acknowledged, 3 unacknowledged.

ALERT_SPECS = [
    (AlertType.temp_high,         33.2, "Temperature exceeded threshold: 33.2°C in room1",                          True,  26),
    (AlertType.temp_high,         31.8, "Temperature exceeded threshold: 31.8°C in room1",                          True,  19),
    (AlertType.temp_high,         34.1, "Temperature exceeded threshold: 34.1°C in room1",                          False,  7),
    (AlertType.air_quality_high, 542.0, "Air quality alert: 542 ppm in room1 — check ventilation",                  True,  22),
    (AlertType.air_quality_high, 578.0, "Air quality alert: 578 ppm in room1 — check ventilation",                  False, 11),
    (AlertType.attendance_anomaly, None, "Attendance anomaly: unrecognized faces detected during session in room1",  True,  15),
    (AlertType.attendance_anomaly, None, "Attendance anomaly: 4 unrecognized faces — potential unauthorized access", False,  4),
    (AlertType.device_offline,    None, "ESP32 node offline — no heartbeat received from room1 for 5 minutes",      True,  18),
]


# ── Helpers ────────────────────────────────────────────────────────────────

def _session_dt(weeks_ago: int, weekday: int, hour: int, minute: int) -> datetime:
    """Return a past datetime in Tunis time (UTC+1) computed relative to now."""
    today = datetime.now(timezone.utc).date()
    this_monday = today - timedelta(days=today.weekday())
    target = this_monday - timedelta(weeks=weeks_ago) + timedelta(days=weekday)
    tunis = timezone(timedelta(hours=1))
    return datetime(target.year, target.month, target.day, hour, minute, tzinfo=tunis)


def _pick_status(profile: str, rng: random.Random) -> AttendanceStatus:
    r = rng.random()
    if profile == "good":
        # 90 % present, 6 % absent, 4 % late
        if r < 0.90: return AttendanceStatus.present
        if r < 0.96: return AttendanceStatus.absent
        return AttendanceStatus.late
    if profile == "average":
        # 73 % present, 18 % absent, 9 % late
        if r < 0.73: return AttendanceStatus.present
        if r < 0.91: return AttendanceStatus.absent
        return AttendanceStatus.late
    # at_risk: 50 % present, 40 % absent, 10 % late
    if r < 0.50: return AttendanceStatus.present
    if r < 0.90: return AttendanceStatus.absent
    return AttendanceStatus.late


# ── Seed ───────────────────────────────────────────────────────────────────

def _run_migrations() -> None:
    """Apply all pending Alembic migrations using the Python API."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    # Override the URL from settings so the env var takes precedence over alembic.ini
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    print("✅ Migrations applied")


async def seed() -> None:
    rng = random.Random(42)  # fixed seed → deterministic attendance distribution

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    AsyncDB = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncDB() as db:

        # ── 0. Professors ──────────────────────────────────────────────────
        # hash_password uses bcrypt — takes ~0.3 s per call, acceptable here
        professor_rows = [
            {
                "id": uid("professor", p["email"]),
                "name": p["name"],
                "email": p["email"],
                "hashed_password": hash_password(p["password"]),
                "role": p["role"],
            }
            for p in PROFESSORS
        ]
        await db.execute(
            pg_insert(Professor).values(professor_rows).on_conflict_do_nothing(index_elements=["email"])
        )

        # ── 1. Courses ─────────────────────────────────────────────────────
        course_rows = [
            {"id": uid("course", code), "code": code, "name": name, "professor_name": prof}
            for code, name, prof in COURSES
        ]
        await db.execute(
            pg_insert(Course).values(course_rows).on_conflict_do_nothing(index_elements=["code"])
        )
        cid = {code: uid("course", code) for code, _, _ in COURSES}

        # Link each course to its professor (idempotent UPDATE)
        for code, email in COURSE_PROFESSOR.items():
            await db.execute(
                update(Course)
                .where(Course.code == code)
                .values(professor_id=uid("professor", email))
            )

        # ── 2. Students ────────────────────────────────────────────────────
        smu_keys = [f"SMU2023{i + 1:04d}" for i in range(len(STUDENT_NAMES))]
        student_rows = [
            {"id": uid("student", k), "name": name, "student_id": k}
            for k, name in zip(smu_keys, STUDENT_NAMES)
        ]
        await db.execute(
            pg_insert(Student).values(student_rows).on_conflict_do_nothing(index_elements=["student_id"])
        )
        sid_map = {k: uid("student", k) for k in smu_keys}

        # ── 3. Course enrollments ──────────────────────────────────────────
        enrollment_rows = [
            {"course_id": cid[code], "student_id": sid_map[smu_keys[i]]}
            for i, courses in enumerate(STUDENT_COURSES)
            for code in courses
        ]
        await db.execute(
            pg_insert(course_students).values(enrollment_rows).on_conflict_do_nothing()
        )

        # ── 4. Sessions ────────────────────────────────────────────────────
        session_rows = []
        sessions_by_course: dict[str, list[tuple[int, datetime, datetime]]] = {}

        for spec_idx, (code, w, wday, hr, mn, dur) in enumerate(SESSION_SPECS):
            s_id = uid("session", code, str(spec_idx))
            started = _session_dt(w, wday, hr, mn)
            ended = started + timedelta(minutes=dur)
            session_rows.append({
                "id": s_id,
                "course_id": cid[code],
                "room_id": "room1",
                "started_at": started,
                "ended_at": ended,
                "status": SessionStatus.ended,
            })
            sessions_by_course.setdefault(code, []).append((spec_idx, started, ended))

        await db.execute(
            pg_insert(Session).values(session_rows).on_conflict_do_nothing(index_elements=["id"])
        )

        # ── 5. Attendance records ──────────────────────────────────────────
        profiles = ["good"] * 21 + ["average"] * 11 + ["at_risk"] * 3

        attendance_rows = []
        for i, (smu_key, course_list) in enumerate(zip(smu_keys, STUDENT_COURSES)):
            profile = profiles[i]
            stu_id = sid_map[smu_key]
            for code in course_list:
                for spec_idx, s_start, _s_end in sessions_by_course[code]:
                    s_id = uid("session", code, str(spec_idx))
                    status = _pick_status(profile, rng)
                    if status == AttendanceStatus.present:
                        detected = s_start + timedelta(minutes=rng.randint(0, 12))
                    elif status == AttendanceStatus.late:
                        detected = s_start + timedelta(minutes=rng.randint(20, 50))
                    else:  # absent — no detection; store session start as placeholder
                        detected = s_start
                    attendance_rows.append({
                        "id": uid("attendance", s_id, stu_id),
                        "session_id": s_id,
                        "student_id": stu_id,
                        "status": status,
                        "detected_at": detected,
                        "adjusted_by": None,
                        "adjusted_at": None,
                        "moodle_synced": False,
                    })

        await db.execute(
            pg_insert(AttendanceRecord).values(attendance_rows).on_conflict_do_nothing(index_elements=["id"])
        )

        # ── 6. Alerts ──────────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        alert_rows = [
            {
                "id": uid("alert", str(idx)),
                "room_id": "room1",
                "type": a_type,
                "value": value,
                "message": msg,
                "acknowledged": ack,
                "created_at": now - timedelta(days=d),
            }
            for idx, (a_type, value, msg, ack, d) in enumerate(ALERT_SPECS)
        ]
        await db.execute(
            pg_insert(Alert).values(alert_rows).on_conflict_do_nothing(index_elements=["id"])
        )

        # ── 7. Phase-16 sessions: live + upcoming + sensor readings ──────────
        now = datetime.now(timezone.utc)

        # ── 7a. Live session (CS415 / Trabelsi, always 30 min ago relative to now)
        # ON CONFLICT DO UPDATE ensures started_at refreshes every seed run so the
        # session is always "live" regardless of when the seed was last executed.
        live_id      = uid("session", "phase16", "live")
        live_started = now - timedelta(minutes=30)
        live_ended   = now + timedelta(minutes=60)
        await db.execute(
            pg_insert(Session).values([{
                "id":         live_id,
                "course_id":  cid["CS415"],
                "room_id":    "room1",
                "started_at": live_started,
                "ended_at":   live_ended,
                "status":     SessionStatus.active,
            }]).on_conflict_do_update(
                index_elements=["id"],
                set_={"started_at": live_started, "ended_at": live_ended, "status": SessionStatus.active},
            )
        )

        # ── 7b. Upcoming sessions ─────────────────────────────────────────────
        for code, u_start, u_end in [
            ("CS301", now + timedelta(hours=2),  now + timedelta(hours=3, minutes=30)),
            ("NET301", now + timedelta(days=1),  now + timedelta(days=1, hours=1, minutes=30)),
        ]:
            await db.execute(
                pg_insert(Session).values([{
                    "id":         uid("session", "phase16", "upcoming", code),
                    "course_id":  cid[code],
                    "room_id":    "room1",
                    "started_at": u_start,
                    "ended_at":   u_end,
                    "status":     SessionStatus.upcoming,
                }]).on_conflict_do_nothing(index_elements=["id"])
            )

        # ── 7c. Sensor readings ───────────────────────────────────────────────
        # Generate 5-minute-interval readings for every seeded session so the
        # sensors summary tab has data for ALL done sessions, not just one.
        # Live session readings use ON CONFLICT DO UPDATE to stay anchored to the
        # current "now" — otherwise a second seed run would leave them in the past.

        def _sensor_reading(tag: str, stype: SensorType, offset_min: int, ts: datetime) -> dict:
            if stype == SensorType.temperature:
                val = round(22.5 + 4.0 * rng.random() + rng.uniform(-0.4, 0.4), 1)
                unit = "C"
            elif stype == SensorType.humidity:
                val = round(48.0 + 18.0 * rng.random() + rng.uniform(-1.5, 1.5), 1)
                unit = "%"
            elif stype == SensorType.air_quality:
                val = round(240 + 180 * rng.random() + rng.uniform(-15, 15), 0)
                unit = "ppm"
            else:  # sound
                val = 1.0 if rng.random() < 0.72 else 0.0
                unit = "bool"
            return {
                "id":          uid("sensor", tag, stype.value, str(offset_min)),
                "room_id":     "room1",
                "sensor_type": stype,
                "value":       val,
                "unit":        unit,
                "recorded_at": ts,
            }

        # ── Done sessions: seed readings for every session in SESSION_SPECS ──
        static_rows: list[dict] = []
        for spec_idx, (code, w, wday, hr, mn, dur) in enumerate(SESSION_SPECS):
            s_start = _session_dt(w, wday, hr, mn)
            for offset in range(0, dur + 1, 5):
                ts = s_start + timedelta(minutes=offset)
                tag = f"done:{code}:{spec_idx}"
                for stype in SensorType:
                    static_rows.append(_sensor_reading(tag, stype, offset, ts))

        if static_rows:
            await db.execute(
                pg_insert(SensorReading).values(static_rows).on_conflict_do_nothing(index_elements=["id"])
            )

        # ── Live session: fresh readings anchored to current now ─────────────
        live_rows: list[dict] = []
        for minutes_ago in range(30, -1, -5):
            ts = now - timedelta(minutes=minutes_ago)
            for stype in SensorType:
                live_rows.append(_sensor_reading(f"live:{minutes_ago}", stype, minutes_ago, ts))

        if live_rows:
            # DO UPDATE so timestamps stay correct even when seed runs twice
            await db.execute(
                pg_insert(SensorReading).values(live_rows).on_conflict_do_update(
                    index_elements=["id"],
                    set_={"value": pg_insert(SensorReading).excluded.value, "recorded_at": pg_insert(SensorReading).excluded.recorded_at},
                )
            )

        await db.commit()

    await engine.dispose()

    print("✅ Seed complete")
    print(f"   Students  : {len(STUDENT_NAMES)}")
    print(f"   Courses   : {len(COURSES)}")
    print(f"   Sessions  : {len(SESSION_SPECS)}")
    print(f"   Attendance: {len(attendance_rows)}")
    print(f"   Alerts    : {len(ALERT_SPECS)}")
    print()
    print("👤 Accounts seeded:")
    for p in PROFESSORS:
        role_label = p["role"].value
        print(f"   {p['email']:<28} / {p['password']:<10} ({role_label})")


if __name__ == "__main__":
    _run_migrations()   # synchronous — must run before asyncio.run() starts a loop
    asyncio.run(seed())
