from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views_generic, viewsets

# ===== Router：一行注册 = 6 条路由 =====
router = DefaultRouter()
router.register('articles', viewsets.ArticleViewSet, basename='article')
router.register('tags', viewsets.TagViewSet, basename='tag')

# ===== Mixin 版本（对比用，路径加 /generic/ 前缀区分）=====
generic_patterns = [
    path(
        'generic/articles/',
        views_generic.ArticleListCreateView.as_view(),
        name='generic-article-list',
    ),
    path(
        'generic/articles/<slug:slug>/',
        views_generic.ArticleDetailView.as_view(),
        name='generic-article-detail',
    ),
    path(
        'generic/articles/<slug:slug>/comments/',
        views_generic.ArticleCommentsView.as_view(),
        name='generic-article-comments',
    ),
]

urlpatterns = [
    path('', include(generic_patterns)),
    path('', include(router.urls)),   # ← 自动生成的全部路由
]