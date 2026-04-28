"""
Tests for the sessions API.

Covers: start, end, conflict, list, and get endpoints.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ── helpers ───────────────────────────────────────────────────────────────

async def _make_course(client: AsyncClient, code: str) -> str:
    resp = await client.post(
        "/api/courses",
        json={"code": code, "name": f"Course {code}", "professor_name": "Prof Test"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Start session ─────────────────────────────────────────────────────────

async def test_start_session_creates_and_returns_session(client: AsyncClient) -> None:
    course_id = await _make_course(client, "SESS_A01")
    resp = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_sa1"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "active"
    assert data["course_id"] == course_id
    assert data["room_id"] == "room_sa1"
    assert "id" in data
    assert data["ended_at"] is None


async def test_start_session_unknown_course_returns_404(client: AsyncClient) -> None:
    resp = await client.post("/api/sessions/start", json={"course_id": "no-such-id", "room_id": "room_sa2"})
    assert resp.status_code == 404


async def test_start_session_conflict_active_returns_409(client: AsyncClient) -> None:
    course_id = await _make_course(client, "SESS_A02")
    # First session — succeeds
    await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_sa3"})
    # Second session in same room — conflict
    course_id2 = await _make_course(client, "SESS_A03")
    resp = await client.post("/api/sessions/start", json={"course_id": course_id2, "room_id": "room_sa3"})
    assert resp.status_code == 409
    assert "already active" in resp.json()["detail"].lower()


# ── End session ───────────────────────────────────────────────────────────

async def test_end_session_updates_status_to_ended(client: AsyncClient) -> None:
    course_id = await _make_course(client, "SESS_B01")
    start = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_sb1"})
    session_id = start.json()["id"]

    resp = await client.post(f"/api/sessions/{session_id}/end")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ended"
    assert data["ended_at"] is not None


async def test_end_session_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.post("/api/sessions/no-such-id/end")
    assert resp.status_code == 404


async def test_end_session_already_ended_returns_409(client: AsyncClient) -> None:
    course_id = await _make_course(client, "SESS_B02")
    start = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_sb2"})
    session_id = start.json()["id"]

    await client.post(f"/api/sessions/{session_id}/end")
    resp = await client.post(f"/api/sessions/{session_id}/end")
    assert resp.status_code == 409


# ── Get / List sessions ───────────────────────────────────────────────────

async def test_get_session_returns_summary(client: AsyncClient) -> None:
    course_id = await _make_course(client, "SESS_C01")
    start = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_sc1"})
    session_id = start.json()["id"]

    resp = await client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session_id
    assert "present_count" in data
    assert "total_students" in data
    assert data["present_count"] == 0


async def test_get_session_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/api/sessions/no-such-session")
    assert resp.status_code == 404


async def test_list_sessions_includes_created(client: AsyncClient) -> None:
    course_id = await _make_course(client, "SESS_D01")
    start = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_sd1"})
    session_id = start.json()["id"]

    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert session_id in ids


async def test_list_sessions_status_filter(client: AsyncClient) -> None:
    course_id = await _make_course(client, "SESS_D02")
    start = await client.post("/api/sessions/start", json={"course_id": course_id, "room_id": "room_sd2"})
    session_id = start.json()["id"]
    await client.post(f"/api/sessions/{session_id}/end")

    resp = await client.get("/api/sessions?status=ended")
    assert resp.status_code == 200
    assert all(s["status"] == "ended" for s in resp.json())
