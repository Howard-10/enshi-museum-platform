# 向量索引接入说明

当前数据库只保存向量字段和索引元数据，尚无向量值；学校确认 embedding 服务前，不允许索引任务进行外部调用。

检查计划（安全，不联网）：

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli.index_embeddings --limit 20
```

取得学校提供的模型名、OpenAI 兼容地址、向量维度、限流与费用确认后，先只处理 20 个子分块。命令必须同时满足 `.env` 中 `EXTERNAL_MODEL_CALLS_ENABLED=true` 和命令行 `--yes` 才会真正发请求。

通过维度、耗时和离线题集回归后，再固定 `vector(N)` 列并增加余弦距离 HNSW 索引。检索顺序为关键词前 20 + 向量前 20 → RRF（k=60）→ 前 12 → reranker/本地降级 → 3–5 个父分块证据。
