# 智景 ScenicMind

人流量预测系统的最小前后端骨架。当前不包含演示数据、预测算法或真实鉴权，便于后续按实际需求接入。

```text
frontend/  React + TypeScript + Vite（登录页、数据看板空页面）
backend/   FastAPI（模块一、模块二、统一输出契约）
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

- 模块一：实现 `backend/app/modules/module_one.py` 中的 `get_output()`。
- 模块二：实现 `backend/app/modules/module_two.py` 中的 `get_output()`。
- 前端数据：调用 `frontend/src/api/modules.ts` 中的 `getModuleOutput()`，并传入 `module-one` 或 `module-two`。
- 登录鉴权：在 `frontend/src/pages/LoginPage.tsx` 中接入；确定鉴权方案后再添加后端接口。

两个模块统一返回一个轻量封装：`generatedAt`、`data`、`text`。其中 `data` 暂不限定结构，等看板指标确定后再收紧类型。

当前模块入口：

- `GET /api/v1/module-one/output`
- `GET /api/v1/module-two/output`

算法未接入前，两个入口都会返回 `501`。
