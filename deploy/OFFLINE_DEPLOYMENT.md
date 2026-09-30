# 离线一键部署

把 `deploy/` 下的离线部署目录完整复制到任意安装了 Docker Compose 的机器后，只需要编辑其中的 `.env`，然后运行：

```bash
chmod +x offline-deploy.sh
./offline-deploy.sh
```

脚本会自动导入 `enshi-museum-images-1.0.0.tar` 中的五个镜像、创建 `data/` 和 `volumes/` 下的持久化目录，并以 `--pull never` 模式启动所有容器，不会联网拉取镜像。

首次执行如不存在 `.env`，脚本会复制 `.env.example` 后安全退出；填写密码和公网地址后，再运行一次即可。

不要删除 `volumes/postgres`、`volumes/redis` 或 `volumes/minio`，这些目录分别保存数据库、缓存和媒体对象。
