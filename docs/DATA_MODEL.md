# 第一阶段：数据模型

这一版数据模型完全重新设计，不沿用旧项目的 JSON 路径、Parquet 索引或本地文件搜索方式。

## 关键表

| 表 | 用途 |
| --- | --- |
| `artifacts` | 文物或文化主题的标准名称、别名、年代、分类 |
| `documents` | 一份原始 Word 资料及其清洗后的全文 |
| `document_chunks` | 父/子 Chunk，后续存关键词索引和向量 |
| `media_assets` | MinIO 文件的元数据，绝不保存 Windows 磁盘路径 |
| `users` | 登录与角色 |
| `conversations` | 会话主记录 |
| `conversation_messages` | 可追溯的完整对话消息、引用和媒体 |

## 为什么先不创建向量索引

向量维度由 embedding 模型决定。学校免费模型尚未确认时，先保留 `vector` 字段，暂不创建 HNSW/IVFFlat 索引。模型确定后再用一次数据库迁移固定维度并建立索引，避免以后整库重建。

## 应用迁移

基础服务启动后，在 `backend/` 执行：

```powershell
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

这一步只创建空表，不会导入旧项目数据。
