# 部署方式

开发阶段继续使用“Docker 运行 PostgreSQL、Redis、MinIO；Windows 本机运行前后端”。正式服务器可使用同一个 Compose 文件启动完整应用。

## 部署前检查

1. 复制 `.env.example` 为 `.env`，设置强密码。
2. 将 `FRONTEND_ORIGIN` 改为实际访问域名或服务器地址。
3. 保持 `EXTERNAL_MODEL_CALLS_ENABLED=false`，直到项目负责人确认模型接入。
4. 不要把 `.env`、E 盘原始资料或 MinIO 数据卷提交到 Git。

## 启动完整应用

```powershell
docker compose --profile app up -d --build
docker compose --profile app ps
```

默认访问地址：

- 前端：`http://服务器地址:8080`
- 后端接口：`http://服务器地址:8000/docs`
- MinIO 控制台：`http://服务器地址:9001`

前端容器会把 `/api/` 转发给后端，因此生产前端不会直接接触 PostgreSQL、Redis、MinIO 或本地磁盘路径。

## 常用运维命令

```powershell
docker compose --profile app logs backend
docker compose --profile app logs frontend
docker compose --profile app down
```

`docker compose --profile app down` 只停止容器；不要使用带 `-v` 的命令，除非已经备份并确认要删除所有本地数据库、缓存和对象存储数据。
