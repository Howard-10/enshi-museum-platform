# 模型接入准备

当前版本已完成关键词检索、原始资料引用、媒体返回和对话记忆。学校确认模型后，使用 OpenAI 兼容接口接入，不需要重新导入任何资料。

后端已经按 `langchain>=1`、`langchain-openai>=1`、`langgraph>=1` 的接口准备了受保护的客户端工厂。开关关闭时，客户端不会被创建，因此不会产生模型请求或费用。

请向学校或项目负责人确认以下信息：

1. 聊天模型：模型名、接口地址、密钥获取方式。
2. Embedding 模型：模型名、接口地址、**向量维度**、调用限额。
3. Reranker：是否提供、模型名、接口地址、密钥获取方式。
4. 是否允许服务器调用外网模型接口，以及是否有 IP 白名单要求。

将信息填入项目根目录的 `.env`（不要提交或发送密钥）：

```dotenv
LLM_API_KEY=学校提供的密钥
LLM_BASE_URL=https://学校提供的接口地址/v1
CHAT_MODEL=学校提供的聊天模型名

EMBEDDING_API_KEY=学校提供的密钥
EMBEDDING_BASE_URL=https://学校提供的接口地址/v1
EMBEDDING_MODEL=学校提供的向量模型名
EMBEDDING_DIMENSIONS=学校确认的维度

RERANKER_API_KEY=学校提供的密钥
RERANKER_BASE_URL=https://学校提供的接口地址
RERANKER_MODEL=学校提供的重排序模型名

# 默认必须为 false；经项目负责人确认后才改为 true。
EXTERNAL_MODEL_CALLS_ENABLED=false
```

其中 `EMBEDDING_DIMENSIONS` 必须准确。它决定 pgvector 索引的维度；确认后再创建向量索引并批量写入 10,345 个 Word 子分块，避免后续重建。

当前系统会把模型就绪状态暴露在 `GET /api/v1/system/readiness`；该接口只返回缺少哪些配置和资料数量，绝不会返回密钥内容。
