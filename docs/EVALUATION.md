# 离线评估与验收

本阶段的评估只访问本机 PostgreSQL、Redis 和 MinIO；不会构造聊天模型、embedding、reranker 或 Tavily 客户端。

## 题集

`data/evaluation/retrieval-evaluation-cases.json` 固定 60 条人工可核验问题：25 条精确文物、10 条口语化问法、10 条媒体请求、10 条背景资料、5 条应拒答问题。每条均包含预期文物或资料标题、最少引用数、媒体类型和人工参考结论。

## 运行

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli.evaluate_retrieval ..\data\evaluation\retrieval-evaluation-cases.json --report ..\data\reports\retrieval-evaluation.json
.\.venv\Scripts\python.exe -m app.cli.audit_platform_data --report ..\data\reports\platform-data-audit.json
```

报告目录被 Git 忽略，避免把每次本机运行时间和本地数据审计误提交到仓库。

## 当前离线基线（2026-08-12）

- 60/60 通过；高优先级问题 100% 通过。
- 文物 Hit@1：93.33%；Hit@3：97.78%；Hit@5：100%。
- 媒体类型命中率：100%；应拒答问题处理正确率：100%。
- `external_model_calls=0`、`web_search_calls=0`。

模型接入后必须复用同一题集；只有高优先级和媒体结果不退化、Hit@3 不低于 90% 时，才允许启用混合检索。
