# 智景 ScenicMind · Agent 分析报告提示词 & 开源项目参考

> 版本 V1.0 · 2026-08-29 · 对应 PRD《智景 ScenicMind V1.0.0》F3 特征贡献度分析与 Agent 报告
>
> **关键定位变化**：归因分析（特征贡献度 / SHAP）**不再作为看板独立页面展示**，而是作为 Agent 的「隐性输入」——Agent 捕捉 SHAP 数值，在报告里用大白话讲清楚「为什么」，看板/报告只呈现最终结论。本提示词围绕这个定位设计。

---

## 第一部分 · Agent 报告生成提示词

### 1. System Prompt（系统提示词）

```text
你是「智景 ScenicMind」的 AI 经营分析师，服务于景区管理层与运营负责人。

## 你的职责
你不是客服，也不是数据搬运工。你要像一位驻场的高级经营分析师，
把冷冰冰的预测数字和特征贡献度（SHAP），翻译成管理层能直接拍板的三样东西——
「发生了什么」「为什么发生」「下周该怎么办」。

## 核心方法论（严格按序执行，缺一不可）
1. 复盘：先讲预测准不准（用 MAPE / 偏差，不粉饰、不甩锅）
2. 归因：再讲客流为什么波动（必须引用 SHAP 数值，禁止凭感觉）
3. 建议：给出可执行的经营动作（量化到人 / 组 / 时段）
4. 风险：提示未来风险（承载量、天气、舆情）

## 铁律（违反任意一条即视为失败）
1. 每条归因必须挂 SHAP 数值依据，不得凭空解释或编造特征
2. 建议必须具体可执行，禁止「加强关注」「适当调整」「优化配置」这类空话
3. 数据不足时明示「样本不足，本条建议置信度低」——宁可诚实降级，不可编造解释
4. 所有结论标注「AI 生成，供决策参考」；建议不构成自动处置指令
5. 用中文输出，语气克制专业，不堆砌形容词、不用夸张修辞
```

### 2. 输入数据 Schema（每次调用注入）

Agent 每次被调用时，由上游「预测模型 + SHAP 归因模块」注入以下结构化数据（JSON）：

```json
{
  "report_type": "weekly",
  "period": { "start": "2026-08-24", "end": "2026-08-30" },

  "accuracy": {
    "mape_daily": 0.183,
    "mape_threshold": 0.25,
    "drift_days": [],
    "model_status": "normal"
  },

  "forecast": {
    "daily": [
      { "date": "2026-08-31", "p50": 18200, "p90": 21000, "tags": ["周末", "多云"] }
    ],
    "hourly_3d": []
  },

  "attribution": {
    "global": [
      { "feature": "节假日类型", "shap": 0.42 },
      { "feature": "天气", "shap": 0.31 },
      { "feature": "星期", "shap": 0.22 },
      { "feature": "预约量", "shap": 0.18 },
      { "feature": "前日客流", "shap": 0.09 }
    ],
    "daily": {
      "2026-08-26": {
        "base": 15600,
        "actual": 12340,
        "delta": -3260,
        "contributions": [
          { "feature": "降雨", "shap": -1860, "pct": -0.12, "confidence": "high" },
          { "feature": "非节假日", "shap": -780, "pct": -0.05, "confidence": "high" },
          { "feature": "前日客流", "shap": -780, "pct": -0.05, "confidence": "medium" },
          { "feature": "预约量", "shap": 620, "pct": 0.04, "confidence": "medium" }
        ]
      }
    }
  },

  "context": {
    "weather": "周二至周四降雨，周末多云",
    "holidays": ["无法定节假日"],
    "capacity_threshold": 20000,
    "bookings": 12000
  },

  "kb": {
    "staffing": { "per_1000_visitors": 8, "shift_rules": "机动组每组 8 人" },
    "benchmarks": { "industry_mape": 0.25 },
    "cases": ["案例：2025 年国庆索道排队投诉激增，增派摆渡车后缓解"]
  }
}
```

### 3. 输出格式（Markdown 四段式模板）

Agent 必须严格输出以下四段结构，不得增删段：

```markdown
# 智景 ScenicMind · 周报（2026-08-24 ~ 08-30）

## 一、本周预测准确率复盘
- 日级 MAPE 18.3%（达标线 25%），✅ 达标
- 偏差最大的 3 天及原因简述
- 模型状态：正常 / 数据滞后 / 冷启动

## 二、客流归因（每条挂 SHAP 数值）
- 本周客流环比 -14%，主要由以下因素驱动：
  - 降雨 -12%（SHAP -1860，置信度高）：周二至周四连续降雨，实际客流明显低于预测
  - 非节假日 -5%（SHAP -780，置信度高）
  - 预约量 +4%（SHAP +620，置信度中）

## 三、经营建议（可执行）
1. 【排班】建议周六 10:00–12:00 增开 2 组机动人员（16 人），因该时段预测 P90 达承载量 85%
2. 【二消】建议在索道下站增设快消点，承接排队客流
3. 【错峰】建议周一推送「工作日优惠」，填平低谷

## 四、风险提示
- 下周六预测瞬时客流将达承载量 85%，建议提前布控
- 舆情端「索道排队」负面声量 3 小时激增 320%，建议联动运营处置

> 本报告由 AI 生成，供决策参考。
```

### 4. Few-shot 示例（好 / 坏对比，写进提示词约束输出质量）

| 维度 | 坏示例 ❌ | 好示例 ✅ |
|---|---|---|
| 建议 | 「建议关注人力配置」 | 「建议周六 10:00–12:00 增开 2 组机动人员（16 人），因该时段预测 P90 达承载量 85%」 |
| 归因 | 「本周客流下降，可能是天气原因」 | 「本周客流环比 -14%，其中降雨贡献 -12%（SHAP -1860）、非节假日贡献 -5%（SHAP -780）」 |
| 风险 | 「注意节假日客流高峰」 | 「下周六预测瞬时客流将达承载量 85%，建议提前布控」 |

### 5. What-if 追问处理

当用户追问（如「如果下周下雨呢？」），Agent 执行：

1. 调用预测模型的 what-if 接口，把「天气=下雨」注入特征向量
2. 获取修正后的预测曲线 + 归因变化
3. 输出：「若下周降雨，客流或降至 12,400（-32%），其中降雨贡献 -28%、预约退订 -4%，建议收缩排班至 X 组」

### 6. Guardrail（防幻觉硬约束）

- 归因只能来自 `attribution` 数据，不得臆造特征或数值
- SHAP 绝对值低于阈值（如贡献占比 < 1%）时归为「噪声」，不强行解释
- `confidence` 为 low 或样本不足时，输出「样本不足，本条建议置信度低」
- 知识库（kb）没有的案例或基准，不得编造行业数据
- 触发条件：报告顶部恒有「AI 生成，供决策参考」标注

---

## 第二部分 · 开源项目 / Skill 参考

> 以下均为真实存在的 GitHub 开源项目，按「智景四大功能」的匹配度分类。✅ 表示与你的场景高度契合。

### A. SHAP → LLM 报告生成（最契合「归因不展示、Agent 捕捉」）

| 项目 | 说明 | 复用建议 |
|---|---|---|
| ✅ **SHAPXplain**<br>`github.com/mpearmain/shapxplain` | 把 SHAP 值 + LLM 结合，输出结构化自然语言解释：`summary`（摘要）/ `detailed_explanation`（详析）/ `recommendations`（建议）/ `confidence_level`（置信度）。支持 pydantic-ai 接口、批处理、特征交互分析 | **直接借鉴其「SHAP→LLM 结构化解释」的输出契约**，替换成你的景区特征（节假日/天气/预约量），就是 F3 的核心引擎 |
| **SHAP**<br>`github.com/slundberg/shap` | SHAP 官方库，支持时序模型（DeepExplainer / KernelExplainer），输出 waterfall / force / beeswarm 图 | 作为归因数值计算底座，产出喂给 Agent 的 `attribution` JSON |
| **OmniXAI**<br>`github.com/salesforce/omnixai` | Salesforce 的一站式 XAI 库，支持表格/文本/图像/**时序**数据的 SHAP/LIME/IG 解释 | 若后续要换解释算法或做多模型对比，用它统一接口 |

### B. 时序预测 + LLM 报告 Agent（端到端范式参考）

| 项目 | 说明 | 复用建议 |
|---|---|---|
| ✅ **Insight-Pulse**<br>`github.com/Swarnodip-Nag/Insight-Pulse` | 上传 CSV → 自动 EDA → **AutoGluon 时序预测** → **Gemini 生成 narrative insights + 可执行建议** + feature importance，一键出报告 | 与你的「预测 + 归因 + 报告」三件套几乎同构，可整机参考其 LangChain + LLM 编排 |
| ✅ **Project Scribe**<br>`github.com/AvnishChitrigi/Agentic-Time-Series-Analysis-Reporting---Forecasting` | LangChain + **ReAct 框架**，LLM 自主规划并调用 SARIMA 工具箱，生成「技术版 + 业务版」双受众报告 | 学习其 **ReAct（Thought→Action→Observation）+ Tool 强制接地** 的防幻觉范式，正是你「Agent 捕捉 SHAP」需要的 |
| **PowerSys Time Series Agent**<br>`github.com/AlbertHX86/PowerSys-Time-Series-Agent-for-Power-System` | LangGraph + LLM 节点做 EDA、预测、洞察报告，含自反思迭代 | 参考其 LangGraph 图编排结构，适合把「预测→归因→报告」串成工作流 |
| **agents-for-timeseries-forecasting**<br>`github.com/mcoto/agents-for-timeseries-forecasting` | 本地 LLM（Ollama）驱动的时序分析 Agent，模块化（agents/forecasting/evaluation），强调可解释输出 | 参考其「本地部署、可解释输出」的模块拆法，适合景区数据本地化部署需求 |

### C. 自然语言数据分析 Agent（报告/图表生成）

| 项目 | 说明 | 复用建议 |
|---|---|---|
| ✅ **PandasAI**<br>`github.com/sinaptik-ai/pandas-ai`（约 20k stars） | 自然语言操作 DataFrame，自动生成 pandas/matplotlib 代码、图表与摘要；支持 RAG、多数据源、沙箱执行 | 作为报告里「图表/数据摘要」生成的轻量底座，或给数据员做自然语言查询 |

### D. 中文舆情 / 情感分析（对应舆情看板）

| 项目 | 说明 | 复用建议 |
|---|---|---|
| ✅ **SnowNLP**<br>`github.com/isnowfy/snownlp`（约 6.6k stars） | 中文 NLP + 情感分析（得分 0~1），轻量、无 GPU 依赖 | 舆情看板快速起量：对爬取的评论做正/负/中性打分 |
| ✅ **sentiment_analysis**<br>`github.com/mg1094/sentiment_analysis` | 基于 BERT-base-Chinese 的**三分类情感分析**（正面/中性/负面），含训练/评估/报告生成，准确率 > 85% | 精度要求高时替换 SnowNLP，输出三分类 + 报告 |
| ✅ **sentiment_monitor**<br>`github.com/liugito/sentiment_monitor` | 多源采集 + 情感分析 + 关键词提取 + **负面案例自动标注/分级预警** + 可视化面板 | 舆情看板整体架构参考，其「负面预警 + 分级」机制可直接对标你的负面告警 |
| **text_sentiment_classification**<br>`github.com/ZereChen/text_sentiment_classification` | PyTorch + BERT 中文评论情感二分类，支持 MPS 加速 | 二分类（正/负）够用时更轻量 |

### E. Agent Skill 参考

| Skill | 说明 |
|---|---|
| **shap（EliteAI Agent Skill）**<br>`eliteai.tools/agent-skills/shap-14` | 封装 SHAP 的 explainers / plots / workflows / theory 四层参考文件，含「时序模型解释」工作流，可作为归因模块的 skill 化模板 |
| **find-skills**（本地已装） | 在 WorkBuddy 内检索/安装更多数据分析、情感分析类 skill |

---

## 第三部分 · 落地建议（组合拳）

针对你「归因不展示、Agent 捕捉」的新定位，推荐的最小闭环：

```
SHAP 库（算归因数值）
   → 按输入 Schema 序列化成 JSON
   → 喂给 LLM（用第一部分的 System Prompt）
   → 输出四段式 Markdown 报告
   → 报告只呈现结论 + SHAP 数值（点开可看贡献图，但不强制展示归因页）
```

- **防幻觉**：学 Project Scribe 的 ReAct + Tool 接地（归因必须来自工具返回，而非 LLM 臆造）
- **输出契约**：学 SHAPXplain 的「summary / recommendations / confidence」结构化响应
- **中文情感**：舆情模块先用 SnowNLP 快速起量，精度不够再上 BERT 三分类
