from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import viewsets, views_auth

# ===== Router：一行注册 = 6 条路由 =====
router = DefaultRouter()
router.register('articles', viewsets.ArticleViewSet, basename='article')
router.register('tags', viewsets.TagViewSet, basename='tag')
router.register('auth', views_auth.AuthViewSet, basename='auth') 
router.register('comments', viewsets.CommentViewSet, basename='comment') 

urlpatterns = [
    path('', include(router.urls)),   # ← 自动生成的全部路由
]