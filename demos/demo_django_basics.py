"""
Django 基础演示脚本

演示 Django 项目的核心概念
"""

def show_project_structure():
    """展示项目结构"""
    print("╔" + "═" * 58 + "╗")
    print("║" + " Django 项目结构".center(50) + "║")
    print("╚" + "═" * 58 + "╝")

    structure = """
django-blog/                   ← 项目根目录
├── mysite/                    ← 项目配置包
│   ├── __init__.py
│   ├── settings.py            ← 配置文件（核心）
│   ├── urls.py                ← 根路由
│   ├── wsgi.py                ← WSGI 部署入口
│   └── asgi.py                ← ASGI 异步入口
├── blog/                      ← 博客应用
│   ├── __init__.py
│   ├── admin.py               ← Admin 后台配置
│   ├── apps.py                ← 应用配置
│   ├── models.py              ← 数据模型（明天学）
│   ├── views.py               ← 视图函数（今天重点）
│   ├── urls.py                ← 应用路由（今天创建）
│   ├── tests.py               ← 测试
│   └── migrations/            ← 数据库迁移
├── manage.py                  ← 管理命令入口
├── db.sqlite3                 ← SQLite 数据库（自动创建）
└── .venv/                     ← 虚拟环境
"""
    print(structure)


def show_url_mapping():
    """展示 URL 映射关系"""
    print("╔" + "═" * 58 + "╗")
    print("║" + " URL 路由映射".center(50) + "║")
    print("╚" + "═" * 58 + "╝")

    mappings = """
Django URL 映射:
  /api/blog/hello/          → views.hello()
  /api/blog/health/         → views.health_check()
  /api/blog/articles/       → views.article_list()
  /api/blog/articles/<id>/  → views.article_detail()

FastAPI 对比:
  @router.get("/hello")
  def hello(): ...

  Django:
  path("hello/", views.hello, name="hello")
"""
    print(mappings)


def show_fastapi_vs_django():
    """对比 FastAPI 和 Django 的写法"""
    print("╔" + "═" * 58 + "╗")
    print("║" + " FastAPI vs Django 写法对比".center(46) + "║")
    print("╚" + "═" * 58 + "╝")

    comparison = """
1. 路由定义:

   FastAPI:
   @router.get("/articles/{article_id}")
   async def get_article(article_id: int):
       ...

   Django:
   # urls.py
   path("articles/<int:article_id>/", views.article_detail)
   # views.py
   def article_detail(request, article_id):
       ...

2. 查询参数:

   FastAPI:
   @router.get("/articles")
   async def list(skip: int = 0, limit: int = 20):
       ...

   Django:
   def article_list(request):
       skip = int(request.GET.get("skip", 0))
       limit = int(request.GET.get("limit", 20))

3. 返回 JSON:

   FastAPI:
   return {"articles": articles}

   Django:
   from django.http import JsonResponse
   return JsonResponse({"articles": articles})

4. 错误处理:

   FastAPI:
   raise HTTPException(status_code=404, detail="Not found")

   Django:
   from django.http import JsonResponse
   return JsonResponse({"error": "Not found"}, status=404)
"""
    print(comparison)


if __name__ == "__main__":
    show_project_structure()
    show_url_mapping()
    show_fastapi_vs_django()

    print("\n✅ 运行服务器: python manage.py runserver")
    print("✅ 访问接口: http://127.0.0.1:8000/api/blog/hello/")
    print("✅ 管理后台: http://127.0.0.1:8000/admin/")
