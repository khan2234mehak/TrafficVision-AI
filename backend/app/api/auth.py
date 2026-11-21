from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import admin, current_user
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.entities import User
from app.schemas.schemas import LoginIn, RegisterIn, RoleIn, TokenOut, UserOut
from app.services.common import log_activity

router = APIRouter(tags=["auth"])


@router.post("/api/auth/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower().strip()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    # Public sign-up always creates a read-only viewer. An admin can promote the account.
    user = User(email=email, username=data.username.strip(), hashed_password=hash_password(data.password), role="viewer")
    db.add(user)
    db.commit()
    log_activity(db, user, "register", "New account", request)
    return TokenOut(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.post("/api/auth/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower().strip()))
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled.")
    log_activity(db, user, "login", "", request)
    return TokenOut(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.get("/api/users", response_model=list[UserOut])
def list_users(_: User = Depends(admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.id)))


@router.put("/api/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: int, data: RoleIn, request: Request, me: User = Depends(admin), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found.")
    if target.id == me.id and data.role != "admin":
        raise HTTPException(400, "You cannot remove your own admin role.")
    target.role = data.role
    db.commit()
    log_activity(db, me, "role_change", f"{target.email} -> {data.role}", request)
    return target
