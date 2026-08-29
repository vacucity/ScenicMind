# 智景 ScenicMind

客流预测产品现已打通完整主链路：注册 / 登录 → 上传真实数据 → FlowStack 算法分析 → 动态数据看板。特征贡献结果单独保存在后端，供后续 Agent 报告使用，不进入看板接口的数据主体。

```text
frontend/  React + TypeScript + Vite（注册、登录、上传、动态看板）
backend/   FastAPI + SQLite（鉴权、文件存储、预测与分析接口）
```

## 启动

后端：

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

接口文档：http://127.0.0.1:8000/docs

前端（另开终端）：

```powershell
cd frontend
pnpm install
pnpm dev --host 127.0.0.1
```

页面：http://127.0.0.1:5173

- `/register`：注册账号
- `/login`：登录
- `/upload`：上传单个客户数据文件并执行分析
- `/dashboard`：展示最新真实客流、历史真实值、历史回测和未来 7D / 14D / 30D 预测

## 上传数据要求

支持 `.csv`、`.xlsx`、`.xls`、`.json` 和 `.parquet`，单文件不超过 50 MB，至少包含 21 天数据：

```csv
date,visitors
2026-01-01,3200
2026-01-02,3450
```

日期列可使用 `date`、`日期`、`day`、`ds`、`时间`、`统计日期`；真实客流列可使用 `visitors`、`客流量`、`游客量`、`游客人数`、`入园人数` 等名称。文件中的天气、预约、景区承载量、公告和网络关注度字段会被识别为真实上传数据。

看板不会为缺失的外部数据伪造数值。没有出现在上传文件中的数据源会明确显示“待配置真实数据源”，后续可按景区位置、票务接口和官方公告地址增加采集适配器。

## 当前演示数据

已使用 `C:\Users\23017\Desktop\data.xlsx` 完成前端上传、后端解析、FlowStack 推理和看板展示测试。演示时可用以下结果快速核对是否运行正确：

- 有效数据：2,377 行、56 列
- 日期范围：2019-10-11 至 2026-08-28
- 最新真实客流：15,667 人（2026-08-28）
- 未来 7 天预测日均：19,858 人
- 未来 30 天预测日均：20,197 人
- 模型版本：`flowstack-20260828T182829Z`

操作顺序：注册 → 登录 → 选择 `data.xlsx` → 点击“开始分析” → 自动跳转看板。分析期间按钮会显示“分析中…”，请等待跳转，不要重复点击。

## 接口

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`
- `POST /api/v1/analyses`
- `GET /api/v1/analyses/latest`
- `GET /api/v1/analyses/{analysis_id}`
- `GET /api/v1/analyses/{analysis_id}/importance`（仅供后续 Agent 报告）

运行后端集成测试：

```powershell
cd backend
uv run pytest -q
```
