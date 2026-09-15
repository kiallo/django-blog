from django.shortcuts import render
from django.http import JsonResponse
from django.http import HttpResponse
from .models import Article, Comment, Tag
import json


def hello(request):
    """最简单的视图 — 返回纯文本"""
    return HttpResponse("Hello, Django! 你好世界！")


def health_check(request):
    """健康检查接口"""
    return JsonResponse({
        "status": "ok",
        "framework": "Django",
        "version": "2.0",
        "db": "connected",
    })


def _article_to_dict(article):
    """将 Article 对象转为字典（类似 FastAPI 的 Schema 序列化）"""
    return {
        "id": article.id,
        "slug": article.slug,
        "title": article.title,
        "description": article.description,
        "body": article.body,
        "tagList": list(article.tags.values_list('name', flat=True)),
        "createdAt": article.created_at.isoformat(),
        "updatedAt": article.updated_at.isoformat(),
        "author": {
            "username": article.author.username,
            "bio": getattr(article.author, 'bio', ''),
        },
        "favoritesCount": 0,
    }


def article_list(request):
    """
    文章列表（从数据库查询）

    支持查询参数：
    - skip: 跳过数量
    - limit: 返回数量
    - tag: 标签过滤
    - author: 作者过滤
    """
    skip = int(request.GET.get("skip", 0))
    limit = int(request.GET.get("limit", 20))
    tag = request.GET.get("tag")
    author = request.GET.get("author")

    # 构建查询集（QuerySet）
    # 类比 FastAPI: db.query(Article).filter(...)
    queryset = Article.objects.all()

    if tag:
        queryset = queryset.filter(tags__name=tag)
    if author:
        queryset = queryset.filter(author__username=author)

    # 计算总数（在分页前）
    total = queryset.count()

    # 分页
    queryset = queryset[skip:skip + limit]

    # 序列化
    articles = [_article_to_dict(a) for a in queryset]

    return JsonResponse({
        "articles": articles,
        "articlesCount": total,
    })


def article_detail(request, article_id):
    """
    文章详情（从数据库查询）
    """
    try:
        article = Article.objects.select_related('author').get(id=article_id)
    except Article.DoesNotExist:
        return JsonResponse(
            {"error": "文章不存在"},
            status=404
        )

    return JsonResponse({
        "article": _article_to_dict(article),
    })


def article_comments(request, article_id):
    """
    文章评论列表
    """
    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        return JsonResponse(
            {"error": "文章不存在"},
            status=404
        )

    comments = Comment.objects.filter(article=article).select_related('author')

    comment_list = [
        {
            "id": c.id, # type: ignore
            "body": c.body,
            "createdAt": c.created_at.isoformat(),
            "author": {
                "username": c.author.username,
            },
        }
        for c in comments
    ]

    return JsonResponse({
        "comments": comment_list,
        "commentsCount": len(comment_list),
    })


def tag_list(request):
    """标签列表"""
    tags = Tag.objects.all()
    tag_names = list(tags.values_list('name', flat=True))
    return JsonResponse({"tags": tag_names})