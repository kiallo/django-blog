"""
DRF vs 原生 Django 视图对比演示
"""


def show_comparison():
    print("╔" + "═" * 62 + "╗")
    print("║" + " 原生 Django vs DRF 对比".center(54) + "║")
    print("╚" + "═" * 62 + "╝")

    print("""
1. 序列化对比：

   原生 Django（手动转字典）:
   ┌──────────────────────────────────────────────────┐
   │ def _article_to_dict(article):                   │
   │     return {                                     │
   │         "id": article.id,                        │
   │         "slug": article.slug,                    │
   │         "title": article.title,                  │
   │         # ... 每个字段手写                        │
   │     }                                            │
   └──────────────────────────────────────────────────┘

   DRF（声明式序列化器）:
   ┌──────────────────────────────────────────────────┐
   │ class ArticleSerializer(serializers.ModelSerializer): │
   │     class Meta:                                  │
   │         model = Article                          │
   │         fields = ['id', 'slug', 'title', ...]   │
   │                                                  │
   │ # 使用：serializer.data 自动生成 JSON            │
   └──────────────────────────────────────────────────┘

2. 视图对比：

   原生 Django:
   ┌──────────────────────────────────────────────────┐
   │ def article_list(request):                       │
   │     if request.method == "GET":                  │
   │         ...                                      │
   │     elif request.method == "POST":               │
   │         ...                                      │
   └──────────────────────────────────────────────────┘

   DRF:
   ┌──────────────────────────────────────────────────┐
   │ class ArticleListView(APIView):                  │
   │     def get(self, request):                      │
   │         ...                                      │
   │     def post(self, request):                     │
   │         ...                                      │
   └──────────────────────────────────────────────────┘

3. 数据验证对比：

   原生 Django（手动验证）:
   ┌──────────────────────────────────────────────────┐
   │ title = request.POST.get('title')                │
   │ if not title:                                    │
   │     return JsonResponse({"error": "..."}, 400)   │
   │ if len(title) > 255:                             │
   │     return JsonResponse({"error": "..."}, 400)   │
   └──────────────────────────────────────────────────┘

   DRF（自动验证）:
   ┌──────────────────────────────────────────────────┐
   │ serializer = ArticleSerializer(data=request.data)│
   │ if not serializer.is_valid():                    │
   │     return Response(serializer.errors, 400)      │
   │ # 自动验证字段类型、长度、必填等                   │
   └──────────────────────────────────────────────────┘

4. 响应对比：

   原生 Django:
   ┌──────────────────────────────────────────────────┐
   │ from django.http import JsonResponse             │
   │ return JsonResponse({"data": ...})               │
   └──────────────────────────────────────────────────┘

   DRF:
   ┌──────────────────────────────────────────────────┐
   │ from rest_framework.response import Response     │
   │ return Response({"data": ...})                   │
   │ # 自动支持 JSON、HTML、XML 等格式                  │
   └──────────────────────────────────────────────────┘
    """)


def show_url_comparison():
    print("\n╔" + "═" * 62 + "╗")
    print("║" + " URL 路由对比".center(54) + "║")
    print("╚" + "═" * 62 + "╝")

    print("""
原生 Django:
  path("articles/", views.article_list)

DRF:
  path("articles/", views.ArticleListView.as_view())
  # 类视图需要用 .as_view() 转换为视图函数

两套路由并存：
  /api/blog/articles/     → 原生视图（手动序列化）
  /api/v2/articles/       → DRF 视图（自动序列化）
    """)


def show_drf_features():
    print("\n╔" + "═" * 62 + "╗")
    print("║" + " DRF 特色功能".center(54) + "║")
    print("╚" + "═" * 62 + "╝")

    print("""
1. 可浏览的 API（Browsable API）:
   - 浏览器直接访问 API 地址，自动渲染 HTML 界面
   - 可以在页面上直接发送请求
   - 访问: http://127.0.0.1:8000/api/v2/articles/

2. 自动文档:
   - DRF 自动生成 API 文档
   - 配合 drf-spectacular 可生成 Swagger 文档

3. 认证和权限:
   - 内置多种认证方式（Session、Token、JWT）
   - 灵活的权限控制（AllowAny、IsAuthenticated 等）

4. 分页:
   - 内置分页类
   - 自动处理分页参数

5. 限流:
   - 内置请求限流
   - 防止 API 被滥用
    """)


if __name__ == "__main__":
    show_comparison()
    show_url_comparison()
    show_drf_features()

    print("\n✅ 启动服务器: python manage.py runserver")
    print("✅ 原生接口: http://127.0.0.1:8000/api/blog/articles/")
    print("✅ DRF 接口: http://127.0.0.1:8000/api/v2/articles/")
    print("✅ 浏览器登录: http://127.0.0.1:8000/api-auth/login/")
