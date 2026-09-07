# 本机混合 RAG 与引用回答验证 v1.0

本版本默认运行“关键词检索演示模式”，不调用学校模型、Tavily 或旧项目三元组。所有真实调用均需同时满足环境变量与命令行确认。

## 固定开关

```text
EXTERNAL_MODEL_CALLS_ENABLED=false
EMBEDDING_INDEXING_ENABLED=false
HYBRID_RETRIEVAL_ENABLED=false
CHAT_GENERATION_ENABLED=false
WEB_SEARCH_ENABLED=false
```

启用顺序不可跳过：embedding 试点 → 人工批准 → 全量索引 → 混合检索评估 → 聊天生成评估。

## Phase 0：证据审核

生成候选不会修改 Word、Excel、媒体或旧项目：

```powershell
cd D:\恩施智能体\enshi-museum-platform\backend
.\.venv\Scripts\python.exe -m app.cli.generate_evidence_review_candidates
.\.venv\Scripts\python.exe -m app.cli.audit_evidence_review
```

- `document_evidence_reviews`：每份 Word 必有一个 `approved`、`rejected` 或 `needs_review` 状态。
- `artifact_document_links`：自动候选默认 `needs_review`，仅 `approved` 可作为模型回答的馆内事实证据。
- `artifact_aliases`：别名必须记录来源或审核说明，默认 `needs_review`。
- 历史媒体关联标记为 `legacy_verified`：可在演示中播放，但在正式 Evidence Gate 中仍需升级为 `approved` 才能作为已审核媒体证据。

审核 SQL 示例（仅审核后执行）：

```sql
UPDATE artifact_document_links
SET review_status = 'approved', review_note = '人工确认：标题与正文明确对应'
WHERE id = '<候选关系 UUID>';
```

## Phase 1–2：embedding

收到学校参数后先填写本机 `.env`，其中 `EMBEDDING_PROFILE_ID` 必须是新且稳定的版本号，例如 `school_embed_v1`。模型或服务版本改变时使用 `school_embed_v2`，绝不覆盖旧向量。

```powershell
# 仅创建 20 条 staging 试点；没有网络请求
.\.venv\Scripts\python.exe -m app.cli.index_embeddings --pilot

# 人工确认开关和学校额度后，才实际跑某个试点
.\.venv\Scripts\python.exe -m app.cli.index_embeddings --run-id <run UUID> --yes

# 20 条成功、无失败后人工批准 profile，再创建固定 vector(N) 正式表
.\.venv\Scripts\python.exe -m app.cli.index_embeddings --approve-pilot school_embed_v1
.\.venv\Scripts\python.exe -m app.cli.index_embeddings --provision-profile school_embed_v1

# 最后才运行全量；固定每批 20，成功相同哈希自动跳过，失败最多两次
.\.venv\Scripts\python.exe -m app.cli.index_embeddings --yes
```

正式索引字段：`chunk_id + embedding_profile_id`、文本哈希、向量、`pending/running/success/failed/skipped`、时间、错误类型、尝试次数。试点向量只在 staging JSON 中保存。

## Phase 3：混合检索验收

检索：关键词 Top20 与向量 Top20 → `RRF(d) = Σ 1 / (60 + rank_i(d))` → Top12 → 本地确定性重排 → 去重 → 3–5 父分块。

向量失败会自动回落到关键词，不会导致接口失败。混合检索验收前保持 `HYBRID_RETRIEVAL_ENABLED=false`。

```powershell
.\.venv\Scripts\python.exe -m app.cli.evaluate_retrieval ..\data\evaluation\retrieval-evaluation-cases.json ..\data\evaluation\semantic-evaluation-cases.json --report ..\data\reports\keyword-baseline.json
.\.venv\Scripts\python.exe -m app.cli.compare_retrieval_modes ..\data\reports\keyword-baseline.json ..\data\reports\hybrid.json
```

`semantic-evaluation-cases.json` 固定为 6 别名 + 6 口语 + 5 描述 + 3 多条件题。人工审核题目与预期文物后，再把它作为混合检索验收集；通过条件：语义 Hit@3 必须提高，且高优先级语义题零退化。

## Phase 4–5：回答与引用

Evidence Gate 是后端确定性规则，模型无权判断证据是否充分。目录字段优先级为 P1 目录结构化数据、P2 已审核文物 Word、P3 已审核背景资料；P1 不能被 Word 覆盖。

只有 Evidence Gate 为 `sufficient` 才会调用聊天模型。模型只收到 Evidence Pack；其输出必须是 `internal_answer`、`internal_citations`、`unverified_extension`。`CitationValidator` 会检查来源 ID 是否存在、重复或格式非法；失败时整条模型输出丢弃，返回本地证据降级结果。

## 降级链

```text
Hybrid + Chat
  ↓ 聊天异常或引用校验失败
Hybrid Evidence Only
  ↓ 向量异常
Keyword RAG
  ↓ 无已审核证据
Insufficient Evidence
```
