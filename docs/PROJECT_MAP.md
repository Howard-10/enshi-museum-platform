# 项目目录说明

```text
enshi-museum-platform/
├── backend/                 # 所有服务端代码；只由后端维护
│   ├── app/
│   │   ├── api/             # HTTP 接口层：接收请求、返回响应，不写业务规则
│   │   ├── core/            # 配置、日志、安全等全局能力
│   │   ├── db/              # 数据库连接、ORM 模型、迁移入口
│   │   ├── graphs/          # LangGraph 工作流：意图→检索→评估→回答
│   │   ├── repositories/    # 数据读写封装：文档、媒体、会话等
│   │   ├── schemas/         # API 请求与响应的数据结构
│   │   ├── services/        # 业务能力：RAG、媒体、记忆、权限
│   │   └── main.py          # FastAPI 应用入口
│   ├── tests/               # 后端自动化测试
│   ├── pyproject.toml       # Python 依赖与工具配置
│   └── Dockerfile           # 后端容器构建文件
├── frontend/                # 所有浏览器端代码；不允许直连数据库/MinIO
│   ├── src/api/             # 调用后端 API 的唯一入口
│   ├── src/components/      # 通用界面组件
│   ├── src/features/        # 按业务组织的页面功能，例如聊天、文物管理
│   ├── src/pages/           # 页面级组件
│   └── src/types/           # 前端数据类型
├── infra/                   # Docker 初始化、反向代理、运维配置
├── data/                    # 本地导入资料的临时落点，不提交 Git
│   ├── raw/                 # 原始 Word、图片、视频等
│   ├── processed/           # 清洗后的中间结果
│   └── imports/             # 每次导入的日志与报告
├── docs/                    # 任何成员都应先阅读的说明
├── scripts/                 # 可重复执行的本地脚本
├── .env.example             # 配置模板，不能保存真实密码或 API Key
└── docker-compose.yml       # PostgreSQL、Redis、MinIO 本地编排
```

## 代码放置规则

| 需求 | 应放位置 |
| --- | --- |
| 新增一个 HTTP 接口 | `backend/app/api/v1/` |
| 新增数据库表 | `backend/app/db/models/` |
| 文档入库、混合检索、重排序 | `backend/app/services/` |
| 多步骤 Agent 流程 | `backend/app/graphs/` |
| 文件上传、预签名媒体地址 | `backend/app/services/media_service.py` |
| 前端调用后端 | `frontend/src/api/` |
| 页面上的聊天区域 | `frontend/src/features/chat/` |
| 数据库/MinIO/Redis 配置 | 根目录 `.env`，不要写进代码 |
