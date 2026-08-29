# 智景 ScenicMind

景区客流预测与经营决策平台。前后端已融合：前端采用可视化经营驾驶舱外观，后端由模块一（客流预测）与模块二（经营分析 Agent）提供数据。

```text
frontend/  React + TypeScript + Vite（登录页、经营驾驶舱看板）
backend/   FastAPI（模块一客流预测、模块二报告引擎、统一输出契约）
datasets/  贵州文旅评论数据（模块二游客声音证据）
```

## 启动

后端：

```powershell
cd backend
python -m pip install -e .
python -m uvicorn app.main:app --reload
```

接口文档位于 http://127.0.0.1:8000/docs。

前端（另开终端）：

```powershell
cd frontend
npm install --no-package-lock
npm run dev
```

页面位于 http://127.0.0.1:5173，登录页和看板页分别为 `/login`、`/dashboard`。

## 模块一

模块一提供客流预测数据，驱动看板顶部指标、趋势图和未来 7 天预报：

- `GET /api/v1/module-one/output?spot=黄果树瀑布`：返回今日预测、历史 30 天、未来 7 天预测与周预报；
- 当前为演示口径（固定种子、可复现），数字与模块二演示预测对齐；接入真实预测模型时替换 `backend/app/module_one_service.py` 的数据来源即可。

## 模块二

模块二现已提供证据约束型经营报告：

- 使用演示预测或接收模块一传入的真实预测、承载量和特征贡献；
- 聚合评论数据中的游客情绪、主题与高影响原声；
- 生成带数值依据、证据编号、优先级和预期效果的经营建议；
- 保存模型版本、数据快照和生成模式，便于报告回放；
- 不配置外部大模型也能稳定运行，后续可在表达层接入 LLM。

接口：

- `GET /api/v1/module-two/output?spot=黄果树瀑布`：获取可直接展示的报告；
- `POST /api/v1/module-two/reports`：传入模块一结果并生成报告；
- `GET /api/v1/module-two/spots`：获取评论数据覆盖的景点；
- `GET /health`：部署健康检查。

模块一向 `POST /api/v1/module-two/reports` 提交的数据结构可在 Swagger 文档中查看。未传入 `forecast` 或 `drivers` 时，接口会使用明确标注的演示数据。

## 后续接入位置

- 模块一：接入真实预测模型时，替换 `backend/app/module_one_service.py` 中的数据来源（契约不变）。
- 模块二：在 `backend/app/module_two_service.py` 中扩展规则或接入 LLM 表达层。
- 前端数据：看板由 `frontend/src/pages/DashboardPage.tsx` 聚合调用 `getModuleOneOutput()`（客流）与 `getModuleTwoOutput()`（经营报告）。
- 登录鉴权：在 `frontend/src/pages/LoginPage.tsx` 中接入；确定鉴权方案后再添加后端接口。

两个模块统一返回 `generatedAt`、`data`、`text`。模块二的 `data` 已收紧为报告、预测、归因、游客洞察、建议和追溯信息。

当前模块入口：

- `GET /api/v1/module-one/output`
- `GET /api/v1/module-two/output`
- `POST /api/v1/module-two/reports`
- `GET /api/v1/module-two/spots`

模块一已可运行并明确标记演示预测；模块二已可运行并会明确标记演示预测。
