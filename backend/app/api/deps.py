from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db_models import Professor, ProfessorRole
from app.services.auth import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Returned when REQUIRE_AUTH=false and no token is supplied — preserves
# backward compatibility with seed.py, e2e tests, and the pre-auth frontend.
_SYSTEM_ADMIN = Professor(
    id="00000000-0000-0000-0000-000000000000",
    name="System",
    email="system@local",
    hashed_password="",
    role=ProfessorRole.admin,
)


async def get_current_professor(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Professor:
    if token is None:
        if settings.require_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return _SYSTEM_ADMIN

    payload = decode_token(token)
    professor_id: str | None = payload.get("sub")
    if not professor_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    professor = await db.get(Professor, professor_id)
    if professor is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Professor not found")
    return professor


async def require_admin(
    current: Professor = Depends(get_current_professor),
) -> Professor:
    if current.role != ProfessorRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current
