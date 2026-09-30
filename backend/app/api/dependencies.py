from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.core import User
from app.db.session import get_db_session
from app.services.auth import InvalidAccessToken, verify_access_token

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: DbSession,
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = verify_access_token(credentials.credentials)
    except InvalidAccessToken as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录。",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录用户不存在，请重新登录。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: DbSession,
) -> User | None:
    """Resolve a visitor when supplied, while allowing public kiosk mode.

    A valid token still enables user-scoped conversations in public mode. When
    auth is disabled, an absent or stale token is treated as an anonymous
    visitor instead of blocking the public museum experience.
    """

    if credentials is None:
        if settings.auth_required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="请先登录。",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None
    try:
        user_id = verify_access_token(credentials.credentials)
    except InvalidAccessToken as error:
        if not settings.auth_required:
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录。",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        if not settings.auth_required:
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录用户不存在，请重新登录。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


OptionalCurrentUser = Annotated[User | None, Depends(get_optional_user)]
