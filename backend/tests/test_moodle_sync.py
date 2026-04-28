"""
Tests for Moodle sync service and related endpoints.

All httpx calls are mocked — no live Moodle required.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

pytestmark = pytest.mark.asyncio


# ── helpers ───────────────────────────────────────────────────────────────

def _mock_httpx_response(json_data):
    """Return a mock httpx.Response that returns json_data."""
    m = MagicMock()
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    return m


async def _setup_session_with_record(test_engine) -> tuple[str, str]:
    """Create a course, student, session and one attendance record. Return (session_id, record_id)."""
    import uuid
    from app.models.db_models import (
        AttendanceRecord, AttendanceStatus, Course, Session, SessionStatus, Student
    )
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSessionLocal() as db:
        # Unique code per call to avoid UNIQUE constraint collision across tests
        course = Course(code=f"MDL_{uuid.uuid4().hex[:8]}", name="Moodle Test", professor_name="Prof")
        db.add(course)
        await db.flush()

        student = Student(name="Sync Student", student_id=f"SYNC_{uuid.uuid4().hex[:8]}")
        db.add(student)
        await db.flush()

        session = Session(
            course_id=course.id, room_id="room_moodle", status=SessionStatus.active
        )
        db.add(session)
        await db.flush()

        record = AttendanceRecord(
            session_id=session.id,
            student_id=student.id,
            status=AttendanceStatus.present,
            moodle_synced=False,
        )
        db.add(record)
        await db.commit()
        return session.id, record.id


# ── MoodleClient unit tests ───────────────────────────────────────────────

async def test_connection_success() -> None:
    from app.services.moodle_client import MoodleClient
    client = MoodleClient()
    mock_resp = _mock_httpx_response({"sitename": "Moodle", "username": "admin"})

    with patch.object(client, "_client_instance") as mock_factory:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_factory.return_value = mock_http
        assert await client.test_connection() is True
    await client.close()


async def test_connection_failure() -> None:
    import httpx
    from app.services.moodle_client import MoodleClient
    client = MoodleClient()

    with patch.object(client, "_client_instance") as mock_factory:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_factory.return_value = mock_http
        assert await client.test_connection() is False
    await client.close()


async def test_moodle_exception_in_response() -> None:
    """Moodle returns HTTP 200 but with an exception dict — should be treated as error."""
    from app.services.moodle_client import MoodleClient
    client = MoodleClient()
    mock_resp = _mock_httpx_response({
        "exception": "moodle_exception",
        "errorcode": "invalidtoken",
        "message": "Invalid token",
    })

    with patch.object(client, "_client_instance") as mock_factory:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_factory.return_value = mock_http
        assert await client.test_connection() is False
    await client.close()


async def test_get_courses_returns_list() -> None:
    from app.services.moodle_client import MoodleClient
    client = MoodleClient()
    mock_resp = _mock_httpx_response([{"id": 1, "fullname": "CS101"}])

    with patch.object(client, "_client_instance") as mock_factory:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_factory.return_value = mock_http
        courses = await client.get_courses()
        assert len(courses) == 1
        assert courses[0]["fullname"] == "CS101"
    await client.close()


async def test_sync_attendance_success(test_engine) -> None:
    """Happy path: records are synced and moodle_synced is set to True."""
    from sqlalchemy import select
    from app.models.db_models import AttendanceRecord
    from app.services.moodle_client import MoodleClient

    session_id, record_id = await _setup_session_with_record(test_engine)
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    client = MoodleClient()
    mock_resp = _mock_httpx_response({"status": "ok"})

    with (
        patch.object(client, "_client_instance") as mock_factory,
        patch("app.services.moodle_client.AsyncSessionLocal", TestSessionLocal),
    ):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_factory.return_value = mock_http
        result = await client.sync_attendance(session_id)

    assert result["synced"] == 1
    assert result["failed"] == 0

    async with TestSessionLocal() as db:
        rec = await db.get(AttendanceRecord, record_id)
        assert rec.moodle_synced is True

    await client.close()


async def test_sync_attendance_moodle_unreachable(test_engine) -> None:
    """When Moodle is down, failed count increments and session pushed to retry queue."""
    import httpx
    from app.services.moodle_client import MoodleClient

    session_id, _ = await _setup_session_with_record(test_engine)
    # Use a new session+record for isolation (same test engine, different IDs)
    # Actually use the same ones — moodle_synced is still False
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    client = MoodleClient()
    pushed: list[str] = []

    async def _fake_push(sid):
        pushed.append(sid)

    with (
        patch.object(client, "_client_instance") as mock_factory,
        patch("app.services.moodle_client.AsyncSessionLocal", TestSessionLocal),
        patch("app.services.moodle_client._push_retry_queue", side_effect=_fake_push),
    ):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_factory.return_value = mock_http
        result = await client.sync_attendance(session_id)

    assert result["failed"] >= 1
    assert result["synced"] == 0
    assert session_id in pushed

    await client.close()


async def test_sync_no_records(test_engine) -> None:
    """Sync on a session with no records returns zeros without calling Moodle."""
    from app.services.moodle_client import MoodleClient
    from app.models.db_models import Session, SessionStatus, Course
    import uuid

    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSessionLocal() as db:
        course = Course(code=f"EMPTY_{uuid.uuid4().hex[:6]}", name="Empty", professor_name="Prof")
        db.add(course)
        await db.flush()
        session = Session(course_id=course.id, room_id="room_empty", status=SessionStatus.ended)
        db.add(session)
        await db.commit()
        sid = session.id

    client = MoodleClient()
    with patch("app.services.moodle_client.AsyncSessionLocal", TestSessionLocal):
        result = await client.sync_attendance(sid)

    assert result["synced"] == 0
    assert result["failed"] == 0
    await client.close()


# ── API endpoint tests ────────────────────────────────────────────────────

async def test_moodle_test_endpoint_connected(client: AsyncClient) -> None:
    with patch("app.services.moodle_client.moodle_client.test_connection", new_callable=AsyncMock, return_value=True):
        resp = await client.get("/api/moodle-test")
    assert resp.status_code == 200
    assert resp.json()["connected"] is True


async def test_moodle_test_endpoint_disconnected(client: AsyncClient) -> None:
    with patch("app.services.moodle_client.moodle_client.test_connection", new_callable=AsyncMock, return_value=False):
        resp = await client.get("/api/moodle-test")
    assert resp.status_code == 200
    assert resp.json()["connected"] is False


async def test_sync_moodle_endpoint(client: AsyncClient) -> None:
    """POST /api/sessions/{id}/sync-moodle returns sync result."""
    # Create a course + session first
    cr = await client.post(
        "/api/courses",
        json={"code": "MOODLE_EP", "name": "Moodle EP", "professor_name": "Prof"},
    )
    course_id = cr.json()["id"]
    sess = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_mep"})
    session_id = sess.json()["id"]

    fake_result = {"synced": 0, "failed": 0, "session_id": session_id}
    # Patch the singleton on its module so the lazy import inside the endpoint resolves it
    with patch("app.services.moodle_client.moodle_client.sync_attendance", new=AsyncMock(return_value=fake_result)):
        resp = await client.post(f"/api/sessions/{session_id}/sync-moodle")

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert "synced" in data
    assert "failed" in data


async def test_sync_moodle_session_not_found(client: AsyncClient) -> None:
    resp = await client.post("/api/sessions/no-such-id/sync-moodle")
    assert resp.status_code == 404
