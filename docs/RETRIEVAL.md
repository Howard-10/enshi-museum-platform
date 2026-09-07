# 检索链路

在学校提供 embedding 模型前，系统先运行可验证的本地关键词检索：

```text
用户问题
  -> 目录中的文物名称、时代、地点、材质匹配
  -> Word 子 Chunk 的关键词匹配
  -> 返回原始资料引用
  -> 若问题请求图片、音频或视频，再返回对应 MinIO 短时链接
```

数据库已建立 `pg_trgm` 索引，用于提高中文 `ILIKE` 关键词检索速度。当前接口：

- `GET /api/v1/knowledge/search?query=...`
- `POST /api/v1/chat`

后续确认模型后，保留这条关键词召回，并追加：

```text
向量召回 + 关键词召回 -> RRF 融合 -> reranker -> LLM 生成带引文回答
```

这样无需重新导入 Word、Excel 或媒体资料。
