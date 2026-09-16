from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # 原始视图（保留作对比）
    path('api/blog/', include('blog.urls')),

    # DRF 视图（新）
    path('api/v2/', include('blog.urls_drf')),

    # DRF 登录页面（浏览器可浏览的 API）
    path('api-auth/', include('rest_framework.urls')),
]