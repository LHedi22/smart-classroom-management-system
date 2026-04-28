import io
import logging
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import FaceEncoding, Student
from app.models.schemas import EnrollFaceResponse, StudentCreate, StudentResponse
from app.services.face_recognition_service import face_recognition_service

logger = logging.getLogger(__name__)

# Optional imports — face_recognition may not be available outside RPi
try:
    import face_recognition as fr  # type: ignore[import]
    _FR_AVAILABLE = True
except ImportError:
    fr = None  # type: ignore[assignment]
    _FR_AVAILABLE = False

try:
    import cv2  # type: ignore[import]
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False

router = APIRouter()


# ── POST /api/students ────────────────────────────────────────────────────

@router.post("/students", response_model=StudentResponse, status_code=201)
async def create_student(
    body: StudentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudentResponse:
    existing = (
        await db.execute(select(Student).where(Student.student_id == body.student_id))
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="Student ID already exists")

    student = Student(name=body.name, student_id=body.student_id)
    db.add(student)
    await db.flush()  # get the server-generated UUID before commit
    await db.refresh(student)
    await db.commit()
    return StudentResponse.model_validate(student)


# ── GET /api/students ─────────────────────────────────────────────────────

@router.get("/students", response_model=list[StudentResponse])
async def list_students(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[StudentResponse]:
    rows = (await db.execute(select(Student).order_by(Student.name))).scalars().all()
    return [StudentResponse.model_validate(r) for r in rows]


# ── GET /api/students/{id} ────────────────────────────────────────────────

@router.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudentResponse:
    student = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return StudentResponse.model_validate(student)


# ── POST /api/students/{id}/enroll-face ──────────────────────────────────

@router.post("/students/{student_id}/enroll-face", response_model=EnrollFaceResponse)
async def enroll_face(
    student_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    images: list[UploadFile] = File(..., description="Up to 5 face images"),
) -> EnrollFaceResponse:
    # Verify student exists
    student = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if len(images) > 5:
        raise HTTPException(status_code=422, detail="Maximum 5 images allowed")

    if not _FR_AVAILABLE or not _CV2_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="face_recognition library not available on this server",
        )

    encodings: list[np.ndarray] = []

    for upload in images:
        raw = await upload.read()
        # Decode bytes → numpy BGR frame
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            logger.warning("Could not decode image %s — skipping", upload.filename)
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_encs = fr.face_encodings(rgb)
        if not face_encs:
            logger.warning("No face detected in %s — skipping", upload.filename)
            continue

        encodings.append(face_encs[0])  # take the first (largest) face

    if not encodings:
        raise HTTPException(status_code=422, detail="No valid face detected in any uploaded image")

    # Average all encodings into one representative vector
    mean_encoding: np.ndarray = np.mean(encodings, axis=0)

    # Delete any existing encoding for this student (re-enrollment)
    existing_enc = (
        await db.execute(select(FaceEncoding).where(FaceEncoding.student_id == student_id))
    ).scalar_one_or_none()
    if existing_enc:
        await db.delete(existing_enc)

    db.add(FaceEncoding(student_id=student_id, encoding=mean_encoding.tobytes()))
    await db.commit()

    # Refresh the in-memory recognition service
    await face_recognition_service.reload_encodings()

    logger.info("Enrolled face for student %s (%d images used)", student_id, len(encodings))
    return EnrollFaceResponse(
        student_id=student_id,
        frames_captured=len(encodings),
        message=f"Successfully enrolled {len(encodings)} face image(s)",
    )
