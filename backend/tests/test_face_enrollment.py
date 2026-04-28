"""
Integration tests for student enrollment and face encoding API.

face_recognition and cv2 are mocked — tests run without dlib or a camera.
"""
import io
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

FAKE_ENCODING = np.random.rand(128).astype(np.float64)


# ── helpers ───────────────────────────────────────────────────────────────

def _tiny_jpeg() -> bytes:
    """Fake image bytes — cv2.imdecode is always mocked so content is irrelevant."""
    return b"FAKE_IMAGE_BYTES_FOR_TEST"


def _mock_cv2():
    """Return a MagicMock that acts like cv2 for enrollment purposes."""
    from unittest.mock import MagicMock
    m = MagicMock()
    m.imdecode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    m.cvtColor.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    m.IMREAD_COLOR = 1
    m.COLOR_BGR2RGB = 4
    return m


def _mock_fr(encoding: np.ndarray | None = None):
    """Return a MagicMock for face_recognition."""
    from unittest.mock import MagicMock
    enc = encoding if encoding is not None else FAKE_ENCODING.copy()
    m = MagicMock()
    m.face_encodings.return_value = [enc]
    return m


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
        patch("app.api.enrollment._FR_AVAILABLE", True),
        patch("app.api.enrollment._CV2_AVAILABLE", True),
        patch("app.api.enrollment.fr", _mock_fr()),
        patch("app.api.enrollment.cv2", _mock_cv2()),
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
    assert "enrolled" in data["message"].lower() or "successfully" in data["message"].lower()


async def test_enroll_face_no_face_detected_returns_422(client: AsyncClient) -> None:
    cr = await client.post("/api/students", json={"name": "Frank", "student_id": "S006"})
    student_id = cr.json()["id"]

    no_face_fr = _mock_fr()
    no_face_fr.face_encodings.return_value = []  # no face found

    with (
        patch("app.api.enrollment._FR_AVAILABLE", True),
        patch("app.api.enrollment._CV2_AVAILABLE", True),
        patch("app.api.enrollment.fr", no_face_fr),
        patch("app.api.enrollment.cv2", _mock_cv2()),
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


async def test_enroll_face_library_unavailable(client: AsyncClient) -> None:
    cr = await client.post("/api/students", json={"name": "Grace", "student_id": "S007"})
    student_id = cr.json()["id"]

    with (
        patch("app.api.enrollment._FR_AVAILABLE", False),
        patch("app.api.enrollment._CV2_AVAILABLE", False),
    ):
        resp = await client.post(
            f"/api/students/{student_id}/enroll-face",
            files={"images": ("face.jpg", io.BytesIO(_tiny_jpeg()), "image/jpeg")},
        )

    assert resp.status_code == 503


# ── FaceRecognitionService unit tests ─────────────────────────────────────

async def test_recognize_faces_returns_empty_without_library() -> None:
    from app.services.face_recognition_service import FaceRecognitionService

    with patch("app.services.face_recognition_service._FR_AVAILABLE", False):
        svc = FaceRecognitionService()
        result = svc.recognize_faces(np.zeros((480, 640, 3), dtype=np.uint8))
        assert result == []


async def test_count_heads_returns_zero_without_cv2() -> None:
    from app.services.face_recognition_service import FaceRecognitionService

    with patch("app.services.face_recognition_service._CV2_AVAILABLE", False):
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

    vec = np.random.rand(128).astype(np.float64)
    db_session.add(FaceEncoding(student_id=student.id, encoding=vec.tobytes()))
    await db_session.commit()

    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    svc = FaceRecognitionService()
    with patch("app.services.face_recognition_service.AsyncSessionLocal", TestSessionLocal):
        await svc.reload_encodings()

    assert student.id in svc.known_encodings
    np.testing.assert_allclose(svc.known_encodings[student.id], vec)
