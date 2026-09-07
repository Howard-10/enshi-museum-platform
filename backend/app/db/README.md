# 数据层

后续会在这里增加：

- `session.py`：SQLAlchemy 异步会话。
- `models/`：PostgreSQL ORM 模型。
- `migrations/`：Alembic 迁移文件。

不要在 API 路由中直接写 SQL；通过 `repositories/` 访问这里的模型。
