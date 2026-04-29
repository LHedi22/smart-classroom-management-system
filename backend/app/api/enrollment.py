import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.database import get_db
from app.models.db_models import FaceEncoding, Professor, Student
from app.models.schemas import EnrollFaceResponse, StudentCreate, StudentResponse
from app.services.face_recognition_service import face_recognition_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ── POST /api/students ────────────────────────────────────────────────────

@router.post("/students", response_model=StudentResponse, status_code=201)
async def create_student(
    body: StudentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Professor = Depends(require_admin),
) -> StudentResponse:
    existing = (
        await db.execute(select(Student).where(Student.student_id == body.student_id))
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="Student ID already exists")

    student = Student(name=body.name, student_id=body.student_id)
    db.add(student)
    await db.flush()
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


# ── DELETE /api/students/{id} ────────────────────────────────────────────

@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Professor = Depends(require_admin),
) -> None:
    student = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    await db.delete(student)
    await db.commit()


# ── POST /api/students/{id}/enroll-face ──────────────────────────────────

@router.post("/students/{student_id}/enroll-face", response_model=EnrollFaceResponse)
async def enroll_face(
    student_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    images: list[UploadFile] = File(..., description="Up to 5 face images"),
) -> EnrollFaceResponse:
    student = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if len(images) > 5:
        raise HTTPException(status_code=422, detail="Maximum 5 images allowed")

    images_bytes = [await img.read() for img in images]

    result = await face_recognition_service.enroll_student_face(student_id, images_bytes)

    if result["encoding"] is None:
        raise HTTPException(status_code=422, detail="No valid face detected in any uploaded image")

    existing_enc = (
        await db.execute(select(FaceEncoding).where(FaceEncoding.student_id == student_id))
    ).scalar_one_or_none()
    if existing_enc:
        await db.delete(existing_enc)

    db.add(FaceEncoding(student_id=student_id, encoding=result["encoding"].tobytes()))
    await db.commit()

    await face_recognition_service.reload_encodings()

    frames = result["frames_used"]
    mode = result["mode"]

    if mode == "stub":
        logger.info("Enrolled stub face for student %s (placeholder encoding)", student_id)
        return EnrollFaceResponse(
            student_id=student_id,
            frames_captured=0,
            message="Face enrollment stub: placeholder encoding stored (FACE_RECOGNITION_ENABLED=false)",
        )

    logger.info("Enrolled face for student %s (%d images used)", student_id, frames)
    return EnrollFaceResponse(
        student_id=student_id,
        frames_captured=frames,
        message=f"Successfully enrolled {frames} face image(s)",
    )
