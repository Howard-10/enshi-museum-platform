# Excel 文物目录导入

本项目把 Excel 中“时代、文物名称、地点、材质、图片”这五列作为结构化目录，而不是把整张表转换成一段无结构文本。

## 保存方式

- `artifacts`：文物的标准名称；相同名称只保留一条。
- `artifact_catalog_records`：保留每一个来源行，包括来源工作簿、工作表、行号、原始字段和内容指纹。
- “（上一）”“（下左）”等版面注记保留为 `annotation`，不会创建文物。
- 完全相同的目录行会共享同一标准文物，但仍保留各自的来源行，便于审核。

## 执行顺序

先预检，生成报告但不写入数据库：

```powershell
cd "D:\恩施智能体\enshi-museum-platform\backend"
.\.venv\Scripts\python.exe -m app.cli.import_artifact_catalog "E:\恩施知识库\地方志材料  与  重点文物及其各时期背景材\恩施州民族博物馆 有关三交史的文物及其背景资料\明清 文物\文物清单-元明清.xlsx" `
  --knowledge-root "E:\恩施知识库" --dry-run `
  --report "E:\恩施知识库\迁移审核\artifact-catalog-dry-run.json"
```

确认报告后，去掉 `--dry-run` 再执行一次。

原始 Excel 文件不会被改写、移动或删除。
