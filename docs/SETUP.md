# 从零搭建步骤

## 0. 安装基础工具

在 Windows 上准备：

- Git
- Docker Desktop（开启 WSL 2 后端）
- Python 3.11+
- Node.js 20.19+ 或 22.12+

Vite 当前要求 Node.js `20.19+` 或 `22.12+`；LangGraph/LangChain 的当前 Python 安装要求至少 Python 3.10，本项目统一使用 3.11+。[Vite 文档](https://vite.dev/guide/)；[LangGraph 安装文档](https://docs.langchain.com/oss/python/langgraph/install)

## 1. 创建本地配置

在项目根目录执行：

```powershell
Copy-Item .env.example .env
```

首次本地运行可以保留端口不变，但必须把密码改成自己的值。真实 API Key 只允许写进 `.env`，不能提交 Git。

本项目当前采用“Docker 运行 PostgreSQL、Redis、MinIO；Windows 直接运行后端和前端”的开发方式，因此 `.env` 中的服务地址应保持为 `localhost`。

## 2. 启动基础服务

```powershell
docker compose up -d
docker compose ps
```

确认 PostgreSQL、Redis、MinIO 都显示为运行中。MinIO 控制台地址为 `http://localhost:9001`。

## 3. 启动后端

```powershell
cd backend
# 若本机安装了多个 Python，可用 py -3.11；否则直接使用 python。
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

浏览器打开 `http://localhost:8000/docs`。看到 `/api/v1/health` 即表示后端骨架正常。

## 4. 启动前端

另开一个 PowerShell：

```powershell
cd frontend
npm install
npm run dev
```

如果 PowerShell 报出“running scripts is disabled”，请把上面两行替换为：

```powershell
npm.cmd install
npm.cmd run dev
```

浏览器打开 `http://localhost:5173`。前端只通过 `src/api/client.ts` 调用后端。

## 5. 第一个验收动作

1. 访问前端页面。
2. 输入任意问题，例如“介绍虎钮錞于”。
3. 前端应请求 `POST /api/v1/chat`。
4. 后端返回工作流占位结果和结构化字段。

这一步只验证“前后端分离 + LangGraph 调用链”打通，还没有连接真实知识库。

## 6. 后续开发顺序

1. 建立 PostgreSQL 表和 Alembic 数据库迁移。
2. 实现 Word 清洗、父子 Chunk、embedding 入库脚本，见 `docs/INGESTION.md`。
3. 实现关键词检索、pgvector 检索、RRF、reranker。
4. 实现 MinIO 上传、媒体元数据和下载接口。
5. 实现 Redis + PostgreSQL 对话记忆。
6. 接入模型、浏览器检索和权限管理。
7. 完成前端聊天、文物库、资料管理后台。

## 常用排错命令

```powershell
docker compose logs postgres
docker compose logs redis
docker compose logs minio
docker compose down
```

停止服务不会删除数据；只有执行 `docker compose down -v` 才会删除本地数据库、缓存和对象存储卷。
