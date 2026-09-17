"""
第10课演示：三层视图演进 + Router 自动路由表
运行：python demo_drf_viewsets.py
"""
import os
import sys
import django

# 把项目根目录加入模块搜索路径，保证在 demos/ 下也能 import mysite / blog
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.test.utils import setup_test_environment       # noqa: E402
from rest_framework.routers import DefaultRouter           # noqa: E402
from rest_framework.test import APIClient                  # noqa: E402

from blog import viewsets                                  # noqa: E402

# 脱离测试用例单独使用 API 测试客户端时，需要手动初始化测试环境
# （否则测试客户端用的 testserver 主机名会被 ALLOWED_HOSTS 拦下）
setup_test_environment()


def show_evolution():
    print("╔" + "═" * 66 + "╗")
    print("║" + " 三层视图演进".center(60) + "║")
    print("╚" + "═" * 66 + "╝")
    print("""
① APIView（第9课）—— 全部手写
   class ArticleListView(APIView):
       def get(self, request):    ← 过滤/分页/序列化/响应格式全自己写
       def post(self, request):   ← 校验/保存/状态码全自己写

② GenericAPIView + Mixins（本课）—— 组装积木
   class ArticleListCreateView(mixins.ListModelMixin,
                               mixins.CreateModelMixin,
                               generics.GenericAPIView):
       pagination_class = ArticlePagination   ← 分页：一行
       search_fields = [...]                  ← 搜索：一行
       def get(self, request, *a, **kw):
           return self.list(request, *a, **kw)   ← 胶水

③ ModelViewSet + Router（本课）—— 全自动
   class ArticleViewSet(viewsets.ModelViewSet):
       queryset = Article.objects.all()
       lookup_field = 'slug'

   router.register('articles', ArticleViewSet, basename='article')
   → 自动生成 6 条标准路由，代码量再减一半
""")


def show_router_urls():
    print("╔" + "═" * 66 + "╗")
    print("║" + " Router 自动生成的路由表".center(58) + "║")
    print("╚" + "═" * 66 + "╝")

    router = DefaultRouter()
    router.register("articles", viewsets.ArticleViewSet, basename="article")
    router.register("tags", viewsets.TagViewSet, basename="tag")

    for url in router.urls:
        pattern = str(url.pattern)
        name = url.name
        if "api-root" in name:
            continue
        print(f"  /api/v3/{pattern:<32} {name}")
    print()


def smoke_test():
    """只读冒烟测试：确认接口都能正常返回"""
    print("╔" + "═" * 66 + "╗")
    print("║" + " 接口冒烟测试（只读，不写库）".center(54) + "║")
    print("╚" + "═" * 66 + "╝")

    client = APIClient()
    checks = [
        ("GET", "/api/v3/", None),
        ("GET", "/api/v3/articles/", None),
        ("GET", "/api/v3/articles/?limit=3", None),
        ("GET", "/api/v3/articles/?search=Redis", None),
        ("GET", "/api/v3/articles/?ordering=title", None),
        ("GET", "/api/v3/articles/stats/", None),
        ("GET", "/api/v3/tags/", None),
        ("GET", "/api/v3/generic/articles/", None),
    ]

    for method, url, payload in checks:
        response = client.get(url)
        body = response.json() if response.content else {} # type: ignore
        if isinstance(body, dict) and "articlesCount" in body:
            detail = f"articlesCount={body['articlesCount']} 本页 {len(body.get('articles', []))} 条"
        elif isinstance(body, dict) and "results" in body:
            detail = f"count={body['count']}"
        elif isinstance(body, dict):
            detail = ", ".join(list(body)[:4])
        elif isinstance(body, list):
            detail = f"{len(body)} 项"
        else:
            detail = ""

        flag = "✅" if response.status_code < 400 else "❌" # type: ignore
        print(f"  {flag} {response.status_code}  {method} {url:<42} {detail}") # type: ignore
    print()


def show_mixins_cheatsheet():
    print("╔" + "═" * 66 + "╗")
    print("║" + " Mixin / ViewSet 速查".center(56) + "║")
    print("╚" + "═" * 66 + "╝")
    print("""
Mixins（积木）
  ListModelMixin        list()
  CreateModelMixin      create()
  RetrieveModelMixin    retrieve()
  UpdateModelMixin      update() / partial_update()
  DestroyModelMixin     destroy()

预置组合（DRF 已帮你组装好）
  generics.ListAPIView                  GET 列表
  generics.CreateAPIView                POST 创建
  generics.ListCreateAPIView            GET + POST
  generics.RetrieveAPIView              GET 详情
  generics.RetrieveUpdateDestroyAPIView GET + PUT + PATCH + DELETE

ViewSet 家族
  ViewSet               只有动作，没有 HTTP 方法 → 必须配 Router
  GenericViewSet        ViewSet + GenericAPIView
  ReadOnlyModelViewSet  list + retrieve
  ModelViewSet          全套 6 个动作
""")


if __name__ == "__main__":
    show_evolution()
    show_router_urls()
    smoke_test()
    show_mixins_cheatsheet()

    print("✅ 启动服务器: python manage.py runserver")
    print("✅ ViewSet 版: http://127.0.0.1:8000/api/v3/articles/")
    print("✅ Mixin 版  : http://127.0.0.1:8000/api/v3/generic/articles/")
    print("✅ API 首页  : http://127.0.0.1:8000/api/v3/")