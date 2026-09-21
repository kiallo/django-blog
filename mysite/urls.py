from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

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

    # ===== API 文档 =====
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]