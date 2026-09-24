# 第二阶段：Word 文档入库

## 这一步做什么

每份 Word 文档会经历：

```text
原始 .docx
  → 提取纯文本
  → 清洗空白字符
  → 父 Chunk（较完整的上下文）
  → 子 Chunk（后续用于检索）
  → PostgreSQL 的 documents / document_chunks 表
```

当前默认按字符切分：父 Chunk 约 1500 字，子 Chunk 约 420 字。它不是最终检索参数；等拿到新 Word 资料后，需要用真实问题集评估并调整。

## 操作步骤

1. 将待导入 Word 放入 `data/raw/`，不要覆盖原始资料。首批 28 份资料的复制方式见 `docs/SEED_KNOWLEDGE_BASE.md`。
2. 启动 Docker 基础服务并执行 `alembic upgrade head`。
3. 在 `backend/` 运行：

```powershell
python -m app.cli.import_docx ..\data\raw
```

如果这一批资料都属于一个明确文物，可附加：

```powershell
python -m app.cli.import_docx ..\data\raw --artifact "虎钮錞于"

导入器会优先读取 Word 标题层级、列表和表格，再按章节生成父子分块。已有文件需要重建分块时，必须显式使用：

```powershell
python -m app.cli.import_docx ..\data\raw --infer-artifact-from-path --replace-existing
```

如果只需要重建数据库中已存在文档的章节分块、保留文档 ID 和审核记录，可以使用：

```powershell
python -m app.cli.reindex_docx ..\data
```

重建分块会使旧子块的向量失效；配置好当前 embedding profile 后，再运行现有的
`python -m app.cli.index_embeddings` 重建向量索引。
```

## 当前不做的事

- 不读取旧项目的 Parquet、BM25 或 Chroma 索引。
- 不把 Windows 文件路径保存给前端。
- 不在导入阶段调用 embedding API；模型确定后单独执行向量化任务。
