# 智景 ScenicMind · 多 Agent 协作报告系统方案

> 版本：v1.0 · 2026-08-29
> 定位：接入现有 ScenicMind 全栈项目，多 Agent 协作生成景区经营分析报告

---

## 一、目标与边界

**核心目标**：用户（景区管理人员）一键生成高质量经营分析报告，报告基于项目已有的三个数据维度交叉验证，可指导实际经营决策。

**三个数据维度**（项目已有，直接复用）：

| 维度 | 数据来源 | 现有 API |
|---|---|---|
| 预测客流量 | `analyze_visitors()` | `GET /api/v1/analyses/{id}` |
| 指标蓝图 | `compute_indicators()` 8 大模块 | `GET /api/v1/analyses/{id}/indicators` |
| 特征贡献度 | `ImportanceService` + semantic_groups | `GET /api/v1/analyses/{id}/importance` |

**不做的事**：
- 不做多景区对比（当前单景区单数据集）
- 不做实时流式推理（离线批式生成，报告缓存复用）
- 不引入向量数据库/RAG（数据结构化程度高，Tool 直接取数即可）

---

## 二、多 Agent 架构

### 协作拓扑（LangGraph 状态图）

```
用户发起报告请求
      │
      ▼
┌─────────────┐    路由：按报告类型分派
│ Coordinator │◄──────────────────────────┐
│  (编排Agent) │                           │
└──────┬──────┘                           │
       │ 派发采集任务                       │
       ▼                                  │
┌─────────────┐  tool_forecast()          │  审核不通过
│ DataCollector│  tool_indicators()       │  修订循环(≤2次)
│ (采集Agent)  │  tool_importance()       │
└──────┬──────┘                           │
       │ 三维度数据包                       │
       ▼                                  │
┌─────────────┐                           │
│  Analyst    │ 交叉验证/风险识别/机会发现   │
│ (分析Agent)  │ 输出结构化分析要点          │
└──────┬──────┘                           │
       ▼                                  │
┌─────────────┐                           │
│   Writer    │ Markdown 报告撰写           │
│ (撰写Agent)  │ 业务语言，非技术术语        │
└──────┬──────┘                           │
       ▼                                  │
┌─────────────┐   通过                     │
│  Reviewer   │──────────────► 报告交付    │
│ (审核Agent)  │ 校验数值/逻辑/完整性       │
└─────────────┘
```

### Agent 角色定义

| Agent | 职责 | LLM 用途 | 输出契约 |
|---|---|---|---|
| **Coordinator** | 解析用户意图（报告类型/时间范围），编排流程，失败重试 | 意图分类 + 路由 | `{report_type, horizon, checklist}` |
| **DataCollector** | 调 3 个 Tool 拉取三维度数据，做数据完备性检查（缺字段时降级标注） | 无（纯确定性 Tool 调用） | `{forecast, indicators, importance, gaps[]}` |
| **Analyst** | 三维度交叉分析：预测峰值 vs 承载上限（拥堵预警）、贡献度 top 主题 vs 指标印证、异常定位 | 推理主力 | `{insights[], risks[], actions[]}` 每条带数据引用 |
| **Writer** | 把分析要点转成管理者可读的 Markdown 报告，固定章节结构 | 文本生成 | Markdown 文本 |
| **Reviewer** | 校验报告中数值与数据包一致（防幻觉）、章节完整性、建议可执行性 | LLM-as-judge + 数值比对 | `{pass: bool, issues[]}` |

**关键设计决策**：
1. **DataCollector 不用 LLM**——三个 Tool 是确定性的函数调用，省 token 且零幻觉
2. **Reviewer 数值校验是硬规则**——报告中的每个数字必须能在数据包中找到，找不到即打回（防 LLM 编造数据）
3. **修订循环上限 2 次**——避免无限循环，2 次不通过则带警告交付

### 报告类型（Coordinator 路由）

| 类型 | 触发 | 侧重 |
|---|---|---|
| `daily_brief` | 每日/默认 | 明日预测 + 风险提示 + 当日动作 |
| `deep_dive` | 经营分析页"问 Agent" | 单一主题深挖（如节假日效应） |
| `periodic` | 用户选周期（周/月） | 趋势回顾 + 下期展望 + 资源规划建议 |

---

## 三、工具层（契合现有后端）

```python
# backend/app/agent/tools.py —— 直接包装现有 service，零重复开发
from ..services.forecast import ...
from ..services.indicators import compute_indicators
from ..database import analysis_by_id

def tool_forecast(analysis_id: str, horizon: int = 7) -> dict:
    """预测客流量：future_points + horizons 摘要 + metrics"""

def tool_indicators(analysis_id: str) -> dict:
    """指标蓝图：8 大模块（客流/承载/节假日/天气/交通/热度/质量）"""

def tool_importance(analysis_id: str) -> dict:
    """特征贡献度：semantic_groups 业务主题占比"""
```

三个 Tool 的数据从 SQLite `analyses` 表读（已有 `result_json` / `indicators_json` / `importance_json` 三列），**无需重新计算**，报告生成延迟主要来自 LLM 推理。

---

## 四、API 设计

### 新增路由（backend/app/routers/agent.py）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/v1/agent/report` | POST | 发起报告生成（异步：立即返回 report_id） |
| `/api/v1/agent/report/{id}` | GET | 轮询报告状态/结果 |
| `/api/v1/agent/reports` | GET | 历史报告列表 |
| `/api/v1/agent/chat` | POST | 对话式问答（现有 AgentChat 升级，流式可选） |

### 数据表（增量迁移）

```sql
CREATE TABLE IF NOT EXISTS agent_reports (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    analysis_id TEXT NOT NULL,
    report_type TEXT NOT NULL,          -- daily_brief / deep_dive / periodic
    status TEXT NOT NULL,               -- pending / running / done / failed
    question TEXT,                       -- deep_dive 时的主题问题
    markdown TEXT,                       -- 报告正文
    trace_json TEXT,                     -- Agent 执行轨迹（调试/展示用）
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

### 报告生成流程

1. `POST /agent/report` → 校验登录 → 写 `agent_reports`(pending) → 后台线程启动 LangGraph 工作流
2. 工作流执行：Coordinator → DataCollector → Analyst → Writer → Reviewer（修订循环）
3. 每阶段状态写入 `trace_json`（前端可展示 Agent 协作过程）
4. 完成 → `status=done` + `markdown` 落库
5. 前端轮询 `GET /agent/report/{id}` 展示

---

## 五、前端设计

### 新增"Agent 报告"页面（第四视图）

侧边栏变为四项：**数据看板 / 指标蓝图 / 经营分析 / Agent 报告**

```
┌────────────────────────────────────────────┐
│ Agent 报告                    [生成新报告]  │
├──────────────┬─────────────────────────────┤
│ 报告列表(左) │  报告正文(右)                │
│ · 每日简报   │  # 景区经营分析报告           │
│ · 深度:节假日 │  ## 一、客流预测概要          │
│ · 周期:周报  │  ...Markdown 渲染            │
│              │  [导出 MD] [重新生成]         │
└──────────────┴─────────────────────────────┘
```

**生成面板**：报告类型选择 + 周期选择 + （deep_dive 时）主题选择（复用 GROUP_META 六个主题）

**协作过程可视化**：生成中的报告显示 Agent 执行轨迹（Coordinator 分派 → 采集完成 → 分析中 → 撰写中 → 审核中），从 `trace_json` 读取——这是演示亮点，让评委/用户看到多 Agent 在干活。

### 现有组件升级

- **AgentChat**（数据看板右栏）：模拟回复切换为 `POST /agent/chat` 真实调用，chat 复用同一套 Tool + Analyst，轻量版（单轮，无 Writer/Reviewer）
- **经营分析页**："问 Agent 深入分析"按钮 → 改为跳转 Agent 报告页并自动发起 `deep_dive` 报告

---

## 六、LLM 接入策略

**分层可配置**（`settings.py` + 环境变量）：

| 层级 | 用途 | 推荐模型 | 说明 |
|---|---|---|---|
| Analyst/Writer | 推理与撰写 | DeepSeek-V3 / Qwen2.5-72B API | 中文业务写作质量优先 |
| Coordinator/Reviewer | 路由与审核 | 同上（可降级到小模型） | 结构化输出即可 |
| 本地模式（可选） | 数据不出域 | Ollama + Qwen2.5-7B | 演示兜底，质量打折 |

**降级链**：配置的 LLM 不可用 → 尝试备用 provider → 全部失败则 DataCollector + 模板化 Writer 生成"数据简报"（无 LLM 的确定性报告），保证报告功能永不白屏。

**Prompt 关键约束**（写入 Writer/Analyst system prompt）：
- 所有数值必须来自 Tool 返回，禁止推断编造
- 建议必须可执行（带具体动作 + 预期效果 + 触发条件）
- 面向非技术读者，禁用 lag/rolling/特征工程术语

---

## 七、落地步骤（建议两期）

### 第一期（核心闭环，约 2-3 天工作量）
1. `backend/app/agent/` 包：`tools.py`（3 Tool）+ `graph.py`（LangGraph 工作流）+ `prompts.py`
2. `agent_reports` 表迁移 + `routers/agent.py`（report 四端点）
3. 前端"Agent 报告"页面（列表 + 正文渲染 + 生成面板 + 轨迹展示）
4. AgentChat 接真实 `/agent/chat`
5. LLM 配置化 + 模板化降级兜底

### 第二期（增强，后续迭代）
- 报告定时生成（每日简报自动化，挂 automation 或 APScheduler）
- 报告导出 PDF/DOCX（python-docx）
- Reviewer HITL：审核不通过时人工介入确认
- 多报告对比（本期 vs 上期）

### 依赖增量

```
langgraph >= 0.2        # 工作流编排（核心）
langchain-core          # LLM 抽象
openai 或 dashscope     # LLM provider（按配置）
```

后端 venv 直接 pip 安装，前端零新增依赖（Markdown 渲染手写轻量解析器或用 marked，二选一）。

---

## 八、与历史方案的差异（为什么这样调整）

| 历史方案 | 本方案 | 调整原因 |
|---|---|---|
| 参考 Reasonlytics（本地 Ollama 全套） | LLM 可配置 + API 优先 | 演示需要报告质量；本地 7B 模型中文报告质量不足 |
| 通用 data-analyst（NL→SQL→pandas） | 三个固定 Tool | 项目数据已结构化为三个 JSON API，NL2SQL 属过度设计且引入幻觉风险 |
| 单一报告生成链 | Coordinator/Collector/Analyst/Writer/Reviewer 五角色 | 用户明确要求"多 Agent 协作"+ 生成"高质量"报告，审核环节是质量保障关键 |
| AgentChat 直接调工作流 | chat 与 report 分离：chat 轻量单轮，report 完整五段式 | 对话要快，报告要深，复用同一 Tool 层 |
| 前端弹窗展示报告 | 独立"Agent 报告"页面 + 历史列表 | 用户要求"添加 Agent 报告页面"；报告需沉淀复用 |

---

## 九、验收标准

1. 用户在"Agent 报告"页选择类型 → 30-90 秒内生成完整 Markdown 报告
2. 报告含四要素：预测概要 / 关键发现（≥3条，带数据引用）/ 风险预警 / 行动建议（≥3条可执行）
3. 报告中数值 100% 可溯源到三维度数据（Reviewer 硬校验）
4. LLM 故障时仍能输出模板化数据简报（降级链生效）
5. trace 轨迹在前端可见（多 Agent 协作过程展示）
6. 历史报告可列表、可重复查看
