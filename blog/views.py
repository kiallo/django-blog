from django.shortcuts import render
from django.http import JsonResponse
from django.http import HttpResponse
import json


def hello(request):
    """最简单的视图 — 返回纯文本"""
    return HttpResponse("Hello, Django! 你好世界！")


def health_check(request):
    """
    健康检查接口

    类比 FastAPI:
    @router.get("/health")
    async def health():
        return {"status": "ok"}
    """
    return JsonResponse({
        "status": "ok",
        "framework": "Django",
        "version": "1.0",
    })


def article_list(request):
    """
    文章列表接口（模拟）

    类比 FastAPI:
    @router.get("/articles")
    async def list_articles(skip: int = 0, limit: int = 20):
        ...
    """
    # 从查询参数获取分页信息（类似 FastAPI 的 Query 参数）
    skip = int(request.GET.get("skip", 0))
    limit = int(request.GET.get("limit", 20))

    # 模拟数据
    articles = [
        {
            "id": 1,
            "title": "Django 入门教程",
            "description": "学习 Django 的基础知识",
            "tagList": ["Python", "Django"],
        },
        {
            "id": 2,
            "title": "Django REST Framework",
            "description": "使用 DRF 构建 API",
            "tagList": ["Python", "DRF", "API"],
        },
    ]

    # 分页处理
    paginated = articles[skip:skip + limit]

    return JsonResponse({
        "articles": paginated,
        "articlesCount": len(paginated),
    })


def article_detail(request, article_id):
    """
    文章详情接口（模拟）

    类比 FastAPI:
    @router.get("/articles/{article_id}")
    async def get_article(article_id: int):
        ...

    注意：Django 的路径参数直接在 URL 中定义，通过函数参数接收
    """
    # 模拟数据库查询
    articles = {
        1: {"id": 1, "title": "Django 入门教程", "body": "Django 是一个强大的框架..."},
        2: {"id": 2, "title": "DRF 教程", "body": "Django REST Framework 可以快速构建 API..."},
    }

    article = articles.get(article_id)
    if not article:
        return JsonResponse(
            {"error": "文章不存在"},
            status=404
        )

    return JsonResponse({"article": article})