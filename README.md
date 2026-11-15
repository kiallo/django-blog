# Django 博客 API

基于 Django 6 + Django REST Framework 实现的博客后端，接口设计对标
[RealWorld](https://github.com/gothinkster/realworld) 规范。

## 技术栈

| 组件      | 选型                               |
| --------- | ---------------------------------- |
| 框架      | Django 6.1 + DRF 3.18              |
| 认证      | JWT（simplejwt）+ Redis 白名单     |
| 缓存/会话 | Redis                              |
| 数据库    | SQLite（生产可换 PostgreSQL）      |
| API 文档  | drf-spectacular（Swagger / ReDoc） |

## 快速开始

````bash
# 1. 创建虚拟环境 {#1-创建虚拟环境  data-source-line="1198"}
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux {#source-venvbinactivate------macos--linux  data-source-line="1201"}

# 2. 安装依赖 {#2-安装依赖  data-source-line="1203"}
pip install -r requirements.txt

# 3. 起 MySQL 与 Redis（见下节「本地起 MySQL + 跑测试」）
## 本地起 MySQL + 跑测试

数据库已从 SQLite 迁移到 **MySQL 8.4**（Django 6.1 的硬性要求，8.0 会在 `migrate` 时报版本不支持），
Redis 用独立容器。以下命令 Windows PowerShell / Git Bash 均可执行。

```bash
# 1. 起 MySQL（宿主 3307 → 容器 3306）
#    用 3307 是为了避开本机 3306 上可能已有的 MySQL 8.0
docker run -d --name blog-mysql \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=blog \
  -e MYSQL_USER=blog \
  -e MYSQL_PASSWORD=blogpass \
  -p 3307:3306 \
  mysql:8.4

# 2. 起 Redis（宿主 16379 → 容器 6379）
#    ⚠️ 不能用 6379：Windows 的 winnat 把 6289–6388 整段预留，
#    绑定会报 "An attempt was made to access a socket in a way forbidden by its access permissions"
docker run -d --name blog-redis -p 16379:6379 redis:7-alpine

# 3. 授权测试库（Django 跑测试会 CREATE/DROP test_blog，必须单独授权）
docker exec -it blog-mysql mysql -uroot -prootpass
#   在 mysql> 提示符下执行这两条：
#     GRANT ALL PRIVILEGES ON `test_blog`.* TO 'blog'@'%';
#     FLUSH PRIVILEGES;
#   然后 exit

# 4. 配置环境变量（.env 已在 .gitignore 里，不会进仓库）
cp .env.example .env

# 5. 建表 + 造演示数据（需要先有 kiallo 这个用户，见 demos/seed_demo_articles.py 第 35 行）
python manage.py migrate
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.get_or_create(username='kiallo', defaults={'is_staff': True, 'is_superuser': True})"
python demos/seed_demo_articles.py

# 6. 跑测试（62 个用例，全程 fakeredis，不需要 Redis 真的在跑）
python manage.py test

# 7. 覆盖率
pip install coverage
coverage run manage.py test
coverage report -m --include="blog/*"

# 4. 建表 {#4-建表  data-source-line="1208"}
python manage.py migrate

# 5. 创建管理员 {#5-创建管理员  data-source-line="1211"}
python manage.py createsuperuser

# 6. 启动 {#6-启动  data-source-line="1214"}
# ⚠️ 必须显式写 18000。Django 默认的 8000 落在 Windows 保留端口段里（约 1024–15000），
#    会报 [WinError 10013] 权限不允许 —— 注意不是「端口已被占用」。
python manage.py runserver 18000
``` {data-source-line="1216"}

访问：
- API 文档：http://127.0.0.1:18000/api/docs/
- 管理后台：http://127.0.0.1:18000/admin/
- API 根目录：http://127.0.0.1:18000/api/v3/

## 接口一览

| 接口 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/v3/auth/register/` | POST | 匿名 | 注册 |
| `/api/v3/auth/login/` | POST | 匿名 | 登录，返回 access + refresh |
| `/api/v3/auth/refresh/` | POST | 匿名 | 刷新 access |
| `/api/v3/auth/logout/` | POST | 必须 | 登出（删 Redis 会话） |
| `/api/v3/auth/me/` | GET | 必须 | 当前用户 |
| `/api/v3/auth/my-session/` | GET | 必须 | 我的会话详情 |
| `/api/v3/auth/force-logout/` | POST | 管理员 | 强制某用户下线 |
| `/api/v3/auth/online/` | GET | 管理员 | 在线用户列表 |
| `/api/v3/articles/` | GET | 匿名 | 文章列表（分页/搜索/排序/过滤） |
| `/api/v3/articles/` | POST | 必须 | 创建文章 |
| `/api/v3/articles/<slug>/` | GET | 匿名 | 文章详情 |
| `/api/v3/articles/<slug>/` | PUT/PATCH | 作者或管理员 | 更新文章 |
| `/api/v3/articles/<slug>/` | DELETE | 作者或管理员 | 删除文章 |
| `/api/v3/articles/<slug>/comments/` | GET/POST | 读匿名/写必须 | 评论列表 / 发表评论 |
| `/api/v3/articles/<slug>/favorite/` | POST/DELETE | 必须 | 收藏 / 取消收藏 |
| `/api/v3/articles/stats/` | GET | 匿名 | 站点统计 |
| `/api/v3/comments/<id>/` | GET | 匿名 | 评论详情 |
| `/api/v3/comments/<id>/` | PUT/PATCH/DELETE | 评论作者 | 改 / 删评论 |
| `/api/v3/tags/` | GET | 匿名 | 标签列表 |
| `/api/v3/tags/<name>/` | GET | 匿名 | 标签详情 |

## 认证方式

```bash
# 1. 登录拿 token {#1-登录拿-token  data-source-line="1251"}
curl -X POST http://127.0.0.1:18000/api/v3/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"yourname","password":"yourpass"}'

# 2. 后续请求带上 access token {#2-后续请求带上-access-token  data-source-line="1256"}
curl http://127.0.0.1:18000/api/v3/auth/me/ \
  -H "Authorization: Bearer <access>"
``` {data-source-line="1259"}

## 设计要点

- **JWT + Redis 白名单**：纯 JWT 无法撤销，登出/强制下线靠 Redis 会话白名单实现。
  每次认证多一次 Redis 查询，换来"真登出"和"单点登录"。
- **读/写序列化器分离**：`ArticleListSerializer`（列表轻量）、`ArticleDetailSerializer`（详情带评论）、
  `ArticleWriteSerializer`（写入校验），由 `get_serializer_class()` 按 `self.action` 分发。
- **统一响应契约**：单个资源 `{"article": {...}}`，列表 `{"articles": [...], "articlesCount": n}`。
- **N+1 防治**：`select_related('author')` + `prefetch_related('tags', 'favorited_by')`。

## 验收

```bash
python demos/verify_week2.py     # 10 条验收标准自动跑
``` {data-source-line="1274"}
````
