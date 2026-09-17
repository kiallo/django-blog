from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # 第7-8课：原生 Django 视图（手写 JsonResponse）
    path('api/blog/', include('blog.urls')),

    # 第9课：DRF APIView（手写序列化调用）
    path('api/v2/', include('blog.urls_drf')),

    # 第10课：DRF Generic + ViewSet + Router（全自动）
    path('api/v3/', include('blog.urls_v3')),

    # DRF 登录页面（浏览器可浏览的 API）
    path('api-auth/', include('rest_framework.urls')),
]