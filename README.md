# 智景 ScenicMind

> 景区客流预测、经营指标分析与多 Agent 决策报告平台

**ScenicMind** 把景区历史客流、日历节假日、天气、网络热度、预约承载和交通事件，转化为**可预测、可解释、可执行**的经营决策：

- **FlowStack** 算法给出未来 7 / 14 / 30 天客流预测；
- **指标蓝图**（8 大模块）解释当前经营状态；
- **多 Agent 系统** 把确定性数据组织成经过审核的管理报告。

一句话技术价值：*我们不是单纯做一条预测曲线，而是把「数据接入 — 预测 — 解释 — 建议 — 审核 — 交付」做成了一条完整、可降级、可追踪的决策链路。*

---

## 目录

- [核心特性](#核心特性)
- [技术架构](#技术架构)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [上传数据要求](#上传数据要求)
- [FlowStack 预测算法](#flowstack-预测算法)
- [指标蓝图（8 大模块）](#指标蓝图8-大模块)
- [多 Agent 报告系统](#多-agent-报告系统)
- [模型评估结果](#模型评估结果)
- [API 一览](#api-一览)
- [测试](#测试)
- [技术栈](#技术栈)
- [文档索引](#文档索引)
- [已知边界与生产化路线](#已知边界与生产化路线)
- [License](#license)

---

## 核心特性

| 能力 | 说明 |
|---|---|
| **完整主链路** | 注册 / 登录 → 上传数据 → FlowStack 分析 → 动态数据看板 → Agent 报告 → PDF 导出 |
| **多格式上传** | CSV / XLSX / XLS / JSON / Parquet，单文件 ≤ 50 MB |
| **时间安全特征** | 滞后与滚动特征只使用目标日前可见数据，避免数据穿越 |
| **FlowStack 集成模型** | 冗余感知特征选择 + 差分目标 + 四路基学习器 OOF 堆叠 + 稳健损失 + 场景校正 |
| **指标蓝图** | 从上传数据动态计算 8 大经营模块，缺失数据明确标注「待配置」 |
| **多 Agent 协作** | Coordinator → Collector → Analyst → Writer → Reviewer 五阶段，防幻觉审核 |
| **可降级** | 模型加载失败回退季节滞后模型；LLM 不可用回退确定性模板简报 |
| **可审计** | 每个分析和报告都有唯一 ID、状态、执行轨迹，接口均校验用户归属 |

---

## 技术架构

四层架构：

```
┌────────────────────────────────────────────────────────────┐
│  交互层    React 19 + TypeScript + Vite                     │
│            注册登录 / 上传 / 看板 / 指标蓝图 / 经营分析 / Agent 报告  │
├────────────────────────────────────────────────────────────┤
│  业务 API 层  FastAPI + Uvicorn + SQLite                     │
│            鉴权 / 分析 / 指标 / 贡献度 / Agent 报告 / 对话 / PDF  │
├────────────────────────────────────────────────────────────┤
│  算法与智能层                                                 │
│    · FlowStack        客流预测、回测、特征重要性、场景校正         │
│    · Indicator Engine  8 大模块经营指标计算                     │
│    · Multi-Agent      Coordinator/Collector/Analyst/Writer/Reviewer │
│    · LLM Client       OpenAI 兼容 Chat Completions（可替换模型）  │
├────────────────────────────────────────────────────────────┤
│  数据与持久化层  SQLite（用户/会话/分析/报告）+ 文件隔离存储        │
│                 joblib + metadata.json 模型产物                 │
└────────────────────────────────────────────────────────────┘
```

**核心设计原则**：

1. **预测与生成式 AI 解耦**：数值由确定性算法和数据库提供，LLM 只负责分析组织与语言表达。
2. **预测与解释解耦**：看板主接口只返回预测事实，特征贡献走独立接口，避免阻塞主链路。
3. **真实数据优先**：缺失天气、预约、承载、公告、热度时显示「待配置真实数据源」，不伪造字段。
4. **时间安全**：特征工程与模型拟合严格遵循时间顺序，杜绝未来信息泄漏。
5. **可降级**：模型与 LLM 双重降级，保证主链路永不白屏。
6. **可审计**：全链路唯一 ID + 状态 + 执行轨迹。

---

## 目录结构

```text
ScenicMind/
├── frontend/                 # React + TypeScript + Vite 前端
│   ├── src/features/         # auth / dashboard / upload 等特性模块
│   └── src/api/              # API 客户端封装
├── backend/                  # FastAPI 后端
│   └── app/
│       ├── routers/          # auth / analyses / agent 路由
│       ├── services/         # dataset / forecast / indicators 服务
│       ├── agent/            # 多 Agent 状态机、Tool、Prompt、LLM Client
│       └── database.py       # SQLite 数据层
├── scenicmind/               # 算法核心库（Python）
│   ├── flowstack/            # FlowStack 集成模型（预测/重要性/导出）
│   ├── scenicboost/          # ScenicBoost 基线模型
│   ├── features/             # 特征工程与日历
│   ├── collectors/           # 九寨沟公告/客流、天气、Wikimedia 采集器
│   ├── importers/            # 百度指数、GitHub 数据源导入
│   ├── parsers/              # 公告解析
│   └── quality/              # 数据质量检查、泄漏防护、训练清洗
├── configs/                  # 景区、特征、数据源、关键词、模型配置
├── artifacts/flowstack/      # 训练产物（model.joblib、metadata、metrics）
├── appendix/                 # 基线对比与评估脚本
├── datasets/                 # 示例/真实数据集
├── docs/                     # 设计稿、集成说明、方案文档、路演手册
├── promo/                    # Remotion 宣传视频项目（营销素材）
└── tests/                    # 单元测试
```

---

## 快速开始

### 环境要求

- Python ≥ 3.11
- Node.js ≥ 18（推荐 20+）
- [uv](https://github.com/astral-sh/uv)（Python 包与虚拟环境管理）
- [pnpm](https://pnpm.io/)（前端包管理）

### 1. 后端

```bash
cd backend

# 同步依赖（自动创建虚拟环境）
uv sync

# 复制环境变量模板并按需填写
cp .env.example .env   # Windows: copy .env.example .env

# 启动服务
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

接口文档（OpenAPI / Swagger）：<http://127.0.0.1:8000/docs>

> `.env` 中 `AGENT_API_KEY` 用于多 Agent 报告系统的 LLM 调用；不填写则 Agent 报告自动降级为模板化数据简报（不影响预测主链路）。

### 2. 前端

另开一个终端：

```bash
cd frontend

pnpm install

pnpm dev --host 127.0.0.1
```

页面：<http://127.0.0.1:5173>

| 路由 | 功能 |
|---|---|
| `/register` | 注册账号 |
| `/login` | 登录 |
| `/upload` | 上传数据文件并执行分析 |
| `/dashboard` | 数据看板（预测 / 指标蓝图 / 经营分析 / Agent 报告） |

---

## 上传数据要求

支持 `.csv`、`.xlsx`、`.xls`、`.json`、`.parquet`，单文件 ≤ 50 MB，至少 21 天数据。最小示例：

```csv
date,visitors
2026-01-01,3200
2026-01-02,3450
```

- **日期列别名**：`date` / `日期` / `day` / `ds` / `时间` / `统计日期`
- **客流列别名**：`visitors` / `客流量` / `游客量` / `游客人数` / `入园人数` / `visitor_count` / `actual_visitors` / `y`
- 文件中的**天气、预约、承载量、公告、网络关注度**字段会被识别为真实上传数据
- CSV 编码按 UTF-8 BOM → UTF-8 → GB18030 顺序自动尝试
- 重复日期保留最后一条并记录警告；晚于上传当天的数据不作为真实值

看板**不会为缺失的外部数据伪造数值**，未出现的数据源会明确显示「待配置真实数据源」。

---

## FlowStack 预测算法

FlowStack 针对景区客流「周期明显、节假日尖峰强、承载有上限」的特点设计：

1. **时间切分**：按时间顺序 80% / 20% 划分，测试集为真正的时间外样本，不随机打乱。
2. **冗余感知特征选择**：训练集上 Spearman 相关聚类（|ρ| ≥ 0.90 归簇），簇内按互信息选代表，61 维降至 46 维。
3. **差分目标**：学习 `delta = visitors − visitors_lag_1`，显式写入「持续性基线 + 变化修正」结构。
4. **场景加权**：普通日 1.0、周末 1.15、暑期 1.25、法定节假日 1.5、限流场景 1.25。
5. **四路基学习器**：LightGBM-Huber、XGBoost-Huber、LightGBM-L1、CatBoost-Huber，对极端尖峰更稳健。
6. **前向 OOF 堆叠**：TimeSeriesSplit(5) 生成 out-of-fold 预测，避免元学习器看到乐观输出。
7. **正约束 Ridge 融合**：元学习器权重非负，可解释各基模型贡献。
8. **场景残差校正**：在 OOF 残差上学习节假日/周末/旺季的系统偏差（有样本门槛与上限）。
9. **物理约束**：预测非负，存在日承载量时不高于承载上限。
10. **递归多步预测**：逐日递归生成未来 30 天，并聚合 7 / 14 / 30 天日均、峰值、谷值。

### 模型产物

```text
artifacts/flowstack/current/
├── model/
│   ├── model.joblib      # 完整模型（选择器/基学习器/元学习器/校正器）
│   └── metadata.json     # 版本、特征清单、融合权重、训练区间
├── feature_importance.csv
├── agent_importance.json
└── oof_predictions.csv
```

### 命令行入口

```bash
# 训练
python -m scenicmind.flowstack.cli train --data path/to/training.xlsx --artifact-dir artifacts/flowstack/current

# 仅预测
python -m scenicmind.flowstack.cli predict --model-dir artifacts/flowstack/current/model --features future_features.csv --output predictions.csv

# 单独生成特征重要性
python -m scenicmind.flowstack.cli importance --model-dir artifacts/flowstack/current/model --output-dir importance --top-k 20
```

---

## 指标蓝图（8 大模块）

指标引擎从标准化 DataFrame 动态计算，不依赖固定文件名：

1. **客流趋势** — 最新客流、总量、均值、P95、同比、环比、波动
2. **承载与售罄** — 载客率、超承载天数、售罄率、限流率、预约量
3. **预测准确率** — MAPE、MAE、验证天数
4. **节假日效应** — 节假日提升率、旺淡季、各假期逐日曲线
5. **天气影响** — 雨/晴天客流、降水影响、温度区间
6. **交通基建** — 高铁/高速开通前后客流与提升率
7. **网络热度** — 百科浏览、微信热度与客流相关系数
8. **数据质量** — 行列数、日期跨度、缺失、封顶、异常尖峰

> 相关系数、前后均值与模型贡献用于**发现线索**，不等同于严格因果效应。

---

## 多 Agent 报告系统

单一 Agent 同时读取数据、分析、写作和自我审查容易混淆职责并放大幻觉。ScenicMind 拆成五阶段：

```
用户发起报告请求
      │
      ▼
┌──────────────┐
│ Coordinator  │  校验类型/周期/主题，确定工作流（确定性路由）
└──────┬───────┘
       ▼
┌──────────────┐
│  Collector   │  调用三个确定性 Tool 取数（不访问互联网、不查库外）
└──────┬───────┘
       ▼
┌──────────────┐
│   Analyst    │  交叉验证预测/指标/贡献度，输出结构化 insights/risks/actions
└──────┬───────┘
       ▼
┌──────────────┐
│    Writer    │  按报告类型将要点写成业务 Markdown
└──────┬───────┘
       ▼
┌──────────────┐  通过 → 交付
│   Reviewer   │  校验数字/章节/建议，不通过最多返工一次
└──────────────┘
```

- **三种报告**：每日简报（300–500 字）、深度分析（600–1,200 字）、周期报告（500–900 字，可选 7/14/30 天）
- **轻量对话**：Agent Chat 只走 Collector + 单轮 LLM，低延迟问答
- **防幻觉**：LLM 只能接收 Collector 生成的数据包，Reviewer 要求每个数字都能溯源到数据包
- **降级链**：LLM 不可用时，退化为数据库字段直接拼接的模板简报

---

## 模型评估结果

评估协议：2,377 天 × 56 列数据，训练 1,901 天 / 测试 476 天（时间外），TimeSeriesSplit(5)，与基线同种子同口径。

| 模型 | R² | MAPE | WAPE | RMSE | MAE |
|---|---:|---:|---:|---:|---:|
| **FlowStack** | **0.8858** | **13.26%** | **10.66%** | **3661.2** | **2270.1** |
| XGBoost 基线 | 0.8709 | 15.40% | 12.82% | 3892.6 | 2729.7 |
| LightGBM 基线 | 0.8665 | 15.76% | 13.64% | 3958.2 | 2904.0 |
| RandomForest 基线 | 0.8586 | 15.19% | 13.01% | 4074.0 | 2768.8 |
| LSTM 基线 | 0.8578 | 14.25% | 11.12% | 4085.2 | 2366.8 |

FlowStack 在五项指标上均超过各自最强基线。详细对比见 [`appendix/baseline/flowstack_vs_baseline.md`](appendix/baseline/flowstack_vs_baseline.md)。

---

## 测试

```bash
# 后端主链路集成测试
cd backend
uv run pytest -q

# 前端类型检查 + 生产构建
cd frontend
pnpm build
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 19、TypeScript 5.9、Vite 7、原生 SVG/CSS |
| 后端 | Python 3.11+、FastAPI、Uvicorn、Pydantic、SQLite |
| 数据处理 | pandas、NumPy、OpenPyXL、xlrd、PyArrow |
| 模型 | LightGBM、XGBoost、CatBoost、scikit-learn、joblib |
| Agent | 纯 Python 状态机、OpenAI 兼容 Chat Completions、JSON Mode、ReportLab PDF |
| 测试 | pytest、FastAPI TestClient、TypeScript/Vite 构建 |

---

## 文档索引

- [`docs/DESIGN.md`](docs/DESIGN.md) — 数据看板视觉设计稿
- [`docs/FlowStack集成说明.md`](docs/FlowStack集成说明.md) — FlowStack 代码与数据接口说明
- [`docs/agent_report_plan.md`](docs/agent_report_plan.md) — 多 Agent 协作报告系统方案
- [`appendix/baseline/flowstack_vs_baseline.md`](appendix/baseline/flowstack_vs_baseline.md) — FlowStack 与基线对比

---

## 已知边界与生产化路线

当前实现是**核心业务闭环已完整跑通**的演示/答辩级系统，生产化需补强：

- **存储**：SQLite → PostgreSQL；原始文件 → 对象存储
- **任务**：同步分析 + Python 守护线程 → Celery/RQ/Arq + Redis（重试、超时、幂等、并发控制）
- **安全**：前端 Token 由 localStorage → HttpOnly Secure Cookie；补充 CSRF、限流、病毒扫描、审计
- **模型**：直接多步预测、分位数/Conformal 区间、漂移检测、自动回训
- **Agent**：数值引用程序化校验、Prompt 版本、离线评测、人工审批节点

## 宣传视频


https://github.com/user-attachments/assets/aa90aee1-1ebd-4f3a-9e35-48463bb91e21


