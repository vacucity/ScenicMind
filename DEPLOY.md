# 智景 ScenicMind 部署文档

## 项目概述

智景 ScenicMind 是面向景区运营的客流预测与决策支持平台。
- 前端：React + TypeScript + Vite，打包为静态文件
- 后端：FastAPI (Python 3.11+)，端口 8001
- 模型：FlowStack 堆叠集成模型（LightGBM/XGBoost/CatBoost + Ridge 元学习器）
- 数据：九寨沟日客流历史数据（2019-09-27 ~ 2025-03-24）

## 目录结构

```
项目根目录/
├── frontend/dist/          # 前端打包产物（静态文件，Nginx 托管）
├── backend/                # 后端代码
│   ├── app/                # FastAPI 应用
│   ├── data/               # 九寨沟客流数据
│   │   └── jiuzhaigou_daily.csv
│   ├── .venv/              # Python 虚拟环境（服务器上重新创建）
│   ├── .env                # 环境变量（DEEPSEEK_API_KEY）
│   └── pyproject.toml      # Python 依赖声明
├── artifacts/flowstack/    # FlowStack 模型产物
│   └── current/model/
│       └── model.joblib    # 训练好的模型文件
└── src/flowstack/          # FlowStack 模型代码
```

## 部署步骤

### 1. 环境准备

```bash
# Python 3.11+
python3 --version

# Node.js 18+（仅打包需要，服务器上可不装）
```

### 2. 后端部署

```bash
cd backend

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate    # Linux
# .venv\Scripts\activate     # Windows

# 安装基础依赖
pip install fastapi uvicorn[standard] python-dotenv pydantic

# 安装 ML 依赖（FlowStack 模型推理需要）
pip install numpy pandas scikit-learn lightgbm xgboost catboost pyarrow joblib

# 配置环境变量（可选：配置后 Agent 对话使用 LLM，不配则用规则引擎）
cat > .env << 'EOF'
DEEPSEEK_API_KEY=your_api_key_here
EOF

# 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

验证后端是否正常：
```bash
curl http://127.0.0.1:8001/api/v1/module-one/output
# 应返回 JSON，包含九寨沟客流预测数据
```

### 3. 前端部署

前端已打包为静态文件，位于 `frontend/dist/`。

用 Nginx 托管：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

### 4. 模型文件

确保以下文件存在于服务器上：

| 文件 | 路径 | 说明 |
|------|------|------|
| model.joblib | artifacts/flowstack/current/model/ | FlowStack 训练好的模型 |
| jiuzhaigou_daily.csv | backend/data/ | 九寨沟历史客流数据 |
| flowstack/ | src/flowstack/ | 模型代码（Python 包） |

后端启动时会自动加载模型和数据。如果模型文件缺失，后端会降级为季节滞后模型（SeasonalLagFallback），仍可运行但预测精度降低。

### 5. 进程管理（推荐 systemd）

```ini
# /etc/systemd/system/scenicmind-backend.service
[Unit]
Description=ScenicMind Backend
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/backend
ExecStart=/path/to/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable scenicmind-backend
sudo systemctl start scenicmind-backend
```

## 关键配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 后端端口 | 8001 | 必须为 8001，前端 API 代理指向此端口 |
| DEEPSEEK_API_KEY | 无 | 配置后 Agent 使用 LLM 对话，不配则用规则引擎 |
| 模型路径 | artifacts/flowstack/current/model/ | FlowStack 模型加载路径 |
| 数据路径 | backend/data/jiuzhaigou_daily.csv | 九寨沟历史客流数据 |

## 健康检查

```bash
# 模块一（客流预测）
curl http://127.0.0.1:8001/api/v1/module-one/output | python3 -m json.tool

# 模块二（经营报告）
curl http://127.0.0.1:8001/api/v1/module-two/output | python3 -m json.tool

# Agent 报告
curl http://127.0.0.1:8001/api/v1/agent/report | python3 -m json.tool
```

## 常见问题

**Q: 后端启动报 `ModuleNotFoundError: No module named 'lightgbm'`**
A: 安装 ML 依赖：`pip install lightgbm xgboost catboost pyarrow joblib`

**Q: 前端页面空白或 404**
A: Nginx 需配置 `try_files $uri $uri/ /index.html;`（React SPA 路由）

**Q: Agent 对话返回规则引擎结果而非 LLM**
A: 在 `backend/.env` 中配置 `DEEPSEEK_API_KEY` 并重启后端

**Q: 模型加载失败，预测结果异常**
A: 检查 `artifacts/flowstack/current/model/model.joblib` 是否存在；缺失时后端自动降级为 fallback 模型
