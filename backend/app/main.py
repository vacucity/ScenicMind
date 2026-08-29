from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import initialize_database
from .routers.agent import router as agent_router
from .routers.analyses import router as analyses_router
from .routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="ScenicMind智景 API",
    version="0.2.0",
    description="注册登录、客户数据上传、FlowStack分析与动态看板接口。",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(analyses_router)
app.include_router(agent_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "scenicmind-api", "version": "0.2.0"}

