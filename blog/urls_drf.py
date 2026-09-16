from django.urls import path
from . import views_drf

app_name = "blog-api"

urlpatterns = [
    # 健康检查
    path("health/", views_drf.HealthCheckView.as_view(), name="health"),

    # 文章
    path("articles/", views_drf.ArticleListView.as_view(), name="article-list"),
    path("articles/<slug:slug>/", views_drf.ArticleDetailView.as_view(), name="article-detail"),
    path("articles/<slug:slug>/comments/", views_drf.ArticleCommentsView.as_view(), name="article-comments"),

    # 标签
    path("tags/", views_drf.TagListView.as_view(), name="tag-list"),
]