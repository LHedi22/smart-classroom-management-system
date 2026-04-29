"""
Integration tests for student enrollment and face encoding API.

DeepFace is never imported here — all face encoding logic is mocked at the
service layer (face_recognition_service.enroll_student_face) rather than at
the DeepFace/cv2 import level, because enrollment.py no longer imports those
libraries directly.
"""
import io
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

FAKE_ENCODING = np.random.rand(128).astype(np.float32)


# ── helpers ───────────────────────────────────────────────────────────────

def _tiny_jpeg() -> bytes:
    """Fake image bytes — content is irrelevant; service is mocked."""
    return b"FAKE_IMAGE_BYTES_FOR_TEST"


# ── student CRUD ─────────────────────────────────────────────────────────

async def test_create_student(client: AsyncClient) -> None:
    resp = await client.post("/api/students", json={"name": "Alice", "student_id": "S001"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alice"
    assert data["student_id"] == "S001"
    assert "id" in data


async def test_create_student_duplicate_returns_409(client: AsyncClient) -> None:
    await client.post("/api/students", json={"name": "Bob", "student_id": "S002"})
    resp = await client.post("/api/students", json={"name": "Bob2", "student_id": "S002"})
    assert resp.status_code == 409


async def test_list_students(client: AsyncClient) -> None:
    await client.post("/api/students", json={"name": "Charlie", "student_id": "S003"})
    resp = await client.get("/api/students")
    assert resp.status_code == 200
    assert any(s["student_id"] == "S003" for s in resp.json())


async def test_get_student_by_id(client: AsyncClient) -> None:
    cr = await client.post("/api/students", json={"name": "Diana", "student_id": "S004"})
    sid = cr.json()["id"]
    resp = await client.get(f"/api/students/{sid}")
    assert resp.status_code == 200
    assert resp.json()["student_id"] == "S004"


async def test_get_student_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/students/nonexistent-uuid")
    assert resp.status_code == 404


# ── face enrollment ───────────────────────────────────────────────────────

async def test_enroll_face_creates_encoding(client: AsyncClient) -> None:
    cr = await client.post("/api/students", json={"name": "Eve", "student_id": "S005"})
    assert cr.status_code == 201
    student_id = cr.json()["id"]

    with (
        patch(
            "app.services.face_recognition_service.face_recognition_service.enroll_student_face",
            new_callable=AsyncMock,
            return_value={"encoding": FAKE_ENCODING.copy(), "frames_used": 1, "mode": "real"},
        ),
        patch(
            "app.services.face_recognition_service.face_recognition_service.reload_encodings",
            new_callable=AsyncMock,
        ),
    ):
        resp = await client.post(
            f"/api/students/{student_id}/enroll-face",
            files={"images": ("face.jpg", io.BytesIO(_tiny_jpeg()), "image/jpeg")},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["student_id"] == student_id
    assert data["frames_captured"] == 1
    assert "successfully" in data["message"].lower()


async def test_enroll_face_no_face_detected_returns_422(client: AsyncClient) -> None:
    cr = await client.post("/api/students", json={"name": "Frank", "student_id": "S006"})
    student_id = cr.json()["id"]

    with patch(
        "app.services.face_recognition_service.face_recognition_service.enroll_student_face",
        new_callable=AsyncMock,
        return_value={"encoding": None, "frames_used": 0, "mode": "real"},
    ):
        resp = await client.post(
            f"/api/students/{student_id}/enroll-face",
            files={"images": ("face.jpg", io.BytesIO(_tiny_jpeg()), "image/jpeg")},
        )

    assert resp.status_code == 422


async def test_enroll_face_student_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/students/does-not-exist/enroll-face",
        files={"images": ("face.jpg", io.BytesIO(_tiny_jpeg()), "image/jpeg")},
    )
    assert resp.status_code == 404


async def test_enroll_face_stub_mode_stores_placeholder(client: AsyncClient) -> None:
    """In stub mode (FACE_RECOGNITION_ENABLED=false), enrollment succeeds with a
    zeroed placeholder encoding rather than raising 503."""
    cr = await client.post("/api/students", json={"name": "Grace", "student_id": "S007"})
    student_id = cr.json()["id"]

    # _FR_AVAILABLE is already False in the test environment, so no extra patching
    # needed for the service itself — just suppress the DB reload call.
    with patch(
        "app.services.face_recognition_service.face_recognition_service.reload_encodings",
        new_callable=AsyncMock,
    ):
        resp = await client.post(
            f"/api/students/{student_id}/enroll-face",
            files={"images": ("face.jpg", io.BytesIO(_tiny_jpeg()), "image/jpeg")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["frames_captured"] == 0
    assert "stub" in data["message"].lower()


# ── FaceRecognitionService unit tests ─────────────────────────────────────

async def test_recognize_faces_returns_empty_without_library() -> None:
    from app.services.face_recognition_service import FaceRecognitionService

    with patch("app.services.face_recognition_service._FR_AVAILABLE", False):
        svc = FaceRecognitionService()
        result = svc.recognize_faces(np.zeros((480, 640, 3), dtype=np.uint8))
        assert result == []


async def test_count_heads_returns_zero_without_library() -> None:
    from app.services.face_recognition_service import FaceRecognitionService

    with patch("app.services.face_recognition_service._FR_AVAILABLE", False):
        svc = FaceRecognitionService()
        assert svc.count_heads(np.zeros((480, 640, 3), dtype=np.uint8)) == 0


async def test_reload_encodings_populates_dict(test_engine, db_session: AsyncSession) -> None:
    """reload_encodings reads FaceEncoding rows from the DB into memory."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.db_models import FaceEncoding, Student
    from app.services.face_recognition_service import FaceRecognitionService

    student = Student(name="Test Student", student_id="TEST_ENC_001")
    db_session.add(student)
    await db_session.flush()

    vec = np.random.rand(128).astype(np.float32)
    db_session.add(FaceEncoding(student_id=student.id, encoding=vec.tobytes()))
    await db_session.commit()

    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    svc = FaceRecognitionService()
    with (
        patch("app.services.face_recognition_service._FR_AVAILABLE", True),
        patch("app.services.face_recognition_service.AsyncSessionLocal", TestSessionLocal),
    ):
        await svc.reload_encodings()

    assert student.id in svc.known_encodings
    np.testing.assert_allclose(svc.known_encodings[student.id], vec)
