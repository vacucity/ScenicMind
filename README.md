# 智景 ScenicMind 客流预测项目

本工作区已经合并产品前后端、数据上传流程与 FlowStack 客流预测算法。当前业务流程如下：

```text
注册 / 登录 → 上传客户数据 → 客流预测与特征贡献分析 → 数据看板
```

- 数据看板只展示未来 7D、14D、30D 客流预测与实际数据对比。
- 特征贡献度不在看板展示，保留给后续 Agent 生成报告。

## 当前目录

| 路径 | 用途 | 产品运行关系 |
|---|---|---|
| `ScenicMind/` | 已统一的 React + FastAPI 产品工程，包含注册、登录、上传与数据看板 | 主产品工程 |
| `src/flowstack/` | FlowStack 训练、预测、特征重要性与导出接口 | 核心算法代码 |
| `artifacts/flowstack/current/` | 已训练模型、元数据和指标 | 当前预测运行必需 |
| `configs/` | 数据源和算法配置 | 按具体运行流程使用 |
| `docs/FlowStack集成说明.md` | 算法调用和数据契约 | 开发对接文档 |
| `appendix/baseline/` | 旧基线实验和历史对比 | 仅供追溯，不参与产品运行 |
| `tests/` | 数据处理与旧接口测试 | 开发验证使用 |

## 当前对接边界

FlowStack 已提供相互独立的两个服务接口：

- `src.flowstack.service.PredictionService`：生成客流预测，供数据看板使用。
- `src.flowstack.service.ImportanceService`：生成特征贡献，供后续 Agent 使用。

具体输入字段、输出契约和调用方式见 `docs/FlowStack集成说明.md`。

`flowstack_eval.py` 是模型复现实验脚本，不参与 Web 产品日常运行。

Web 产品从 `ScenicMind/` 启动。后端保存每次分析的预测结果和特征贡献；看板只读取预测结果，后续 Agent 可通过 `/api/v1/analyses/{analysis_id}/importance` 获取特征贡献。启动命令、上传字段和完整接口见 `ScenicMind/README.md`。
