from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import (
    Alert,
    AttendanceRecord,
    AttendanceStatus,
    Course,
    SensorReading,
    SensorType,
    Session,
    SessionStatus,
    Student,
    course_students,
)

_SYSTEM_ADMIN_ID = "00000000-0000-0000-0000-000000000000"


def _is_admin(professor_id: str | None) -> bool:
    return professor_id is None or professor_id == _SYSTEM_ADMIN_ID


class InsightsEngine:

    # ── Overview ──────────────────────────────────────────────────────────

    async def get_overview(
        self,
        db: AsyncSession,
        professor_id: str | None,
        redis_client,
    ) -> dict:
        s_q = select(func.count()).select_from(Session).where(Session.status == SessionStatus.ended)
        if not _is_admin(professor_id):
            s_q = (
                select(func.count())
                .select_from(Session)
                .join(Course, Session.course_id == Course.id)
                .where(Session.status == SessionStatus.ended, Course.professor_id == professor_id)
            )
        total_sessions: int = (await db.execute(s_q)).scalar_one() or 0

        ar_q = (
            select(
                func.count(AttendanceRecord.id)
                .filter(AttendanceRecord.status.in_([AttendanceStatus.present, AttendanceStatus.late]))
                .label("attended"),
                func.count(AttendanceRecord.id).label("total"),
            )
            .join(Session, AttendanceRecord.session_id == Session.id)
            .join(Course, Session.course_id == Course.id)
            .where(Session.status == SessionStatus.ended)
        )
        if not _is_admin(professor_id):
            ar_q = ar_q.where(Course.professor_id == professor_id)
        ar_row = (await db.execute(ar_q)).one()
        avg_rate = (ar_row.attended / ar_row.total) if ar_row.total > 0 else 0.0

        alerts_count: int = (
            await db.execute(
                select(func.count()).select_from(Alert).where(Alert.acknowledged == False)  # noqa: E712
            )
        ).scalar_one() or 0

        from app.config import settings
        comfort = await self.get_comfort_score(settings.room_id, redis_client)

        at_risk = await self.get_at_risk_students(db, professor_id)

        return {
            "total_sessions": total_sessions,
            "avg_attendance_rate": round(avg_rate, 4),
            "active_alerts_count": alerts_count,
            "comfort_score": round(comfort, 1),
            "at_risk_count": len(at_risk),
        }

    # ── Attendance Trend ──────────────────────────────────────────────────

    async def get_attendance_trend(
        self,
        db: AsyncSession,
        course_id: str | None = None,
        weeks: int = 8,
        professor_id: str | None = None,
    ) -> list[dict]:
        start_dt = datetime.now(timezone.utc) - timedelta(weeks=weeks)
        week_expr = func.date_trunc("week", Session.started_at)

        q = (
            select(
                week_expr.label("week"),
                func.count(AttendanceRecord.id)
                .filter(AttendanceRecord.status.in_([AttendanceStatus.present, AttendanceStatus.late]))
                .label("attended"),
                func.count(AttendanceRecord.id).label("total"),
            )
            .join(AttendanceRecord, AttendanceRecord.session_id == Session.id)
            .join(Course, Session.course_id == Course.id)
            .where(Session.status == SessionStatus.ended, Session.started_at >= start_dt)
        )

        if course_id:
            q = q.where(Session.course_id == course_id)
        elif not _is_admin(professor_id):
            q = q.where(Course.professor_id == professor_id)

        q = q.group_by(week_expr).order_by(week_expr)
        rows = (await db.execute(q)).all()
        return [
            {
                "week_label": row.week.strftime("%Y-W%W"),
                "attendance_rate": round((row.attended / row.total) if row.total > 0 else 0.0, 4),
            }
            for row in rows
        ]

    # ── Attendance Heatmap ────────────────────────────────────────────────

    async def get_attendance_heatmap(
        self,
        db: AsyncSession,
        professor_id: str | None,
    ) -> list[dict]:
        # PostgreSQL DOW: 0=Sunday. Convert to ISO week: 0=Monday via (dow+6)%7
        dow_pg = func.extract("dow", Session.started_at).cast(Integer)
        mon_dow = ((dow_pg + 6) % 7)
        hour = func.extract("hour", Session.started_at).cast(Integer)
        slot = case(
            (hour.between(6, 11), 0),
            (hour.between(12, 17), 1),
            else_=2,
        )

        q = (
            select(
                mon_dow.label("day_of_week"),
                slot.label("hour_slot"),
                func.count(AttendanceRecord.id)
                .filter(AttendanceRecord.status.in_([AttendanceStatus.present, AttendanceStatus.late]))
                .label("attended"),
                func.count(AttendanceRecord.id).label("total"),
            )
            .join(AttendanceRecord, AttendanceRecord.session_id == Session.id)
            .join(Course, Session.course_id == Course.id)
            .where(Session.status == SessionStatus.ended)
        )
        if not _is_admin(professor_id):
            q = q.where(Course.professor_id == professor_id)

        q = q.group_by(mon_dow, slot).order_by(mon_dow, slot)
        rows = (await db.execute(q)).all()
        return [
            {
                "day_of_week": int(row.day_of_week),
                "hour_slot": int(row.hour_slot),
                "avg_rate": round((row.attended / row.total) if row.total > 0 else 0.0, 4),
            }
            for row in rows
        ]

    # ── Attendance Decay ──────────────────────────────────────────────────

    async def get_attendance_decay(
        self,
        db: AsyncSession,
        professor_id: str | None,
    ) -> list[dict]:
        q = (
            select(Session, Course.code)
            .join(Course, Session.course_id == Course.id)
            .where(Session.status == SessionStatus.ended)
            .order_by(Session.course_id, Session.started_at)
        )
        if not _is_admin(professor_id):
            q = q.where(Course.professor_id == professor_id)

        rows = (await db.execute(q)).all()

        sessions_by_course: dict[str, list] = {}
        code_by_course: dict[str, str] = {}
        for sess, code in rows:
            sessions_by_course.setdefault(sess.course_id, []).append(sess)
            code_by_course[sess.course_id] = code

        result = []
        for course_id, sessions in sessions_by_course.items():
            if len(sessions) < 2:
                continue
            first_rate = await self._session_attendance_rate(db, sessions[0].id)
            last_rate = await self._session_attendance_rate(db, sessions[-1].id)
            result.append({
                "course_code": code_by_course[course_id],
                "first_session_rate": round(first_rate, 4),
                "last_session_rate": round(last_rate, 4),
                "delta": round(last_rate - first_rate, 4),
            })
        return result

    async def _session_attendance_rate(self, db: AsyncSession, session_id: str) -> float:
        row = (await db.execute(
            select(
                func.count(AttendanceRecord.id)
                .filter(AttendanceRecord.status.in_([AttendanceStatus.present, AttendanceStatus.late]))
                .label("attended"),
                func.count(AttendanceRecord.id).label("total"),
            ).where(AttendanceRecord.session_id == session_id)
        )).one()
        return (row.attended / row.total) if row.total > 0 else 0.0

    # ── At-Risk Students ──────────────────────────────────────────────────

    async def get_at_risk_students(
        self,
        db: AsyncSession,
        professor_id: str | None,
        threshold: float = 0.70,
        consecutive: int = 3,
    ) -> list[dict]:
        c_q = select(Course)
        if not _is_admin(professor_id):
            c_q = c_q.where(Course.professor_id == professor_id)
        courses = (await db.execute(c_q)).scalars().all()
        if not courses:
            return []

        course_ids = [c.id for c in courses]
        course_map = {c.id: c for c in courses}

        sessions_res = (await db.execute(
            select(Session)
            .where(Session.course_id.in_(course_ids), Session.status == SessionStatus.ended)
            .order_by(Session.course_id, Session.started_at)
        )).scalars().all()
        if not sessions_res:
            return []

        session_ids = [s.id for s in sessions_res]
        sessions_by_course: dict[str, list] = {}
        for s in sessions_res:
            sessions_by_course.setdefault(s.course_id, []).append(s)

        enrollments = (await db.execute(
            select(course_students).where(course_students.c.course_id.in_(course_ids))
        )).all()

        enrolled_by_course: dict[str, set] = {}
        all_student_ids: set[str] = set()
        for e in enrollments:
            enrolled_by_course.setdefault(e.course_id, set()).add(e.student_id)
            all_student_ids.add(e.student_id)

        if not all_student_ids:
            return []

        records = (await db.execute(
            select(AttendanceRecord).where(AttendanceRecord.session_id.in_(session_ids))
        )).scalars().all()
        rec_map: dict[tuple, AttendanceStatus] = {(r.student_id, r.session_id): r.status for r in records}

        students = (await db.execute(
            select(Student).where(Student.id.in_(all_student_ids))
        )).scalars().all()
        student_map = {s.id: s for s in students}

        at_risk: dict[str, dict] = {}

        for course_id, course_sessions in sessions_by_course.items():
            for student_id in enrolled_by_course.get(course_id, set()):
                present_count = 0
                cur_consec = 0
                max_consec = 0

                for sess in course_sessions:
                    status = rec_map.get((student_id, sess.id))
                    if status in (AttendanceStatus.present, AttendanceStatus.late):
                        present_count += 1
                        cur_consec = 0
                    elif status == AttendanceStatus.absent:
                        cur_consec += 1
                        max_consec = max(max_consec, cur_consec)
                    else:
                        cur_consec = 0

                rate = present_count / len(course_sessions)
                if rate >= threshold and max_consec < consecutive:
                    continue

                st = student_map.get(student_id)
                if student_id not in at_risk:
                    at_risk[student_id] = {
                        "student_id": student_id,
                        "name": st.name if st else "Unknown",
                        "institutional_id": st.student_id if st else "",
                        "attendance_rate": rate,
                        "consecutive_absences": max_consec,
                        "courses_at_risk": [],
                    }
                at_risk[student_id]["courses_at_risk"].append(course_map[course_id].code)
                if rate < at_risk[student_id]["attendance_rate"]:
                    at_risk[student_id]["attendance_rate"] = rate
                if max_consec > at_risk[student_id]["consecutive_absences"]:
                    at_risk[student_id]["consecutive_absences"] = max_consec

        result = list(at_risk.values())
        for r in result:
            r["attendance_rate"] = round(r["attendance_rate"], 4)
        return result

    # ── Student Profile ───────────────────────────────────────────────────

    async def get_student_profile(self, db: AsyncSession, student_id: str) -> dict | None:
        st = await db.get(Student, student_id)
        if not st:
            return None

        courses = (await db.execute(
            select(Course)
            .join(course_students, Course.id == course_students.c.course_id)
            .where(course_students.c.student_id == student_id)
        )).scalars().all()

        per_course = []
        overall_attended = 0
        overall_total = 0

        for course in courses:
            sessions = (await db.execute(
                select(Session).where(
                    Session.course_id == course.id,
                    Session.status == SessionStatus.ended,
                )
            )).scalars().all()
            total = len(sessions)
            if total == 0:
                continue

            attended = (await db.execute(
                select(func.count()).select_from(AttendanceRecord).where(
                    AttendanceRecord.session_id.in_([s.id for s in sessions]),
                    AttendanceRecord.student_id == student_id,
                    AttendanceRecord.status.in_([AttendanceStatus.present, AttendanceStatus.late]),
                )
            )).scalar_one() or 0

            overall_attended += attended
            overall_total += total
            per_course.append({
                "course_code": course.code,
                "sessions_attended": attended,
                "sessions_total": total,
                "rate": round(attended / total, 4),
            })

        overall_rate = (overall_attended / overall_total) if overall_total > 0 else 0.0
        if overall_rate < 0.70:
            risk_level = "high"
        elif overall_rate < 0.85:
            risk_level = "medium"
        else:
            risk_level = "low"

        recent_rows = (await db.execute(
            select(AttendanceRecord, Session, Course.code)
            .join(Session, AttendanceRecord.session_id == Session.id)
            .join(Course, Session.course_id == Course.id)
            .where(AttendanceRecord.student_id == student_id)
            .order_by(Session.started_at.desc())
            .limit(10)
        )).all()
        recent_sessions = [
            {"date": row[1].started_at.isoformat(), "course_code": row[2], "status": row[0].status.value}
            for row in recent_rows
        ]

        return {
            "student_id": student_id,
            "name": st.name,
            "institutional_id": st.student_id,
            "overall_attendance_rate": round(overall_rate, 4),
            "risk_level": risk_level,
            "per_course": per_course,
            "recent_sessions": recent_sessions,
        }

    # ── Comfort Score ─────────────────────────────────────────────────────

    async def get_comfort_score(self, room_id: str, redis_client) -> float:
        keys = [
            f"classroom:{room_id}:sensors:temperature",
            f"classroom:{room_id}:sensors:humidity",
            f"classroom:{room_id}:sensors:air_quality",
        ]
        values = await redis_client.mget(keys)

        temp = humidity = air_quality = None
        for key_suffix, raw in zip(["temperature", "humidity", "air_quality"], values):
            if raw:
                try:
                    data = json.loads(raw)
                    v = data["value"]
                    if key_suffix == "temperature":
                        temp = v
                    elif key_suffix == "humidity":
                        humidity = v
                    elif key_suffix == "air_quality":
                        air_quality = v
                except Exception:
                    pass

        score = 100.0
        if temp is not None:
            score -= max(0, temp - 26) * 5
            score -= max(0, 18 - temp) * 5
        if humidity is not None:
            score -= max(0, humidity - 65) * 2
        if air_quality is not None:
            score -= max(0, (air_quality - 300) / 50)
        return max(0.0, min(100.0, score))

    # ── Environment Trends ────────────────────────────────────────────────

    async def get_environment_trends(
        self,
        db: AsyncSession,
        room_id: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> list[dict]:
        day_expr = func.date_trunc("day", SensorReading.recorded_at)
        rows = (await db.execute(
            select(
                day_expr.label("day"),
                SensorReading.sensor_type,
                func.avg(SensorReading.value).label("avg_val"),
                func.min(SensorReading.value).label("min_val"),
                func.max(SensorReading.value).label("max_val"),
            )
            .where(
                SensorReading.room_id == room_id,
                SensorReading.recorded_at >= from_dt,
                SensorReading.recorded_at <= to_dt,
                SensorReading.sensor_type.in_(
                    [SensorType.temperature, SensorType.humidity, SensorType.air_quality]
                ),
            )
            .group_by(day_expr, SensorReading.sensor_type)
            .order_by(day_expr)
        )).all()

        days: dict[str, dict] = {}
        for row in rows:
            day_str = row.day.strftime("%Y-%m-%d")
            if day_str not in days:
                days[day_str] = {"date": day_str}
            t = row.sensor_type.value if hasattr(row.sensor_type, "value") else str(row.sensor_type)
            if t == "temperature":
                days[day_str].update({
                    "temp_avg": round(row.avg_val, 2),
                    "temp_min": round(row.min_val, 2),
                    "temp_max": round(row.max_val, 2),
                })
            elif t == "humidity":
                days[day_str]["humidity_avg"] = round(row.avg_val, 2)
            elif t == "air_quality":
                days[day_str]["air_quality_avg"] = round(row.avg_val, 2)

        return list(days.values())

    # ── AC Effectiveness ──────────────────────────────────────────────────

    async def get_ac_effectiveness(self, db: AsyncSession, room_id: str) -> dict:
        from app.config import settings

        sessions = (await db.execute(
            select(Session)
            .where(Session.room_id == room_id, Session.status == SessionStatus.ended)
            .order_by(Session.started_at)
        )).scalars().all()

        lags: list[float] = []
        for sess in sessions:
            if not sess.ended_at:
                continue
            readings = (await db.execute(
                select(SensorReading)
                .where(
                    SensorReading.room_id == room_id,
                    SensorReading.sensor_type == SensorType.temperature,
                    SensorReading.recorded_at >= sess.started_at,
                    SensorReading.recorded_at <= sess.ended_at,
                )
                .order_by(SensorReading.recorded_at)
            )).scalars().all()

            if len(readings) < 2:
                continue

            ac_on_time = None
            for r in readings:
                if r.value >= settings.temp_ac_on_threshold:
                    ac_on_time = r.recorded_at
                    break
            if ac_on_time is None:
                continue

            for r in readings:
                if r.recorded_at > ac_on_time and r.value <= settings.temp_ac_off_threshold:
                    lags.append((r.recorded_at - ac_on_time).total_seconds() / 60.0)
                    break

        if not lags:
            return {"avg_lag_minutes": None, "sample_size": 0}
        return {"avg_lag_minutes": round(sum(lags) / len(lags), 1), "sample_size": len(lags)}

    # ── Temp vs Attendance ────────────────────────────────────────────────

    async def get_temp_vs_attendance(
        self,
        db: AsyncSession,
        professor_id: str | None,
    ) -> list[dict]:
        q = (
            select(Session, Course.code)
            .join(Course, Session.course_id == Course.id)
            .where(Session.status == SessionStatus.ended)
        )
        if not _is_admin(professor_id):
            q = q.where(Course.professor_id == professor_id)
        sessions = (await db.execute(q)).all()

        result = []
        for sess, code in sessions:
            end = sess.ended_at or datetime.now(timezone.utc)
            avg_temp = (await db.execute(
                select(func.avg(SensorReading.value)).where(
                    SensorReading.room_id == sess.room_id,
                    SensorReading.sensor_type == SensorType.temperature,
                    SensorReading.recorded_at >= sess.started_at,
                    SensorReading.recorded_at <= end,
                )
            )).scalar_one()
            if avg_temp is None:
                continue
            rate = await self._session_attendance_rate(db, sess.id)
            result.append({
                "session_id": sess.id,
                "course_code": code,
                "date": sess.started_at.strftime("%Y-%m-%d"),
                "avg_temp": round(float(avg_temp), 2),
                "attendance_rate": round(rate, 4),
            })
        return result

    # ── Air Quality vs Sound ──────────────────────────────────────────────

    async def get_airquality_vs_sound(self, db: AsyncSession, room_id: str) -> list[dict]:
        sessions = (await db.execute(
            select(Session).where(Session.room_id == room_id, Session.status == SessionStatus.ended)
        )).scalars().all()

        result = []
        for sess in sessions:
            end = sess.ended_at or datetime.now(timezone.utc)
            avg_aq = (await db.execute(
                select(func.avg(SensorReading.value)).where(
                    SensorReading.room_id == room_id,
                    SensorReading.sensor_type == SensorType.air_quality,
                    SensorReading.recorded_at >= sess.started_at,
                    SensorReading.recorded_at <= end,
                )
            )).scalar_one()
            if avg_aq is None:
                continue

            sound_row = (await db.execute(
                select(
                    func.count(SensorReading.id).filter(SensorReading.value > 0).label("detected"),
                    func.count(SensorReading.id).label("total"),
                ).where(
                    SensorReading.room_id == room_id,
                    SensorReading.sensor_type == SensorType.sound,
                    SensorReading.recorded_at >= sess.started_at,
                    SensorReading.recorded_at <= end,
                )
            )).one()
            pct = (sound_row.detected / sound_row.total) if sound_row.total > 0 else 0.0
            result.append({
                "session_id": sess.id,
                "date": sess.started_at.strftime("%Y-%m-%d"),
                "avg_air_quality": round(float(avg_aq), 2),
                "pct_sound_detected": round(pct, 4),
            })
        return result


insights_engine = InsightsEngine()
