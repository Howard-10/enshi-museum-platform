# Tavily 外部搜索预留

未来的外搜供应商已选定为 Tavily，但当前没有填写 API Key，`WEB_SEARCH_ENABLED=false` 且月度额度为 `0`。因此聊天流程不会创建 Tavily 客户端，也不会发送任何网络请求。

启用前必须由负责人确认预算，并同时完成以下配置：

```env
WEB_SEARCH_ENABLED=true
WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=由负责人在本机或服务器填写
WEB_SEARCH_MONTHLY_REQUEST_LIMIT=由负责人填写正整数
```

代码只接受官方白名单域名：`ncha.gov.cn`、`mct.gov.cn`、`hubei.gov.cn`、`chnmuseum.cn`。适配器不用 Tavily 的 AI answer，只保留标题、链接和正文片段；返回域名会二次校验并写入审计表。外部资料只作一次回答的临时证据，绝不回写或覆盖馆藏档案。

正式接入聊天流程时还必须实现每次回答最多两次搜索、每次最多五条结果、Redis 一小时缓存和月度额度拦截。
