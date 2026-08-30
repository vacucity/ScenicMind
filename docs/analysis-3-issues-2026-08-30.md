# ScenicMind 三个问题分析与解决方案

> 定位口径：只说明「需要改什么（WHAT）」，不展开具体实现步骤（HOW）。
> 排查时间：2026-08-30 · 基于当前代码与运行时实况。

---

## 问题 1：「今日入园进度」数据与现实不符

### 现象

看板右侧「今日入园进度」环形图显示 84.1%，但该数字与真实「今日已入园进度」毫无关系。

### 根因（三层语义错位）

当前实现位于 `frontend/src/features/dashboard/pages/DashboardPage.tsx` 的 `AdmissionProgress` 组件：

```ts
const latest = result.latestActual;         // 历史数据最后一天的「完整全天客流」
const next = result.forecastPoints[0];      // 预测第一天
const ratio = latest.visitors / next.predictedVisitors;  // 84.1%
```

1. **分子错位**：`latestActual.visitors` 是历史数据最后一天（如 08-28）的**全天已结束客流**（15,667 人），被当作「今日已入园」。真实的「今日已入园」应当是今日进行中的实时累计值——而整条数据链路（上传历史 xlsx + `indicators.py` 全量指标）里**根本没有实时入园数据源**。
2. **分母错位**：`forecastPoints[0]` 是「数据最新日 + 1」的预测点，被硬编码当作「今日预计入园」。当系统「今日」≠ 预测起点时，分母也不是「今日」的预测值。
3. **分子分母不是同一天**：分子是 D 日（08-28）真实值，分母是 D+1 日（08-29）预测值，二者根本构不成「进度」关系。84.1% = 「昨日真实 ÷ 明日预测」，语义彻底错位。

### 需要修正的逻辑点（WHAT）

1. **明确「今日」锚定**：以系统当前日期锚定「今日」，而非用数据最新日 / 预测起点推算。
2. **分子改为真实实时值**：接入「今日已入园」实时数据源（景区闸机 / 票务实时接口）。当前数据链路无此数据 → 该指标在无实时数据时**本质无法正确计算**。
3. **分母按日期精确匹配**：从 `forecastPoints` 中按「今日」日期精确取 `predictedVisitors`，而非写死 `forecastPoints[0]`。
4. **无实时数据时的降级语义**：改为有真实含义的指标——推荐「最新日预测达成率」（最新真实日真实值 ÷ 该日模型回测/预测值），或直接下线并标注「待接入实时入园数据源」，禁止用「昨日 ÷ 明日」冒充进度。

### 预期修正后的正确表现

- 接入实时数据后：展示「今日已入园 X 人 / 今日预计 Y 人 = Z%」，且 Z% 随当日实时入园递增、跨天正确回零。
- 未接入实时数据时：不再出现伪「进度」，改为「最新日达成率」或明确占位提示。

---

## 问题 2：「经营分析」特征重要性仅显示「历史客流走势」

### 现象

经营分析页的「客流影响因素」只显示「历史客流量趋势」一项（100%），天气、节假日、网络关注度、预约运营、交通等维度全部缺失。

### 根因（两层）

**直接原因**：当前命中的最新分析记录（`d502fb17`，08-30 01:02 上传）是 `fallback-v1`，其 importance 是 `backend/app/services/forecast.py` 第 277–284 行**写死的 3 个 history 特征**：

```python
"feature_importance": [
    {"feature": "visitors_lag_7", ...},
    {"feature": "visitors_lag_14", ...},
    {"feature": "visitors_roll_mean_7", ...},
]
```

`semantic_importance()` 聚合后只剩 `history = 100%`，其余 5 组因 importance=0 被 `if value <= 0: continue` 过滤。

**深层原因**：

1. `analyze_visitors` 中 `load_flowstack()` 在该记录生成时抛异常 → 静默降级到 `SeasonalLagFallback`（`model_version="fallback-v1"`）。
2. **降级分支的 feature_importance 硬编码为 3 个 history 特征**——这是设计缺陷：即使降级，也不该伪装成「只有历史客流在驱动」，应基于实际接入的数据源（`data_availability()` 已能识别）生成多维度解释，或明确标注「降级模型」。
3. `backend/.venv` 缺少 FlowStack 运行所需的 `lightgbm / xgboost / catboost / scikit-learn / scipy`（`pyproject.toml` 的 dependencies 未声明），模型加载处于脆弱不稳定状态——当前虽能 load+predict 成功（cloudpickle 打包了依赖），但任何版本不匹配都会触发静默降级。
4. 模型部署不一致：`model.joblib`（08-29 22:20 重写）与 `metadata.json`（02:28 旧，仍指向 `flowstack-20260828T182829Z`）版本不同步，存在训练/替换窗口期。

### 已验证结论

用同一份上传文件重跑 `analyze_visitors`，**当前可成功返回 FlowStack 引擎 + 完整 6 组语义贡献**：

| 维度 | 贡献度 |
|------|--------|
| 历史客流走势 | 42.9% |
| 节假日与季节 | 25.8% |
| 天气条件 | 11.9% |
| 网络关注度 | 10.6% |
| 预约与运营 | 8.0% |
| 交通可达性 | 0.9% |

### 应恢复展示的维度与呈现

- **6 个维度**，按贡献度降序（见上表），沿用现有 `FeatureContribution` 的横向条形 + 语义色（`GROUP_COLORS`）+ 分析文案（`GROUP_INSIGHT`）+ 「问 Agent」按钮——前端展示层无需大改，恢复 6 组数据即可。

### 需要修正的逻辑点（WHAT）

1. **修复降级机制**：fallback 分支的特征重要性不再写死 history，改为基于 `data_availability` 的可用数据源生成多维度贡献，或至少显式标注「降级模型，仅历史客流可用」。
2. **补齐并声明依赖**：`backend/pyproject.toml` 显式声明 `lightgbm / xgboost / catboost / scikit-learn / scipy` 并安装到 `.venv`，消除「能加载但脆弱」的状态。
3. **模型部署原子化**：`model.joblib` 与 `metadata.json` 版本保持一致，避免替换窗口期降级。
4. **前端兜底提示**：当 `semantic_groups` 仅 1 组时给出「降级模型」提示，避免用户误判「其他维度不重要」。
5. **存量数据刷新**：修复后需**重新上传/重新分析**刷新最新分析记录（已存在的 fallback 记录不会自动恢复）。

---

## 问题 3：「指标蓝图」改造为面向数据分析师的 Power BI 看板

### 调研结论

**可用 Skill**：`data-viz-2025`（LobeHub 社区，专门做交互式数据看板可视化，含库选型决策树、Tremor/shadcn-ui 推荐、framer-motion 动效、Tufte 数据墨水比原则）。SkillHub 官方 registry 无直接匹配的可视化 skill。

**可借鉴的开源图表组件库（GitHub）**：

| 库 | 定位 | 关键能力 | 适配判断 |
|----|------|---------|---------|
| **Tremor** (`@tremor/react`) | Vercel 收购、16k+ stars | KPI 卡、sparkline、bar list、tracker、35+ 组件 + 300+ blocks | 最贴近 Power BI 磁贴看板，但**强依赖 Tailwind** |
| **Ant Design Charts / AntV G2** | 企业级 BI | 自带 drill-down + brush 交互 | 交互最贴合 Power BI |
| **ECharts** (`echarts-for-react`) | 大数据集 | WebGL、dataZoom、brush、图例联动 | 大数据量首选 |
| **Recharts / Nivo** | 轻量 / 美观 | 组件式 / 主题化 | 上手快 |

### Power BI 核心交互范式（需借鉴）

1. **交叉筛选 cross-filter**：点击 A 图数据点，B 图自动过滤到该数据。
2. **交叉高亮 cross-highlight**：非选中数据变暗而非移除，保留上下文。
3. **切片器 slicer**：画布上的持久筛选控件（下拉 / 日期范围 / 按钮）。
4. **下钻 / 上卷 drill-down / drill-up**：同一视觉内从高聚合到明细层级。
5. **钻取 drill-through**：右键数据点导航到详情页，带返回按钮。
6. **KPI 卡置顶 + 条件格式**：核心指标卡放左上角，按值变色 / 图标 / 数据条。

### 技术选型判断

当前前端是**纯手写 SVG + 语义化色彩变量 + 复古美学**（零图表库依赖）。引入 Tremor（需 Tailwind）或 ECharts（重依赖）会破坏既有视觉体系与架构。**建议保持手写 SVG，借鉴 Power BI 交互范式 + Tremor 布局理念做「视觉 + 交互」升级**，而非引入重库。

### 需要改造的可视化模块与目标效果

| # | 模块 | 现状 | 目标效果 |
|---|------|------|---------|
| 0 | **全局布局** | 平铺 12 栅格 | Power BI 磁贴式 dashboard：顶部 KPI 卡行 + 主图区 + 侧辅助区，卡片错落、主次分明 |
| 1 | **KPI 卡（新增置顶）** | 无 | 8 模块核心数字抽成顶部 KPI 卡，数字滚动动画 + 环比涨跌箭头 + 条件格式变色 |
| 2 | **客流趋势** | 30 日静态柱状 | 支持 brush 缩放 + 悬停十字线 + 点击某天交叉高亮其它模块 |
| 3 | **承载与售罄** | 双仪表盘 | 点击「售罄日」下钻到售罄日历热力图 |
| 4 | **节假日效应** | 季节饼图 + sparkline | 点击季节切片，右侧曲线联动高亮该季节 |
| 5 | **天气影响** | 雨天/晴天对比柱 | 点击切换「降水 / 温度 / 风力」子指标 tab |
| 6 | **交通基建** | 前后对比柱 | 加开通前后趋势断点注释 |
| 7 | **网络热度** | 相关性仪表 + 面积折线 | 点击渠道（维基 / 微信）联动高亮 |
| 8 | **数据质量** | 堆叠分布 | 点击「缺失日期」下钻到缺失日历 |
| 9 | **预测准确率** | 环形图 | 加 drill-down 到月度 MAPE 趋势 |
| 10 | **全局交互层（新增）** | 无 | 切片器（数据源 / 日期范围）+ 交叉高亮状态管理 + 钻取详情抽屉 |
| 11 | **动效层（新增）** | 局部 transition | 数字滚动、图表入场/过渡动画（CSS transition + RAF 实现，避免重依赖） |
