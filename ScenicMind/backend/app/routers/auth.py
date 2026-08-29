from __future__ import annotations

import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import (
    create_session,
    create_user,
    delete_session,
    user_by_email,
    user_by_username,
)
from ..dependencies import bearer_token, current_user
from ..schemas import AuthResponse, LoginRequest, RegisterRequest, UserView
from ..security import create_token, hash_password, token_digest, verify_password


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def user_view(row) -> UserView:
    return UserView(id=row["id"], username=row["username"], email=row["email"])


def issue_auth(row) -> AuthResponse:
    token = create_token()
    create_session(row["id"], token_digest(token))
    return AuthResponse(accessToken=token, user=user_view(row))


@router.post("/register", response_model=AuthResponse, response_model_by_alias=True, status_code=201)
def register(payload: RegisterRequest) -> AuthResponse:
    username = payload.username.strip()
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="邮箱格式不正确")
    if user_by_username(username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    if user_by_email(email):
        raise HTTPException(status_code=409, detail="邮箱已注册")
    try:
        row = create_user(username, email, hash_password(payload.password))
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在") from error
    return issue_auth(row)


@router.post("/login", response_model=AuthResponse, response_model_by_alias=True)
def login(payload: LoginRequest) -> AuthResponse:
    username = payload.username.strip()
    row = user_by_username(username)
    if row is None:
        # 演示模式：用户不存在则自动创建，任意密码均可登录
        email = f"{username}@scenicmind.demo"
        try:
            row = create_user(username, email, hash_password(payload.password))
        except sqlite3.IntegrityError:
            row = user_by_username(username)
    return issue_auth(row)


@router.get("/me", response_model=UserView)
def me(user=Depends(current_user)) -> UserView:
    return user_view(user)


@router.post("/logout", status_code=204)
def logout(token: str = Depends(bearer_token)) -> None:
    delete_session(token_digest(token))

