"""
Tests for the attendance API.

Covers: get session attendance, PATCH adjust status, POST mark-absent.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ── helpers ───────────────────────────────────────────────────────────────

async def _setup_session_with_students(
    client: AsyncClient,
    course_code: str,
    room_id: str,
    student_defs: list[tuple[str, str]],
) -> tuple[str, list[str]]:
    """Create course, students, enroll them, start session. Returns (session_id, [student_ids])."""
    cr = await client.post(
        "/api/courses",
        json={"code": course_code, "name": f"Course {course_code}", "professor_name": "Prof"},
    )
    course_id = cr.json()["id"]

    student_ids = []
    for name, inst_id in student_defs:
        sr = await client.post("/api/students", json={"name": name, "student_id": inst_id})
        student_ids.append(sr.json()["id"])

    await client.post(f"/api/courses/{course_id}/enroll", json={"student_ids": student_ids})

    sess = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": room_id})
    session_id = sess.json()["id"]
    return session_id, student_ids


# ── GET attendance ────────────────────────────────────────────────────────

async def test_get_attendance_returns_correct_records(client: AsyncClient) -> None:
    session_id, _ = await _setup_session_with_students(
        client, "ATT_GET1", "room_att_get1", [("Alice", "ATT_GET_A"), ("Bob", "ATT_GET_B")]
    )
    # Mark all absent so we have attendance records
    await client.post(f"/api/sessions/{session_id}/mark-absent")

    resp = await client.get(f"/api/sessions/{session_id}/attendance")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) == 2
    # Each record should have student_name and student_number
    for r in records:
        assert "student_name" in r
        assert "student_number" in r
        assert r["session_id"] == session_id


async def test_get_attendance_empty_session(client: AsyncClient) -> None:
    session_id, _ = await _setup_session_with_students(
        client, "ATT_GET2", "room_att_get2", [("Carol", "ATT_GET_C")]
    )
    resp = await client.get(f"/api/sessions/{session_id}/attendance")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_attendance_session_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/sessions/no-such-session/attendance")
    assert resp.status_code == 404


# ── PATCH adjust ─────────────────────────────────────────────────────────

async def test_patch_attendance_updates_status_and_sets_adjusted_by(client: AsyncClient) -> None:
    session_id, _ = await _setup_session_with_students(
        client, "ATT_ADJ1", "room_att_adj1", [("Dave", "ATT_ADJ_D")]
    )
    # Create an absent record first
    absent_resp = await client.post(f"/api/sessions/{session_id}/mark-absent")
    record_id = absent_resp.json()[0]["id"]

    # Adjust to excused
    patch_resp = await client.patch(f"/api/attendance/{record_id}", json={"status": "excused"})
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["status"] == "excused"
    assert data["adjusted_by"] == "professor"
    assert data["adjusted_at"] is not None
    assert data["moodle_synced"] is False


async def test_patch_attendance_to_late(client: AsyncClient) -> None:
    session_id, _ = await _setup_session_with_students(
        client, "ATT_ADJ2", "room_att_adj2", [("Eve", "ATT_ADJ_E")]
    )
    absent_resp = await client.post(f"/api/sessions/{session_id}/mark-absent")
    record_id = absent_resp.json()[0]["id"]

    resp = await client.patch(f"/api/attendance/{record_id}", json={"status": "late"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "late"


async def test_patch_attendance_invalid_status_returns_422(client: AsyncClient) -> None:
    session_id, _ = await _setup_session_with_students(
        client, "ATT_ADJ3", "room_att_adj3", [("Frank", "ATT_ADJ_F")]
    )
    absent_resp = await client.post(f"/api/sessions/{session_id}/mark-absent")
    record_id = absent_resp.json()[0]["id"]

    resp = await client.patch(f"/api/attendance/{record_id}", json={"status": "unknown_status"})
    assert resp.status_code == 422


async def test_patch_attendance_not_found(client: AsyncClient) -> None:
    resp = await client.patch("/api/attendance/no-such-record", json={"status": "excused"})
    assert resp.status_code == 404


# ── POST mark-absent ─────────────────────────────────────────────────────

async def test_mark_absent_creates_absent_records_for_all_enrolled(client: AsyncClient) -> None:
    session_id, student_ids = await _setup_session_with_students(
        client,
        "ATT_MAB1",
        "room_att_mab1",
        [("Grace", "ATT_MAB_G"), ("Hank", "ATT_MAB_H"), ("Iris", "ATT_MAB_I")],
    )
    resp = await client.post(f"/api/sessions/{session_id}/mark-absent")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) == 3
    assert all(r["status"] == "absent" for r in records)
    created_student_ids = {r["student_id"] for r in records}
    assert created_student_ids == set(student_ids)


async def test_mark_absent_skips_already_recorded_students(client: AsyncClient) -> None:
    """Students who already have attendance records must not get duplicate absent entries."""
    session_id, student_ids = await _setup_session_with_students(
        client,
        "ATT_MAB2",
        "room_att_mab2",
        [("Jack", "ATT_MAB_J"), ("Kate", "ATT_MAB_K")],
    )
    # First call marks both absent
    first = await client.post(f"/api/sessions/{session_id}/mark-absent")
    assert len(first.json()) == 2

    # Second call should find both already recorded — returns empty list
    second = await client.post(f"/api/sessions/{session_id}/mark-absent")
    assert second.status_code == 200
    assert second.json() == []


async def test_mark_absent_session_not_found(client: AsyncClient) -> None:
    resp = await client.post("/api/sessions/no-such-session/mark-absent")
    assert resp.status_code == 404
