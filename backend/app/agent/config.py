"""Agent 模块统一配置 —— API Key 集中管理，便于替换和扩展。

Key 来源优先级：环境变量 AGENT_API_KEY > 本文件默认值。
黑客松阶段：5 个 Agent 共用一个 Key + 一个 provider，后期扩展时
只需在此文件增加条目并按 agent_name 取用。
"""

from __future__ import annotations

import os

# ===== 统一 API Key（环境变量优先） =====
# 请通过环境变量 AGENT_API_KEY（或 backend/.env）注入，勿将密钥硬编码进仓库。
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")

# ===== LLM Provider 配置（OpenAI 兼容协议） =====
# 服务地址与模型名通过环境变量 AGENT_LLM_BASE_URL / AGENT_LLM_MODEL 注入，
# 默认留空，避免把第三方中转商地址硬编码进仓库。
AGENT_LLM_BASE_URL = os.getenv("AGENT_LLM_BASE_URL", "")
AGENT_LLM_MODEL = os.getenv("AGENT_LLM_MODEL", "")
AGENT_LLM_TIMEOUT = 90
AGENT_LLM_MAX_TOKENS = 4000

# ===== Agent 注册表（动态扩展：新增 Agent 只需在此登记） =====
AGENT_REGISTRY: dict[str, dict] = {
    "coordinator": {"role": "编排", "uses_llm": True},
    "collector": {"role": "数据采集", "uses_llm": False},
    "analyst": {"role": "分析", "uses_llm": True},
    "writer": {"role": "撰写", "uses_llm": True},
    "reviewer": {"role": "审核", "uses_llm": True},
}


def llm_headers() -> dict[str, str]:
    """统一的请求头（所有走 LLM 的 Agent 共用）。"""
    return {
        "Authorization": f"Bearer {AGENT_API_KEY}",
        "Content-Type": "application/json",
    }
