from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import (
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

logger = logging.getLogger(__name__)

# ── Palette ────────────────────────────────────────────────────────────────

_PRIMARY    = colors.HexColor("#0075C9")
_LIGHT_GREY = colors.HexColor("#F8F9FA")
_BORDER     = colors.HexColor("#DDE3ED")
_DARK       = colors.HexColor("#1A2233")
_MUTED      = colors.HexColor("#5A6478")
_GREEN      = colors.HexColor("#006450")
_RED        = colors.HexColor("#EC0044")
_ORANGE     = colors.HexColor("#D4700A")
_GREY_TEXT  = colors.HexColor("#8E97A8")

_STATUS_COLORS = {
    "present": _GREEN,
    "absent":  _RED,
    "late":    _ORANGE,
    "excused": _GREY_TEXT,
}

_SENSOR_UNITS = {
    "temperature": "°C",
    "humidity":    "%",
    "air_quality": "ppm",
    "sound":       "bool",
}

_AT_RISK_THRESHOLD = 0.70


# ── Style helpers ──────────────────────────────────────────────────────────

def _ps(name, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **kw)


def _h1(text: str) -> Paragraph:
    return Paragraph(text, _ps("h1", fontName="Helvetica-Bold", fontSize=18,
                                textColor=_DARK, leading=22, spaceAfter=4))


def _h2(text: str) -> Paragraph:
    return Paragraph(text, _ps("h2", fontName="Helvetica-Bold", fontSize=14,
                                textColor=_DARK, leading=18, spaceBefore=12, spaceAfter=6))


def _h3(text: str) -> Paragraph:
    return Paragraph(text, _ps("h3", fontName="Helvetica-Bold", fontSize=11,
                                textColor=_MUTED, leading=14, spaceBefore=4, spaceAfter=2))


def _body(text: str, color=None) -> Paragraph:
    return Paragraph(text, _ps("body", fontName="Helvetica", fontSize=10,
                                textColor=color or _DARK, leading=14, spaceAfter=2))


def _small(text: str, color=None, align=TA_CENTER) -> Paragraph:
    return Paragraph(text, _ps("small", fontName="Helvetica", fontSize=8,
                                textColor=color or _MUTED, leading=10, alignment=align))


def _hr() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=8, spaceBefore=4)


def _table_style() -> TableStyle:
    return TableStyle([
        ("FONTNAME",        (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",        (0, 0), (-1, 0),  9),
        ("TEXTCOLOR",       (0, 0), (-1, 0),  _MUTED),
        ("BACKGROUND",      (0, 0), (-1, 0),  _LIGHT_GREY),
        ("FONTNAME",        (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",        (0, 1), (-1, -1), 9),
        ("TEXTCOLOR",       (0, 1), (-1, -1), _DARK),
        ("ROWBACKGROUNDS",  (0, 1), (-1, -1), [colors.white, _LIGHT_GREY]),
        ("GRID",            (0, 0), (-1, -1), 0.4, _BORDER),
        ("VALIGN",          (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",      (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",   (0, 0), (-1, -1), 5),
        ("LEFTPADDING",     (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",    (0, 0), (-1, -1), 7),
    ])


def _meta_style() -> TableStyle:
    return TableStyle([
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",    (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",   (0, 0), (0, -1),  _MUTED),
        ("TEXTCOLOR",   (1, 0), (1, -1),  _DARK),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ])


# ── Utility functions ──────────────────────────────────────────────────────

def _fmt_dt(dt) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


def _fmt_date(dt) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d")


def _fmt_time(dt) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%H:%M")


def _duration(start, end) -> str:
    if start is None or end is None:
        return "—"
    mins = int((end - start).total_seconds() / 60)
    if mins < 60:
        return f"{mins} min"
    return f"{mins // 60}h {mins % 60}m"


def _status_str(status) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _status_cell(status) -> Paragraph:
    s = _status_str(status)
    col = _STATUS_COLORS.get(s, _DARK)
    return Paragraph(s.capitalize(), _ps("sc", fontName="Helvetica-Bold",
                                          fontSize=9, textColor=col, leading=11))


def _header(report_type: str) -> list:
    return [
        _h3("SMU — Mediterranean Institute of Technology"),
        _h1(report_type),
        _hr(),
    ]


def _footer() -> list:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return [
        Spacer(1, 0.5 * cm),
        _hr(),
        _small(f"Generated by Smart Classroom System · {ts}"),
    ]


# ── Sensor summary (reuses DB query inline) ────────────────────────────────

async def _sensor_summary(session: Session, db: AsyncSession) -> dict:
    end = session.ended_at or datetime.now(timezone.utc)
    stats: dict[str, dict] = {}
    for stype in SensorType:
        row = (await db.execute(
            select(
                func.avg(SensorReading.value),
                func.min(SensorReading.value),
                func.max(SensorReading.value),
            ).where(
                SensorReading.room_id == session.room_id,
                SensorReading.sensor_type == stype,
                SensorReading.recorded_at >= session.started_at,
                SensorReading.recorded_at <= end,
            )
        )).one()
        if row[0] is not None:
            stats[stype.value] = {
                "avg":  round(float(row[0]), 1),
                "min":  round(float(row[1]), 1),
                "max":  round(float(row[2]), 1),
                "unit": _SENSOR_UNITS.get(stype.value, ""),
            }
    return stats


# ── AI summary (best-effort, never raises) ─────────────────────────────────

async def _ai_narrative(scope: str, scope_id: str, context: dict, redis_client) -> str | None:
    if redis_client is None:
        return None
    try:
        from app.services.ai_summary import generate_summary
        result = await generate_summary(scope, scope_id, context, redis_client)
        return result.get("narrative")
    except Exception as exc:
        logger.debug("AI summary skipped in PDF export (%s): %s", scope_id, exc)
        return None


# ── Session PDF ────────────────────────────────────────────────────────────

async def export_session_pdf(session_id: str, db: AsyncSession, redis_client) -> bytes:
    session = await db.get(Session, session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")
    if session.status != SessionStatus.ended:
        raise ValueError("Session is not ended — PDF requires a completed session")

    course = await db.get(Course, session.course_id)

    # Attendance records + student info
    recs_q = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id == session_id)
        .options(selectinload(AttendanceRecord.student))
        .order_by(AttendanceRecord.detected_at)
    )
    recs = list(recs_q.scalars().all())

    # Absent rows sort last
    recs_sorted = sorted(
        recs,
        key=lambda r: (r.status == AttendanceStatus.absent, r.detected_at or datetime.min.replace(tzinfo=timezone.utc)),
    )

    enrolled_count = (await db.execute(
        select(func.count()).select_from(course_students)
        .where(course_students.c.course_id == session.course_id)
    )).scalar_one() or 0

    sensor_stats = await _sensor_summary(session, db)

    ai_text = await _ai_narrative(
        "session", session_id,
        {
            "scope": "session",
            "session_id": session_id,
            "course": course.code if course else "?",
            "date": _fmt_dt(session.started_at),
            "attendance_rate": round(
                sum(1 for r in recs if r.status in (AttendanceStatus.present, AttendanceStatus.late))
                / max(1, len(recs)), 4
            ),
        },
        redis_client,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    story += _header("Session Report")

    # ── Metadata ────────────────────────────────────────────────────────────
    meta = Table(
        [
            ["Course",    course.name if course else "—"],
            ["Code",      course.code if course else "—"],
            ["Date",      _fmt_dt(session.started_at)],
            ["Professor", course.professor_name if course else "—"],
            ["Room",      session.room_id],
            ["Duration",  _duration(session.started_at, session.ended_at)],
        ],
        colWidths=[3.5*cm, None],
    )
    meta.setStyle(_meta_style())
    story.append(meta)
    story.append(Spacer(1, 0.3*cm))
    story.append(_hr())

    # ── Attendance ───────────────────────────────────────────────────────────
    story.append(_h2("Attendance"))
    present_n = sum(1 for r in recs if r.status == AttendanceStatus.present)
    absent_n  = sum(1 for r in recs if r.status == AttendanceStatus.absent)
    late_n    = sum(1 for r in recs if r.status == AttendanceStatus.late)
    excused_n = sum(1 for r in recs if r.status == AttendanceStatus.excused)

    if recs_sorted:
        rows = [["#", "Student Name", "Student ID", "Status", "Detected At", "Adjusted By"]]
        for i, r in enumerate(recs_sorted, 1):
            rows.append([
                str(i),
                r.student.name if r.student else "—",
                r.student.student_id if r.student else "—",
                _status_cell(r.status),
                _fmt_time(r.detected_at),
                r.adjusted_by or "—",
            ])
        att_t = Table(rows, colWidths=[0.6*cm, None, 2.6*cm, 2.0*cm, 2.0*cm, 2.4*cm], repeatRows=1)
        att_t.setStyle(_table_style())
        story.append(att_t)
    else:
        story.append(_body("No attendance records for this session.", color=_MUTED))

    story.append(Spacer(1, 0.2*cm))
    story.append(_body(
        f"Present: {present_n}  |  Absent: {absent_n}  |  Late: {late_n}  |  Excused: {excused_n}  |  Total Enrolled: {enrolled_count}",
        color=_MUTED,
    ))
    story.append(_hr())

    # ── Sensors ──────────────────────────────────────────────────────────────
    story.append(_h2("Environmental Summary"))
    if sensor_stats:
        rows = [["Sensor", "Average", "Min", "Max", "Unit"]]
        for stype, s in sensor_stats.items():
            rows.append([stype.replace("_", " ").title(), str(s["avg"]), str(s["min"]), str(s["max"]), s["unit"]])
        st = Table(rows, colWidths=[3.5*cm, 3*cm, 3*cm, 3*cm, 2*cm], repeatRows=1)
        st.setStyle(_table_style())
        story.append(st)
    else:
        story.append(_body("No sensor data recorded for this session.", color=_MUTED))

    story.append(_hr())

    # ── AI Summary ────────────────────────────────────────────────────────────
    story.append(_h2("AI Summary"))
    story.append(_body(ai_text or "AI summaries not configured or Ollama is unreachable.", color=_MUTED if not ai_text else None))

    story += _footer()

    doc.build(story)
    return buf.getvalue()


# ── Course PDF ─────────────────────────────────────────────────────────────

async def export_course_pdf(course_id: str, db: AsyncSession, redis_client=None) -> bytes:
    course = await db.get(Course, course_id)
    if course is None:
        raise ValueError(f"Course {course_id} not found")

    sessions_q = await db.execute(
        select(Session)
        .where(Session.course_id == course_id, Session.status == SessionStatus.ended)
        .order_by(Session.started_at)
    )
    sessions = list(sessions_q.scalars().all())
    session_ids = [s.id for s in sessions]

    # Enrolled students
    enroll_q = await db.execute(
        select(Student)
        .join(course_students, Student.id == course_students.c.student_id)
        .where(course_students.c.course_id == course_id)
        .order_by(Student.name)
    )
    students = list(enroll_q.scalars().all())

    # All attendance records
    all_recs: list[AttendanceRecord] = []
    if session_ids:
        recs_q = await db.execute(
            select(AttendanceRecord)
            .where(AttendanceRecord.session_id.in_(session_ids))
            .options(selectinload(AttendanceRecord.student))
        )
        all_recs = list(recs_q.scalars().all())

    total_sessions = len(sessions)

    # Per-student stats, sorted by rate ascending (worst first)
    student_stats = []
    for st in students:
        attended = sum(
            1 for r in all_recs
            if r.student_id == st.id
            and r.status in (AttendanceStatus.present, AttendanceStatus.late)
        )
        rate = (attended / total_sessions) if total_sessions > 0 else 0.0
        student_stats.append({
            "name":             st.name,
            "institutional_id": st.student_id,
            "attended":         attended,
            "total":            total_sessions,
            "rate":             rate,
            "at_risk":          rate < _AT_RISK_THRESHOLD,
        })
    student_stats.sort(key=lambda x: x["rate"])

    # Report period
    period_start = _fmt_date(sessions[0].started_at)  if sessions else "—"
    period_end   = _fmt_date(sessions[-1].started_at) if sessions else "—"

    ai_text = await _ai_narrative(
        "course", course_id,
        {
            "scope":           "course",
            "course_code":     course.code,
            "course_name":     course.name,
            "total_sessions":  total_sessions,
            "period":          f"{period_start} to {period_end}",
            "at_risk_count":   sum(1 for s in student_stats if s["at_risk"]),
        },
        redis_client,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    story += _header("Course Report")

    # ── Metadata ────────────────────────────────────────────────────────────
    meta = Table(
        [
            ["Course",          course.name],
            ["Course Code",     course.code],
            ["Professor",       course.professor_name],
            ["Total Sessions",  str(total_sessions)],
            ["Report Period",   f"{period_start} → {period_end}"],
        ],
        colWidths=[3.5*cm, None],
    )
    meta.setStyle(_meta_style())
    story.append(meta)
    story.append(Spacer(1, 0.3*cm))
    story.append(_hr())

    # ── Per-student attendance ───────────────────────────────────────────────
    story.append(_h2("Attendance Summary"))
    if student_stats:
        rows = [["Student Name", "Student ID", "Attended", "Total", "Rate %", "Risk"]]
        for s in student_stats:
            flag_cell = Paragraph(
                "⚠ At Risk",
                _ps("flag", fontName="Helvetica-Bold", fontSize=9, textColor=_RED),
            ) if s["at_risk"] else ""
            rows.append([
                s["name"],
                s["institutional_id"],
                str(s["attended"]),
                str(s["total"]),
                f"{round(s['rate'] * 100)}%",
                flag_cell,
            ])
        st_t = Table(rows, colWidths=[None, 2.5*cm, 2*cm, 2*cm, 1.8*cm, 2.2*cm], repeatRows=1)
        st_t.setStyle(_table_style())
        story.append(st_t)
    else:
        story.append(_body("No enrolled students found.", color=_MUTED))

    story.append(_hr())

    # ── Session history ──────────────────────────────────────────────────────
    story.append(_h2("Session History"))
    if sessions:
        sess_rows = [["Date", "Duration", "Present", "Absent", "Late", "Rate %"]]
        for sess in sessions:
            sess_recs = [r for r in all_recs if r.session_id == sess.id]
            total = len(sess_recs)
            present = sum(1 for r in sess_recs if r.status == AttendanceStatus.present)
            late    = sum(1 for r in sess_recs if r.status == AttendanceStatus.late)
            absent  = sum(1 for r in sess_recs if r.status == AttendanceStatus.absent)
            rate_str = f"{round(((present + late) / total) * 100)}%" if total > 0 else "—"
            sess_rows.append([
                _fmt_date(sess.started_at),
                _duration(sess.started_at, sess.ended_at),
                str(present), str(absent), str(late), rate_str,
            ])
        sess_t = Table(sess_rows, colWidths=[2.5*cm, 2.2*cm, 2*cm, 2*cm, 1.8*cm, None], repeatRows=1)
        sess_t.setStyle(_table_style())
        story.append(sess_t)
    else:
        story.append(_body("No ended sessions found.", color=_MUTED))

    story.append(_hr())

    # ── AI Summary ────────────────────────────────────────────────────────────
    story.append(_h2("AI Summary"))
    story.append(_body(ai_text or "AI summaries not configured or Ollama is unreachable.", color=_MUTED if not ai_text else None))

    story += _footer()

    doc.build(story)
    return buf.getvalue()
