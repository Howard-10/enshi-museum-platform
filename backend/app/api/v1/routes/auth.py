from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession
from app.db.models.core import User
from app.schemas.auth import AuthCredentials, AuthResponse, AuthUserRead, RegisterRequest
from app.services.auth import (
    create_access_token,
    hash_password,
    normalize_email,
    valid_email,
    verify_password,
)

router = APIRouter()


def _user_read(user: User) -> AuthUserRead:
    return AuthUserRead(id=user.id, email=user.email, display_name=user.display_name, role=user.role)


def _validate_email(email: str) -> str:
    normalized = normalize_email(email)
    if not valid_email(normalized):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请输入有效的邮箱地址。")
    return normalized


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, session: DbSession) -> AuthResponse:
    email = _validate_email(request.email)
    display_name = request.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请输入昵称。")
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="这个邮箱已经注册，请直接登录。")
    user = User(email=email, display_name=display_name, password_hash=hash_password(request.password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="这个邮箱已经注册，请直接登录。") from error
    await session.refresh(user)
    return AuthResponse(access_token=create_access_token(user.id), user=_user_read(user))


@router.post("/login", response_model=AuthResponse)
async def login(request: AuthCredentials, session: DbSession) -> AuthResponse:
    email = _validate_email(request.email)
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码不正确。")
    return AuthResponse(access_token=create_access_token(user.id), user=_user_read(user))


@router.get("/me", response_model=AuthUserRead)
async def current_user(user: CurrentUser) -> AuthUserRead:
    return _user_read(user)
