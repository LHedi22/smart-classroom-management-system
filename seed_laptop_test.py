#!/usr/bin/env python3
"""
Seed the laptop-mode live test course.

Creates: demo professor, course DEMO-LAP-001, 7 students, 1 active session.
Idempotent — safe to run multiple times.

Usage:
    docker compose exec backend python seed_laptop_test.py
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone

from passlib.context import CryptContext
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://smartcam:smartcam@postgres:5432/smartclassroom",
)
ROOM_ID = os.getenv("ROOM_ID", "room1")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

STUDENTS = [
    ("Mohamed Hedi Ben Jemaa", "STU-DEMO-001"),
    ("Ahmed Amine Jallouli",   "STU-DEMO-002"),
    ("Abdelhamid Ouertani",    "STU-DEMO-003"),
    ("Ali Saadaoui",           "STU-DEMO-004"),
    ("Iyed Dai",               "STU-DEMO-005"),
    ("Donia Driss",            "STU-DEMO-006"),
    ("Lamia Bouaziz",          "STU-DEMO-007"),
]


async def main() -> None:
    from app.models.db_models import (
        Course,
        Professor,
        ProfessorRole,
        Session as SessionModel,
        SessionStatus,
        Student,
    )

    async with AsyncSessionLocal() as db:

        # ── Professor ──────────────────────────────────────────────────────────
        prof = (
            await db.execute(select(Professor).where(Professor.email == "demo@smu.tn"))
        ).scalar_one_or_none()

        if prof is None:
            prof = Professor(
                id=str(uuid.uuid4()),
                name="Demo Professor",
                email="demo@smu.tn",
                hashed_password=pwd_context.hash("demo1234"),
                role=ProfessorRole.professor,
            )
            db.add(prof)
            await db.flush()
            print("✓ Created professor: demo@smu.tn")
        else:
            print("· Professor demo@smu.tn already exists")

        # ── Course ─────────────────────────────────────────────────────────────
        course = (
            await db.execute(select(Course).where(Course.code == "DEMO-LAP-001"))
        ).scalar_one_or_none()

        if course is None:
            course = Course(
                id=str(uuid.uuid4()),
                code="DEMO-LAP-001",
                name="Automated Attendance Realtime Testing",
                professor_name="Demo Professor",
                professor_id=prof.id,
            )
            db.add(course)
            await db.flush()
            print("✓ Created course: DEMO-LAP-001")
        else:
            print("· Course DEMO-LAP-001 already exists")

        # ── Students + enrollments ─────────────────────────────────────────────
        student_objects: list[Student] = []
        for name, sid in STUDENTS:
            student = (
                await db.execute(select(Student).where(Student.student_id == sid))
            ).scalar_one_or_none()

            if student is None:
                student = Student(id=str(uuid.uuid4()), name=name, student_id=sid)
                db.add(student)
                await db.flush()
                print(f"✓ Created student: {name} ({sid})")
            else:
                print(f"· Student {sid} already exists")

            student_objects.append(student)

        # Enroll all students — INSERT IGNORE pattern via raw SQL
        for student in student_objects:
            await db.execute(
                text(
                    "INSERT INTO course_students (course_id, student_id) "
                    "VALUES (:cid, :sid) ON CONFLICT DO NOTHING"
                ).bindparams(cid=course.id, sid=student.id)
            )
        print(f"✓ Enrolled {len(student_objects)} students in DEMO-LAP-001")

        # ── Session ────────────────────────────────────────────────────────────
        active_session = (
            await db.execute(
                select(SessionModel).where(
                    SessionModel.course_id == course.id,
                    SessionModel.status == SessionStatus.active,
                )
            )
        ).scalar_one_or_none()

        if active_session is None:
            active_session = SessionModel(
                id=str(uuid.uuid4()),
                course_id=course.id,
                room_id=ROOM_ID,
                started_at=datetime.now(timezone.utc),
                status=SessionStatus.active,
            )
            db.add(active_session)
            await db.flush()
            print(f"✓ Created active session: {active_session.id}")
        else:
            print(f"· Active session already exists: {active_session.id}")

        session_id = str(active_session.id)
        await db.commit()

    print(f"""
═══════════════════════════════════════════════
  LAPTOP MODE LIVE TEST — SETUP COMPLETE
═══════════════════════════════════════════════
  Course  : DEMO-LAP-001 — Automated Attendance Realtime Testing
  Session : {session_id}  [ACTIVE]
  Students: 7 enrolled
  Login   : demo@smu.tn / demo1234

  NEXT STEPS
  ──────────
  1. Place one photo per student in enrollment_photos/:
       enrollment_photos/STU-DEMO-001.jpg   (Mohamed Hedi Ben Jemaa)
       enrollment_photos/STU-DEMO-002.jpg   (Ahmed Amine Jallouli)
       enrollment_photos/STU-DEMO-003.jpg   (Abdelhamid Ouertani)
       enrollment_photos/STU-DEMO-004.jpg   (Ali Saadaoui)
       enrollment_photos/STU-DEMO-005.jpg   (Iyed Dai)
       enrollment_photos/STU-DEMO-006.jpg   (Donia Driss)
       enrollment_photos/STU-DEMO-007.jpg   (Lamia Bouaziz)

  2. Run enrollment:
       python enroll_demo_students.py

  3. In firmware/classroom_node/config.h set MQTT_HOST to your laptop's LAN IP, reflash.

  4. Start the stack:
       LAPTOP_MODE=true MOCK_MODE=false docker compose up -d

  5. In a separate terminal:
       pip install -r laptop_recognition_requirements.txt
       python laptop_recognition.py

  6. Open http://localhost:3000, log in as demo@smu.tn,
     navigate to the session for DEMO-LAP-001 and watch attendance update live.
═══════════════════════════════════════════════""")


if __name__ == "__main__":
    asyncio.run(main())
