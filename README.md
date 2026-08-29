# 智景 ScenicMind · 景区客流预测与经营分析平台

从多源数据采集、机器学习预测，到可视化看板与 AI 经营报告，一站式景区客流智能决策平台。

智景 ScenicMind 面向景区运营管理者，用 AI 把「客流预测、经营指标分析、经营决策报告」三个环节串成一条自动化的闭环链路。上传景区历史数据后，系统自动完成客流预测、8 大经营指标计算与影响因素归因，并通过多 Agent 协作生成可直接用于晨会的经营分析报告。

## 项目简介

### 核心价值

景区运营的核心矛盾是「客流波动大、预测难、决策靠经验」。ScenicMind 用数据与 AI 解决三件事：

- **看得清**：未来 7 / 14 / 30 天客流预测 + 实时经营指标看板，一眼掌握景区运行状态。
- **讲得明**：把晦涩的模型特征聚合为「节假日、天气、交通、网络热度」等业务主题，管理者能直接理解客流波动的成因。
- **给得出**：多 Agent 协作生成结构化经营报告，输出可执行的行动建议（分时预约、弹性排班、营销窗口等）。

### 差异化优势

| 维度 | 传统方案 | ScenicMind |
| --- | --- | --- |
| 预测 | 单一模型、黑盒 | FlowStack 堆叠集成：4 路基学习器 + OOF 堆叠 + 冗余感知特征选择，节假日尖峰专项校正 |
| 分析 | 只给数字 | 8 大经营指标 + 业务主题归因，图文表结合 |
| 报告 | 人工撰写 | 5 Agent 协作自动生成，Reviewer 数值硬校验防幻觉 |
| 落地 | 依赖数据科学家 | 上传数据即用，面向非技术管理者 |
| 容错 | 单点故障 | 模型/LLM 双重降级链，核心功能永不白屏 |

## 功能特性清单

### 一、数据接入与认证

- 多格式数据上传：支持 CSV / XLSX / XLS / JSON / Parquet，单文件 ≤ 50 MB，自动识别「日期」「客流量」等多种中文列名别名
- 账号体系：注册 / 登录 / 登出，PBKDF2 密码哈希 + Bearer Token 会话
- 多源数据采集器（算法侧）：九寨沟客流、官方公告、Open-Meteo 天气、维基百科热度、百度指数等适配器

### 二、客流预测引擎（FlowStack）

- 堆叠集成模型：LightGBM(Huber) / XGBoost(Huber) / LightGBM(L1) / CatBoost(Huber) 四路并行，TimeSeriesSplit 前向链式 OOF 预测 + 正约束 Ridge 元学习器融合
- 冗余感知特征选择：Spearman 相关聚类 + 簇内互信息代表特征，化解多重共线性
- 差分目标建模：预测「相对昨日的变化量」，显式内置持续性基线
- 节假日尖峰专项：节假日样本加权 + 场景残差校正 + 承载量约束，专攻假期峰值
- 降级链：FlowStack 不可用时自动切换 SeasonalLagFallback 季节滞后模型

### 三、数据看板（主视图）

- 快照指标：最新真实客流、下一日预测、未来 N 天日均，同比/环比
- 动态趋势图：真实值与预测值曲线逐笔绘制动画（真实线先画、预测线后画），悬停/键盘聚焦逐点对照
- 周期切换：7D / 14D / 30D 一键切换
- 未来 7 日预测明细：按峰值/常态/低谷分级着色
- 预测准确率环形图：基于 MAPE 的环形进度可视化
- 数据来源状态：字段接入状态列表，缺失数据源明确标注

### 四、指标蓝图（8 大经营指标独立可视化）

- 客流趋势：30 日悬停柱状图 + 同比/环比/波动率 KPI
- 承载与售罄：载客率半圆仪表盘 + 售罄/限流堆叠柱
- 节假日效应：季节占比环形饼图 + 7 大假期逐日客流 sparkline 网格
- 天气影响：雨天/晴天垂直对比柱 + 温度渐变条
- 交通基建：高铁/高速开通前后对比柱 + 提升率
- 网络热度：热度-客流相关系数仪表 + 渠道面积折线图
- 数据质量：封顶/尖峰/缺失堆叠进度条
- 全模块配线性 SVG 图标，统一 pine/sage 语义色体系

### 五、经营分析（特征归因）

- 业务主题归因：模型特征聚合为「历史客流 / 节假日 / 天气 / 关注度 / 运营 / 交通」6 大主题
- 简要分析：每个主题附一句话业务解读 + 贡献度占比
- 语义化配色：每个主题独立语义色（绿/紫/蓝/橙/珊瑚/青）

### 六、多 Agent 协作报告

- 5 Agent 协作：Coordinator(编排) → Collector(采集) → Analyst(分析) → Writer(撰写) → Reviewer(审核)
- 三维度交叉验证：预测客流量 × 指标蓝图 × 特征贡献度
- 防幻觉机制：Reviewer 数值硬校验，报告中每个数字必须可溯源
- 三种报告类型：每日简报 / 深度分析（单主题深挖）/ 周期报告
- 协作过程可视化：生成时实时展示 5 个 Agent 的执行轨迹
- 图文表结合：报告页含 KPI 卡 + 预测趋势图 + 贡献占比表 + 正文
- PDF 下载：报告一键导出 PDF（中文字体、视觉层级排版）
- 对话式问答：数据看板内置 Agent 对话框，轻量单轮问答
- 降级链：LLM 不可用时自动生成模板化数据简报，报告功能不中断

## 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 算法 | Python 3.11+、scikit-learn、LightGBM、XGBoost、CatBoost、pandas、NumPy | FlowStack 堆叠集成模型 |
| 后端 | FastAPI、SQLite、reportlab、Uvicorn | 鉴权 / 上传 / 预测 / 指标 / Agent API |
| 前端 | React 19、TypeScript、Vite 7 | 四视图单页应用，纯 SVG 图表（零图表库依赖） |
| Agent | 纯 Python 状态机 + OpenAI 兼容 LLM | 5 Agent 协作，不依赖 LangChain/LangGraph |
| 包管理 | uv（后端）、pnpm（前端） | 依赖锁定、可复现 |

## 环境要求

- Python ≥ 3.11（推荐 3.12）
- Node.js ≥ 18（推荐 22）
- 包管理器：uv（后端）、pnpm（前端）
- 已训练模型：`artifacts/flowstack/current/model/`（仓库已携带）
- 科学计算依赖：`.deps/` 目录（仓库已携带，含 sklearn/lightgbm/xgboost）

## 安装与使用

### 1. 后端启动

```powershell
cd backend
python -m pip install -e .
python -m uvicorn app.main:app --reload --port 8001
```

接口文档：http://127.0.0.1:8001/docs

### 2. 前端启动（另开终端）

```powershell
cd frontend
pnpm install
pnpm dev --host 127.0.0.1
```

访问：http://127.0.0.1:5173

### 3. Agent 模型配置（可选）

后端通过环境变量配置 LLM（默认已内置 OpenAI 兼容中转）：

```powershell
$env:AGENT_LLM_BASE_URL = "https://your-provider.com/v1"
$env:AGENT_LLM_MODEL = "your-model-name"
$env:AGENT_API_KEY = "sk-..."
```

Agent 模块统一管理 API Key，5 个 Agent 共享一套凭证；新增 Agent 只需在 `app/agent/config.py` 的 `AGENT_REGISTRY` 登记。

## 使用示例

### 数据格式

上传文件至少包含「日期」和「客流」两列（列名支持中文别名），建议 ≥ 21 天：

```csv
date,visitors
2026-01-01,3200
2026-01-02,3450
2026-01-03,5100
```

### 操作流程

```
注册/登录 → 上传数据 → 自动分析 → 数据看板 → 指标蓝图 → 经营分析 → Agent 报告
```

- 上传数据：选择文件 → 「开始分析」，分析完成后自动跳转看板
- 看板：查看预测趋势、快照指标、准确率
- 指标蓝图：8 大经营指标独立可视化
- 经营分析：查看 6 大主题贡献度与简要分析，点「问 Agent」深挖
- Agent 报告：选择报告类型生成，查看协作轨迹，下载 PDF

### 演示数据核对

仓库演示数据（`data.xlsx`）运行结果参考：

| 指标 | 值 |
| --- | --- |
| 有效数据 | 2,377 行 × 56 列 |
| 日期范围 | 2019-10-11 ~ 2026-08-28 |
| 最新真实客流 | 15,667 人 |
| 未来 7 天预测日均 | 19,858 人 |
| 平均载客率 | 90.0% |
| 节假日客流提升 | 46.5% |
| 高铁开通提升 | 145.4% |

## 项目结构概览

```text
贵客松/
├── src/                          # 算法层（Python）
│   ├── flowstack/                # ★ 核心：堆叠集成预测模型
│   │   ├── model.py              #   模型训练/预测/特征重要性
│   │   ├── redundancy.py         #   冗余感知特征选择
│   │   ├── service.py            #   PredictionService / ImportanceService
│   │   └── metrics.py            #   评估指标
│   ├── scenicboost/              # 上一代单模型（对比基线）
│   ├── collectors/               # 数据采集器（客流/公告/天气/维基）
│   ├── importers/                # 外部指标导入（百度指数等）
│   ├── features/                 # 特征工程（日历/构建器）
│   └── quality/                  # 数据质量（泄漏检测/清洗）
├── ScenicMind/                   # ★ 产品工程
│   ├── backend/                  # FastAPI 后端
│   │   └── app/
│   │       ├── routers/          #   auth / analyses / agent 路由
│   │       ├── services/         #   forecast / dataset / indicators
│   │       ├── agent/            #   5 Agent 协作（config/llm/tools/prompts/graph/pdf）
│   │       └── database.py       #   SQLite 数据层
│   └── frontend/                 # React 前端
│       └── src/
│           ├── features/
│           │   ├── auth/         #   登录/注册
│           │   ├── upload/       #   数据上传
│           │   └── dashboard/    #   四视图：看板/指标蓝图/经营分析/Agent报告
│           ├── api/              #   API 封装
│           └── styles/           #   样式（语义色 token）
├── artifacts/flowstack/current/  # 已训练模型产物
├── configs/                      # 数据源与算法配置
├── docs/                         # 集成说明与方案文档
├── tests/                        # 测试
└── appendix/                     # 历史基线实验（仅供追溯）
```

## 接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/auth/me` | 当前用户 |
| POST | `/api/v1/analyses` | 上传数据并触发分析 |
| GET | `/api/v1/analyses/latest` | 最新分析结果 |
| GET | `/api/v1/analyses/{id}` | 指定分析 |
| GET | `/api/v1/analyses/{id}/importance` | 特征贡献度 |
| GET | `/api/v1/analyses/{id}/indicators` | 8 大经营指标 |
| POST | `/api/v1/agent/report` | 发起报告生成（异步） |
| GET | `/api/v1/agent/report/{id}` | 轮询报告状态 |
| GET | `/api/v1/agent/report/{id}/pdf` | 下载报告 PDF |
| GET | `/api/v1/agent/reports` | 历史报告列表 |
| POST | `/api/v1/agent/chat` | Agent 对话问答 |

## 运行测试

```powershell
cd backend
uv run pytest -q
```

## 核心亮点速览

- **端到端闭环**：采集 → 预测 → 指标 → 归因 → 报告，全自动。
- **FlowStack 堆叠集成**：四路基学习器 + OOF 融合，专攻节假日尖峰，MAPE 约 10.6%。
- **多 Agent 协作报告**：5 角色分工 + Reviewer 数值硬校验，报告可信可落地。
- **8 大经营指标**：覆盖客流/承载/节假日/天气/交通/热度/质量，图文表结合。
- **面向非技术用户**：业务主题归因、管理者语言报告、中文 PDF 导出。
- **双重降级容错**：模型与 LLM 均有降级链，核心功能永不白屏。