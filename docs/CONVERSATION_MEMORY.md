# 对话记忆

系统采用“Redis + PostgreSQL”双层方案：

```text
一次问答完成
  -> PostgreSQL 保存用户消息、回答、引用和媒体信息（完整可追溯）
  -> Redis 缓存当前会话最近 20 条消息（7 天过期）
  -> 历史页面优先读取 Redis；缓存缺失时自动从 PostgreSQL 恢复并回填缓存
```

接口：

- `POST /api/v1/chat`：完成检索与回答后自动写入双层存储。
- `GET /api/v1/chat/{session_id}/history`：返回最近消息，并在 `source` 标注读取自 `redis` 或 `postgresql`。

原始对话不会存放在浏览器，也不会使用 Windows 本地文件作为数据库。
