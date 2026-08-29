# 智景 ScenicMind

景区客流预测与智能运营分析平台。打通完整主链路：登录 → 数据上传 → FlowStack 算法分析 → 动态数据看板 → Agent 智能助手。

## 核心能力

- **客流预测**：基于 FlowStack 模型，支持 7D / 14D / 30D / 全部历史数据切换
- **Agent 智能助手**：悬浮窗形式，全程右下角显示，接入 DeepSeek LLM，支持自然语言问答与四段式周报（准确率回顾 → 归因分析 → 经营建议 → 风险预警）
- **运营准备**：八模块指标看板，覆盖客流、容量、天气、预约、公告、网络关注度等维度
- **一键部署**：systemd + Caddy 自动反代 + Let's Encrypt TLS

## 技术栈

```text
frontend/  React + TypeScript + Vite（鉴权、上传、动态看板、Agent 悬浮窗）
backend/   FastAPI + SQLite + python-dotenv（鉴权、文件存储、FlowStack 推理、Agent LLM 编排）
```

## 启动

后端：

```powershell
cd backend
uv sync
# 安装 LLM 依赖
pip install python-dotenv
# 配置 .env（参考 .env.example，填入 DeepSeek API Key）
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

接口文档：http://127.0.0.1:8001/docs

前端（另开终端）：

```powershell
cd frontend
pnpm install   # 或 npm install
pnpm dev        # 或 npm run dev
```

页面：http://127.0.0.1:5173

- `/login`：登录（演示模式：任意账密均可进入，底部显示体验账号 test / test）
- `/upload`：上传数据并执行分析
- `/dashboard`：数据看板 + Agent 悬浮窗
  - 数据看板：真实客流、历史回测、未来预测、八模块运营指标
  - 客流影响因素：点击「问 Agent 深入分析」直接在悬浮窗中输出，不跳转页面
  - 智景助手：右下角悬浮窗，可收起 / 展开，支持自然语言问答

## 数据与配置

### 上传数据要求

支持 `.csv`、`.xlsx`、`.xls`、`.json` 和 `.parquet`，单文件不超过 50 MB，至少 21 天数据：

```csv
date,visitors
2025-01-01,3200
2025-01-02,3450
```

日期列支持 `date`、`日期`、`day`、`ds` 等命名；客流列支持 `visitors`、`客流量`、`游客量`、`入园人数` 等。天气、预约、承载量、公告、网络关注度字段会被识别为真实上传数据，缺失源会明确标注「待配置真实数据源」。

### LLM 配置

后端 `backend/.env`：

```env
AGENT_API_KEY=sk-你的DeepSeek密钥
AGENT_LLM_BASE_URL=https://api.deepseek.com/v1
AGENT_LLM_MODEL=deepseek-chat
```

未配置 API Key 时，Agent 自动降级为模板化简报；配置后启用真实 LLM 对话与四段式报告。

### 演示数据

内置九寨沟真实历史数据（2019-09 至今），日承载量上限 41,000 人。FlowStack 模型已预训练，回测 MAPE 约 15.89%。

## 接口

- `POST /api/v1/auth/login`（演示模式：任意账密自动创建用户）
- `GET /api/v1/auth/me`
- `POST /api/v1/analyses`（上传数据）
- `GET /api/v1/analyses/latest`
- `GET /api/v1/analyses/{id}`
- `GET /api/v1/analyses/{id}/importance`
- `GET /api/v1/analyses/{id}/indicators`（八模块指标）
- `POST /api/v1/agent/report`（生成 Agent 报告）
- `GET /api/v1/agent/report`（获取结构化四段式报告）
- `GET /api/v1/agent/reports`（报告列表）
- `GET /api/v1/agent/report/{id}`（报告详情）
- `GET /api/v1/agent/report/{id}/pdf`（下载 PDF）
- `POST /api/v1/agent/chat`（Agent 对话）

## 部署

线上地址：https://scenicmind.wildernotrack.me

- 后端：systemd 管理（`scenicmind.service`），监听 8001
- 前端：Caddy 托管静态文件，`/api/*` 反代到后端
- TLS：Let's Encrypt 自动签发

## 测试

```powershell
cd backend
uv run pytest -q
```
