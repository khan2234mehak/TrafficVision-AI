from __future__ import annotations

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.entities import User

bearer = HTTPBearer(auto_error=False)


def _user_from_token(db: Session, token: str | None) -> User:
    err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated. Please sign in again.",
                        headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise err
    payload = decode_token(token)
    if not payload:
        raise err
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise err
    return user


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    return _user_from_token(db, creds.credentials if creds else None)


def current_user_media(request: Request, token: str | None = Query(default=None),
                       creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    """For <img>/<video> tags that cannot send an Authorization header: also accepts ?token=."""
    return _user_from_token(db, creds.credentials if creds else token)


ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}


def require_role(min_role: str, media: bool = False):
    base = current_user_media if media else current_user

    def dep(user: User = Depends(base)) -> User:
        if ROLE_RANK.get(user.role, -1) < ROLE_RANK[min_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"This action requires the '{min_role}' role.")
        return user

    return dep


viewer = require_role("viewer")
operator = require_role("operator")
admin = require_role("admin")
