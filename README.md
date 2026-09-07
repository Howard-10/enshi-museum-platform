# 恩施博物馆智能导览平台

这是旧演示项目的独立重建版本。前端、后端、数据库、对象存储和资料导入相互分离；不依赖旧项目的本地路径、Parquet 或 Chroma 索引。

## 当前可以使用什么

- 本地关键词 RAG：从 Word 分块和文物目录中检索，返回资料引用；
- 文物目录：45 个标准文物、50 条可追溯 Excel 来源行；
- 媒体服务：170 个去重的图片、音频、视频对象，使用 MinIO 短时链接播放；
- 对话记忆：Redis 缓存最近消息，PostgreSQL 保存完整历史；
- 前端：聊天、馆藏筛选、媒体播放、历史记录；
- 离线检索评测：当前基础回归集 3/3 通过。

当前默认 **不调用任何真实模型 API**。系统处于 `keyword_rag` 模式；模型、向量检索、RRF 和真实 reranker 的接入条件见 [模型接入准备](docs/MODEL_SETUP.md)。

## 快速开始（本机开发）

```powershell
Copy-Item .env.example .env
docker compose up -d

cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开一个 PowerShell：

```powershell
cd "D:\恩施智能体\enshi-museum-platform\frontend"
npm.cmd run dev
```

- 前端：http://localhost:5173
- 接口文档：http://localhost:8000/docs
- 系统就绪状态：http://localhost:8000/api/v1/system/readiness
- MinIO 控制台：http://localhost:9001

可先提问：`介绍一下西瓜碑的音频`。

可随时运行以下只读检查；它不会调用模型：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-system.ps1
```

## 文档入口

- [项目路线图](docs/ROADMAP.md)：当前完成项与后续阶段；
- [目录说明](docs/PROJECT_MAP.md)：每个目录负责什么；
- [资料导入](docs/INGESTION.md)、[媒体导入](docs/MEDIA_INGESTION.md)、[Excel 目录导入](docs/EXCEL_CATALOG_INGESTION.md)；
- [检索链路](docs/RETRIEVAL.md) 与 [检索评测](docs/EVALUATION.md)；
- [对话记忆](docs/CONVERSATION_MEMORY.md)；
- [部署说明](docs/DEPLOYMENT.md)。

## 安全约束

- 原始资料始终保留在 `E:\恩施知识库`，旧项目资料仍保留在 D 盘；
- `.env` 只能保存在本机或服务器，不得提交 Git；
- `EXTERNAL_MODEL_CALLS_ENABLED=false` 是默认安全状态。只有项目负责人确认后才允许改成 `true`。
# 本机混合 RAG 与引用回答验证

当前实现和后续学校模型接入步骤见 [docs/HYBRID_RAG_V1.md](docs/HYBRID_RAG_V1.md)。默认不会调用任何真实模型或 Tavily。
