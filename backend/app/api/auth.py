from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_professor, require_admin
from app.database import get_db
from app.models.db_models import Professor
from app.models.schemas import LoginResponse, ProfessorResponse
from app.services.auth import create_access_token, verify_password

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    result = await db.execute(select(Professor).where(Professor.email == form.username))
    professor = result.scalar_one_or_none()
    if professor is None or not verify_password(form.password, professor.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": professor.id, "role": professor.role.value})
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        role=professor.role.value,
        professor_id=professor.id,
        name=professor.name,
    )


@router.get("/me", response_model=ProfessorResponse)
async def me(current: Professor = Depends(get_current_professor)) -> Professor:
    return current


@router.post("/logout")
async def logout() -> dict:
    # JWT is stateless — client is responsible for dropping the token.
    return {"ok": True}


@router.get("/professors", response_model=list[ProfessorResponse])
async def list_professors(
    db: AsyncSession = Depends(get_db),
    _current: Professor = Depends(get_current_professor),
) -> list[Professor]:
    result = await db.execute(select(Professor).order_by(Professor.name))
    return result.scalars().all()
