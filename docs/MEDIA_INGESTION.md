# 媒体资料导入

媒体原文件始终保留在 `E:\恩施知识库`；系统只将副本上传到 MinIO。PostgreSQL 的
`media_assets` 表保存元数据，不保存 Windows 本地绝对路径。

## 导入规则

- 支持 `.m4a`、`.mp3`、`.wav`、`.jpg`、`.jpeg`、`.png`、`.webp`、`.mp4`、`.mov`、`.avi`。
- 每个文件先计算 SHA-256。MinIO 对象键为 `media/<类型>/<哈希前两位>/<完整哈希>.<扩展名>`，
  因此重复运行不会覆盖已有对象。
- 数据库再次按 SHA-256 去重。已有媒体记录会跳过。
- 去重后的同一对象仍可通过 `artifact_media_links` 关联多个文物，不会因去重丢失归属。
- 音频及层级图片/视频依据上级文件夹关联文物，并标记为 `folder`。
- `图生视频库` 下的平铺视频不自动关联文物，只保留文件名候选并标为 `review`，避免错误归属。

## 先做小批验证

在 `backend/` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m app.cli.import_media "E:\恩施知识库" `
  --types audio --limit 1 `
  --report "E:\恩施知识库\迁移审核\media-import-check.json"
```

## 全量导入

```powershell
.\.venv\Scripts\python.exe -m app.cli.import_media "E:\恩施知识库" `
  --report "E:\恩施知识库\迁移审核\media-import-full.json"
```

可先使用 `--dry-run` 只生成清单，不上传或写入数据库。

## 前端或 Agent 获取媒体

后端只返回短时效 MinIO 下载链接，不返回 E 盘本地路径：

- `GET /api/v1/media?artifact=西瓜碑&media_type=audio`：列出一个文物的媒体记录。
- `GET /api/v1/media/{media_asset_id}/download-url`：获取 10 分钟有效的播放或下载链接。

对于大文件或中断后的续传，可按顶层资料目录分批运行：

```powershell
.\.venv\Scripts\python.exe -m app.cli.import_media "E:\恩施知识库" `
  --types video --source-categories "图生视频库"
```

## 生成完整审核报告

以下命令会逐项检查 E 盘源文件哈希、数据库记录与 MinIO 对象大小：

```powershell
.\.venv\Scripts\python.exe -m app.cli.audit_media "E:\恩施知识库" `
  --report "E:\恩施知识库\迁移审核\media-final-audit.json"
```

## Excel 内嵌图片

图片型 Excel 使用 `DISPIMG` 单元格公式。导入程序只提取能够对应到同一行文物名称的图片，
并把来源工作簿、工作表、单元格和压缩包内图片部件写入审核报告。

```powershell
.\.venv\Scripts\python.exe -m app.cli.import_xlsx_images "E:\恩施知识库" `
  --report "E:\恩施知识库\迁移审核\xlsx-image-import.json"
```

没有单元格映射的内嵌图片不会自动绑定文物，会在报告的 `issues` 中等待审核。
