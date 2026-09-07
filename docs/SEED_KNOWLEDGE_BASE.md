# 首批知识库资料

首批迁入的是 `enshi-core-docx-v1`，总计 **28 份 Word 文档，约 43.9 MB**。

它包含：

- 22 份重点文物或民俗文物资料；
- 6 份史前至隋、唐宋、明清、民俗、近代与“三交”史背景资料；
- 覆盖虎纽錞于、双鱼纹铜洗、盐湖陶釜、仙人洞崖葬、来凤仙佛寺石窟、唐崖土司城牌坊、西兰卡普、摆手舞、贺龙铁单刀等主题。

完整文件清单见 `data/knowledge_seed_manifest.json`。原始 Word 被复制到：

```text
data/raw/seed-v1/
```

## 为什么暂不迁入其他内容

- `.xlsx`：体积较大，且需要单独设计“表格行 → 结构化记录/Chunk”的导入规则；待数据库补齐后接入。
- 图片、视频、音频：将通过 MinIO 上传器进入对象存储，而不是拷贝后交给前端读取磁盘路径。
- 旧 Chroma、Parquet、BM25、视觉索引：均绑定旧项目格式，不能作为新系统的知识库来源。

## 重新复制资料

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\copy_seed_knowledge_base.ps1 `
  -SourceRoot "D:\恩施调研数据库\重点文物及其各时期背景材"
```

脚本使用相对路径清单；如原始资料换盘，只需传入新的根目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\copy_seed_knowledge_base.ps1 -SourceRoot "E:\资料\重点文物及其各时期背景材"
```

这里的 `Bypass` 只对这一次命令生效，不会修改电脑的 PowerShell 全局执行策略。
