"""
Integration tests for courses, sessions, and attendance APIs.

Uses the same in-memory SQLite engine as the face enrollment tests.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# ── Courses ───────────────────────────────────────────────────────────────

async def test_create_course(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/courses",
        json={"code": "CS101", "name": "Intro to CS", "professor_name": "Dr. Smith"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "CS101"
    assert "id" in data


async def test_create_course_duplicate_returns_409(client: AsyncClient) -> None:
    await client.post(
        "/api/courses",
        json={"code": "CS102", "name": "Data Structures", "professor_name": "Dr. Jones"},
    )
    resp = await client.post(
        "/api/courses",
        json={"code": "CS102", "name": "Different Name", "professor_name": "Dr. Jones"},
    )
    assert resp.status_code == 409


async def test_list_courses(client: AsyncClient) -> None:
    await client.post(
        "/api/courses",
        json={"code": "CS103", "name": "Algorithms", "professor_name": "Dr. Lee"},
    )
    resp = await client.get("/api/courses")
    assert resp.status_code == 200
    assert any(c["code"] == "CS103" for c in resp.json())


async def test_enroll_students(client: AsyncClient) -> None:
    cr = await client.post(
        "/api/courses",
        json={"code": "CS104", "name": "Networks", "professor_name": "Dr. Brown"},
    )
    course_id = cr.json()["id"]

    sr = await client.post("/api/students", json={"name": "Hedi", "student_id": "STU_H1"})
    student_id = sr.json()["id"]

    resp = await client.post(f"/api/courses/{course_id}/enroll", json={"student_ids": [student_id]})
    assert resp.status_code == 200


async def test_enroll_unknown_student_returns_404(client: AsyncClient) -> None:
    cr = await client.post(
        "/api/courses",
        json={"code": "CS105", "name": "OS", "professor_name": "Dr. Grey"},
    )
    course_id = cr.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/enroll", json={"student_ids": ["nonexistent-id"]})
    assert resp.status_code == 404


# ── Sessions ──────────────────────────────────────────────────────────────

async def _create_course_and_start_session(client: AsyncClient, code: str, room: str) -> dict:
    cr = await client.post(
        "/api/courses",
        json={"code": code, "name": f"Course {code}", "professor_name": "Prof"},
    )
    course_id = cr.json()["id"]
    sr = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": room})
    return sr.json()


async def test_start_session(client: AsyncClient) -> None:
    resp = await _create_course_and_start_session(client, "SES201", "room_A")
    assert resp["status"] == "active"
    assert "id" in resp


async def test_start_session_course_not_found(client: AsyncClient) -> None:
    resp = await client.post("/api/sessions/start", json={"course_id": "no-such", "room_id": "room_B"})
    assert resp.status_code == 404


async def test_start_session_conflict_active(client: AsyncClient) -> None:
    await _create_course_and_start_session(client, "SES202", "room_C")
    # Try to start another session in the same room
    cr2 = await client.post(
        "/api/courses",
        json={"code": "SES203", "name": "Another", "professor_name": "Prof"},
    )
    resp = await client.post(
        "/api/sessions/start",
        json={"course_id": cr2.json()["id"], "room_id": "room_C"},
    )
    assert resp.status_code == 409


async def test_end_session(client: AsyncClient) -> None:
    session = await _create_course_and_start_session(client, "SES204", "room_D")
    session_id = session["id"]
    resp = await client.post(f"/api/sessions/{session_id}/end")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ended"
    assert resp.json()["ended_at"] is not None


async def test_end_session_already_ended_returns_409(client: AsyncClient) -> None:
    session = await _create_course_and_start_session(client, "SES205", "room_E")
    session_id = session["id"]
    await client.post(f"/api/sessions/{session_id}/end")
    resp = await client.post(f"/api/sessions/{session_id}/end")
    assert resp.status_code == 409


async def test_get_session(client: AsyncClient) -> None:
    session = await _create_course_and_start_session(client, "SES206", "room_F")
    session_id = session["id"]
    resp = await client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session_id
    assert "present_count" in data
    assert "total_students" in data


async def test_list_sessions(client: AsyncClient) -> None:
    await _create_course_and_start_session(client, "SES207", "room_G")
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ── Attendance ────────────────────────────────────────────────────────────

async def test_get_attendance_empty(client: AsyncClient) -> None:
    session = await _create_course_and_start_session(client, "ATT301", "room_H")
    resp = await client.get(f"/api/sessions/{session['id']}/attendance")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_mark_absent_fills_missing_students(client: AsyncClient) -> None:
    # Create course + 2 students + enroll + start session
    cr = await client.post(
        "/api/courses",
        json={"code": "ATT302", "name": "Absent Test", "professor_name": "Prof"},
    )
    course_id = cr.json()["id"]

    s1 = await client.post("/api/students", json={"name": "S1", "student_id": "ATT_S1"})
    s2 = await client.post("/api/students", json={"name": "S2", "student_id": "ATT_S2"})
    sid1, sid2 = s1.json()["id"], s2.json()["id"]

    await client.post(f"/api/courses/{course_id}/enroll", json={"student_ids": [sid1, sid2]})

    sess = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_ATT"})
    session_id = sess.json()["id"]

    resp = await client.post(f"/api/sessions/{session_id}/mark-absent")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) == 2
    assert all(r["status"] == "absent" for r in records)


async def test_adjust_attendance(client: AsyncClient) -> None:
    # Create session + student + mark absent + adjust to excused
    cr = await client.post(
        "/api/courses",
        json={"code": "ATT303", "name": "Adjust Test", "professor_name": "Prof"},
    )
    course_id = cr.json()["id"]
    sr = await client.post("/api/students", json={"name": "S3", "student_id": "ATT_S3"})
    sid = sr.json()["id"]
    await client.post(f"/api/courses/{course_id}/enroll", json={"student_ids": [sid]})
    sess = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_ADJ"})
    session_id = sess.json()["id"]

    absent_resp = await client.post(f"/api/sessions/{session_id}/mark-absent")
    record_id = absent_resp.json()[0]["id"]

    resp = await client.patch(f"/api/attendance/{record_id}", json={"status": "excused"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "excused"
    assert resp.json()["adjusted_by"] == "professor"


async def test_student_attendance_history(client: AsyncClient) -> None:
    cr = await client.post(
        "/api/courses",
        json={"code": "ATT304", "name": "History Test", "professor_name": "Prof"},
    )
    course_id = cr.json()["id"]
    sr = await client.post("/api/students", json={"name": "S4", "student_id": "ATT_S4"})
    sid = sr.json()["id"]
    await client.post(f"/api/courses/{course_id}/enroll", json={"student_ids": [sid]})
    sess = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_HIS"})
    session_id = sess.json()["id"]
    await client.post(f"/api/sessions/{session_id}/mark-absent")

    resp = await client.get(f"/api/students/{sid}/attendance-history")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) == 1
    assert history[0]["course_code"] == "ATT304"
    assert history[0]["status"] == "absent"
