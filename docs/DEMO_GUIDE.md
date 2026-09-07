# 教师演示手册

## 启动顺序

1. 在项目根目录执行 `docker compose up -d`，启动 PostgreSQL、Redis 和 MinIO。
2. 在 `backend` 目录执行迁移并启动 API。
3. 在 `frontend` 目录执行 `npm.cmd run dev`，访问 `http://localhost:5173`。
4. 打开首页的“系统就绪状态”：应看到检索为 `keyword RAG`，模型关闭，Tavily 外搜关闭。

## 推荐演示问题

1. `请介绍一下唐崖长官司印`：展示馆内资料引用、目录命中和“仅依据馆内资料”范围标签。
2. `西瓜碑音频`：展示 MinIO 的短时媒体链接和播放器。
3. `馆藏里有外星人文物吗`：展示“本地资料不足”提示，说明系统不会编造馆藏事实。

## 如何证明本轮没有调用真实模型

运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-system.ps1
```

结果中的 `ExternalModelCallsEnabled=False` 与 `WebSearchEnabled=False` 必须同时成立。再打开最近的 `data/reports/retrieval-evaluation-*.json`，其中应显示 `external_model_calls: 0` 和 `web_search_calls: 0`。
