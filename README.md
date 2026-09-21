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

# 3. 启动 Redis（本机 6379） {#3-启动-redis本机-6379  data-source-line="1206"}

# 4. 建表 {#4-建表  data-source-line="1208"}
python manage.py migrate

# 5. 创建管理员 {#5-创建管理员  data-source-line="1211"}
python manage.py createsuperuser

# 6. 启动 {#6-启动  data-source-line="1214"}
python manage.py runserver
``` {data-source-line="1216"}

访问：
- API 文档：http://127.0.0.1:8000/api/docs/
- 管理后台：http://127.0.0.1:8000/admin/
- API 根目录：http://127.0.0.1:8000/api/v3/

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
curl -X POST http://127.0.0.1:8000/api/v3/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"yourname","password":"yourpass"}'

# 2. 后续请求带上 access token {#2-后续请求带上-access-token  data-source-line="1256"}
curl http://127.0.0.1:8000/api/v3/auth/me/ \
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
