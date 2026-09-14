from django.urls import path
from . import views

app_name = "blog"

urlpatterns = [
    # path(路径, 视图函数, 名称)
    #
    # 类比 FastAPI:
    # @router.get("/hello")
    # def hello(): ...
    #
    # Django:
    # path("hello/", views.hello, name="hello")

    path("hello/", views.hello, name="hello"),
    path("health/", views.health_check, name="health"),
    path("articles/", views.article_list, name="article-list"),
    path("articles/<int:article_id>/", views.article_detail, name="article-detail"),
]


