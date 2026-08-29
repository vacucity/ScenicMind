import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .modules.agent import router as agent_router
from .modules.module_one import router as module_one_router
from .modules.module_two import router as module_two_router

app = FastAPI(
    title="ScenicMind API",
    version="0.1.0",
    description="人流量预测系统的后端接口骨架。",
)

app.include_router(agent_router)
app.include_router(module_one_router)
app.include_router(module_two_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
