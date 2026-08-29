from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]

# 本地工作区已经携带 FlowStack 的科学计算依赖。将它加入导入路径，
# 使后端在开发环境中可以直接加载现有模型；正式部署仍以 pyproject 为准。
LOCAL_DEPS = WORKSPACE_ROOT / ".deps"
if LOCAL_DEPS.exists() and str(LOCAL_DEPS) not in sys.path:
    sys.path.insert(0, str(LOCAL_DEPS))
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

RUNTIME_DIR = Path(os.getenv("SCENICMIND_RUNTIME_DIR", str(BACKEND_ROOT / "runtime"))).resolve()
MODEL_DIR = Path(
    os.getenv(
        "SCENICMIND_MODEL_DIR",
        str(WORKSPACE_ROOT / "artifacts" / "flowstack" / "current" / "model"),
    )
).resolve()
DATABASE_PATH = RUNTIME_DIR / "scenicmind.sqlite3"
UPLOAD_DIR = RUNTIME_DIR / "uploads"

RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

