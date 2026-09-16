from django.urls import path
from . import views

app_name = "blog"

urlpatterns = [
    path("hello/", views.hello, name="hello"),
    path("health/", views.health_check, name="health"),

    # 文章
    path("articles/", views.article_list, name="article-list"),
    path("articles/<int:article_id>/", views.article_detail, name="article-detail"),
    path("articles/<int:article_id>/comments/", views.article_comments, name="article-comments"),

    # 标签
    path("tags/", views.tag_list, name="tag-list"),
]
