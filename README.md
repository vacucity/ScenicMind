# PineFlow

人流量预测系统的最小前后端骨架。当前不包含演示数据、预测算法或真实鉴权，便于后续按实际需求接入。

```text
frontend/  React + TypeScript + Vite（登录页、数据看板空页面）
backend/   FastAPI（健康检查、预测结果接口契约）
```

## 启动

后端：

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

接口文档位于 http://127.0.0.1:8000/docs。

前端（另开终端）：

```powershell
cd frontend
pnpm install
pnpm dev
```

页面位于 http://127.0.0.1:5173，登录页和看板页分别为 `/login`、`/dashboard`。

## 后续接入位置

- 预测算法：实现 `backend/app/prediction.py` 中的 `get_latest_prediction()`。
- 前端数据：调用 `frontend/src/api/predictions.ts` 中的 `getLatestPrediction()`。
- 登录鉴权：在 `frontend/src/pages/LoginPage.tsx` 中接入；确定鉴权方案后再添加后端接口。

预测接口统一返回一个轻量封装：`generatedAt`、`data`、`text`。其中 `data` 暂不限定结构，等看板指标确定后再收紧类型。
