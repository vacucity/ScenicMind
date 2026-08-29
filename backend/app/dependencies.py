from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from .database import user_by_session
from .security import token_digest


def bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少登录凭证")
    return authorization.split(" ", 1)[1].strip()


def current_user(token: str = Depends(bearer_token)):
    user = user_by_session(token_digest(token))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")
    return user
