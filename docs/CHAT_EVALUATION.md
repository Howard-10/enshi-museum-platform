# 聊天回答评测

## 评测集

固定评测集位于：

`data/evaluation/chat-evaluation-cases.json`

共 20 条：

- 10 条文物事实与背景问题
- 3 条别名、口语化问题
- 1 条描述式问题
- 3 条图片、音频、视频请求
- 3 条资料不足问题

## 运行方式

Docker Desktop 在 Windows 下运行完整评测：

```powershell
docker compose --profile app run --build --rm `
  -v "D:\恩施智能体\enshi-museum-platform\data\evaluation:/app/evaluation:ro" `
  -v "D:\恩施智能体\enshi-museum-platform\data\reports:/app/reports" `
  backend python -m app.cli.evaluate_chat_answers `
  --report /app/reports/chat-answer-evaluation-v1-final.json
```

只复测指定题目：

```powershell
docker compose --profile app run --rm `
  -v "D:\恩施智能体\enshi-museum-platform\data\evaluation:/app/evaluation:ro" `
  -v "D:\恩施智能体\enshi-museum-platform\data\reports:/app/reports" `
  backend python -m app.cli.evaluate_chat_answers `
  --ids "alias-04,media-01" `
  --report /app/reports/chat-answer-evaluation-targeted.json
```

评测工具会自动重试短暂的网络断开；它检查引用数量、证据状态、媒体类型、文物或来源命中以及资料不足时是否拒答。

## 人工复核

自动通过不等于回答内容已经完成专家审核。报告中的每条结果还需要人工填写：

- 引用是否合法
- 回答是否被证据支持
- 是否编造馆藏事实
- 馆内回答与通用拓展是否分离
- 展示是否易于理解

本轮完整评测先得到 `19/20`；唯一失败的描述式问题经过“文物名称片段匹配”修复后，定向复测 `1/1` 通过。对应报告：

- `data/reports/chat-answer-evaluation-v1-final.json`
- `data/reports/chat-answer-evaluation-descriptive-fix.json`

本轮没有启用 Tavily，也没有修改旧项目和旧向量库。
