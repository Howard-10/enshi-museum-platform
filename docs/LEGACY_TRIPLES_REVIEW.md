# 旧三元组审核

旧 Chroma 向量库只读保留在 `D:\恩施智能体\代码\enshi_rag_db\chroma.sqlite3`。它不会被本项目加载，也不参与问答。

导出审核表：

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli.export_legacy_triples "D:\恩施智能体\代码\enshi_rag_db\chroma.sqlite3" --csv ..\data\reviews\legacy-triples-review.csv --summary ..\data\reviews\legacy-triples-summary.json
```

输出中的每条关系初始都是 `pending`。缺失来源或重复的关系为 `high` 风险；在人工审核通过前，不写入平台数据库、不参与检索、不对游客展示。
