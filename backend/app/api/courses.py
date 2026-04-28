from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import Course, Student
from app.models.schemas import CourseCreate, CourseEnrollRequest, CourseResponse

router = APIRouter()


@router.get("", response_model=list[CourseResponse])
async def list_courses(db: AsyncSession = Depends(get_db)) -> list[Course]:
    result = await db.execute(select(Course).order_by(Course.code))
    return list(result.scalars().all())


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(body: CourseCreate, db: AsyncSession = Depends(get_db)) -> Course:
    existing = await db.execute(select(Course).where(Course.code == body.code))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Course code already exists")
    course = Course(**body.model_dump())
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: str, db: AsyncSession = Depends(get_db)) -> Course:
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/{course_id}/enroll", response_model=CourseResponse)
async def enroll_students(
    course_id: str,
    body: CourseEnrollRequest,
    db: AsyncSession = Depends(get_db),
) -> Course:
    result = await db.execute(
        select(Course).where(Course.id == course_id).options(selectinload(Course.students))
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    existing_ids = {s.id for s in course.students}
    for sid in body.student_ids:
        if sid in existing_ids:
            continue
        student = await db.get(Student, sid)
        if student is None:
            raise HTTPException(status_code=404, detail=f"Student {sid} not found")
        course.students.append(student)

    await db.commit()
    return course
