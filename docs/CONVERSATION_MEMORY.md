# 对话记忆

系统采用“Redis + PostgreSQL”双层方案：

```text
一次问答完成
  -> PostgreSQL 保存用户消息、回答、引用和媒体信息（完整可追溯）
  -> Redis 缓存当前会话最近 20 条消息（7 天过期）
  -> 历史页面优先读取 Redis；缓存缺失时自动从 PostgreSQL 恢复并回填缓存

下一次提问
  -> 读取最近 6 条消息（最近 3 轮）做“它、刚才那件文物、这件”等指代消解
  -> 用改写后的问题执行关键词/标题/向量/媒体检索
  -> 最终模型上下文使用最近 10 条消息，并同时包含原始问题、改写问题、系统提示词和本轮证据
  -> 对话消息保存 original_query、retrieval_query、改写状态和检索轨迹
  -> 本轮回答完成后继续写回 PostgreSQL 和 Redis
```

接口：

- `POST /api/v1/chat`：完成检索与回答后自动写入双层存储。
- `GET /api/v1/chat/{session_id}/history`：返回最近消息，并在 `source` 标注读取自 `redis` 或 `postgresql`。

原始对话不会存放在浏览器，也不会使用 Windows 本地文件作为数据库。

当前实现不依赖额外的 LangGraph checkpointer：会话事实仍由现有的 PostgreSQL + Redis 记忆服务负责，
LangGraph 继续负责本轮意图和证据链路。这样即使外部模型调用关闭，简单追问也能通过检索改写继承上一轮主题。
