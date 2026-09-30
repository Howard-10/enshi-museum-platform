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

## 生产环境镜像一键部署

生产环境使用 `deploy/` 目录中的 `docker-compose.yml`。它不在运行时构建代码，而是使用两个应用镜像：

- `enshi-museum/backend:1.0.0`
- `enshi-museum/frontend:1.0.0`

PostgreSQL、Redis 和 MinIO 也使用 Docker 镜像，并通过 Compose 统一编排；数据库、Redis 和 MinIO 数据分别持久化到 `deploy/volumes/`，不会因为重新创建容器而丢失。

第一次部署：

```powershell
cd deploy
Copy-Item .env.example .env
# 编辑 .env，至少替换数据库密码、MinIO 密码、ADMIN_API_TOKEN、AUTH_SECRET、
# FRONTEND_ORIGIN 和 MINIO_PUBLIC_ENDPOINT
.\deploy.ps1 -Build
```

Linux 服务器：

```bash
cd deploy
cp .env.example .env
# 编辑 .env
BUILD=true ./deploy.sh
```

后续更新代码后：

```powershell
.\deploy\build-images.ps1 -Tag 2026-09-29
# 将 .env 中 BACKEND_IMAGE 和 FRONTEND_IMAGE 改成对应标签
.\deploy\deploy.ps1
```

如果服务器不能访问镜像仓库，可以在有网络的机器生成离线镜像包：

```powershell
cd deploy
.\package-images.ps1 -Tag 1.0.0
```

把 `.tar` 和项目文件上传服务器后执行：

```bash
docker load -i deploy/enshi-museum-images-1.0.0.tar
cd deploy
./deploy.sh
```

### 仅配置 `.env` 的离线一键部署

已导出镜像时，`deploy/` 本身就是可搬运的离线部署目录；也可以生成带版本号的副本：

```powershell
cd deploy
.\make-offline-package.ps1 -Version 1.0.0
```

将 `deploy/release/enshi-museum-offline-1.0.0/` 整个目录上传到任意安装 Docker 的机器。进入该目录后填写 `.env`：

```bash
cp .env.example .env
nano .env
chmod +x offline-deploy.sh
./offline-deploy.sh
```

该命令自动导入镜像、创建 `data/` 与 `volumes/` 持久化目录，并启动应用。详细说明见 `deploy/OFFLINE_DEPLOYMENT.md`。

应用源资料不要放进镜像。把资料上传到服务器项目的 `data/` 目录后，在后端容器内执行批量导入，例如：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec -T backend \
  python -m app.cli.import_docx /data --infer-artifact-from-path

docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec -T backend \
  python -m app.cli.import_media /data --types image audio video
```

也可以使用 `deploy/import-data.ps1` 导入 Word、目录 Excel、媒体或 Excel 内嵌图片。
