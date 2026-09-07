# 服务层

服务层承载业务能力，计划包括：

- `ingestion_service.py`：Word 清洗、父子 Chunk、入库。
- `retrieval_service.py`：关键词检索、向量检索和 RRF。
- `reranker_service.py`：候选文档重排序。
- `media_service.py`：MinIO 上传、预签名 URL、权限校验。
- `memory_service.py`：Redis 短期记忆和 PostgreSQL 长期记忆。

图工作流只编排这些服务，不在节点内复制数据库或 MinIO 代码。
