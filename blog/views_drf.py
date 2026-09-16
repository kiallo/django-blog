from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Article, Tag, Comment
from .serializers import (
    ArticleListSerializer,
    ArticleDetailSerializer,
    ArticleCreateSerializer,
    CommentSerializer,
    TagSerializer,
)


class ArticleListView(APIView):
    """
    文章列表视图

    类比 FastAPI:
    @router.get("/articles")
    async def list_articles(...):
        ...

    @router.post("/articles")
    async def create_article(...):
        ...
    """

    def get(self, request):
        """
        获取文章列表

        DRF 的 request 对象：
        - request.query_params  → 查询参数（类似 FastAPI 的 Query）
        - request.data          → 请求体（类似 FastAPI 的 Body）
        - request.user          → 当前用户
        """
        queryset = Article.objects.all().select_related('author')

        # 过滤（类似 FastAPI 的 Query 参数）
        tag = request.query_params.get('tag')
        author = request.query_params.get('author')

        if tag:
            queryset = queryset.filter(tags__name=tag)
        if author:
            queryset = queryset.filter(author__username=author)

        # 序列化
        serializer = ArticleListSerializer(queryset, many=True)

        return Response({
            "articles": serializer.data,
            "articlesCount": queryset.count(),
        })

    def post(self, request):
        """
        创建文章

        DRF 的 request.data 已经是解析好的字典/JSON
        """
        serializer = ArticleCreateSerializer(
            data=request.data.get('article', request.data),
            context={'request': request},
        )

        # 验证数据（类似 FastAPI 的 Pydantic 自动验证）
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 保存（调用 serializer 的 create 方法）
        article = serializer.save()

        # 返回创建的文章（使用详情序列化器）
        response_serializer = ArticleDetailSerializer(article)
        return Response(
            {"article": response_serializer.data},
            status=status.HTTP_201_CREATED,
        )


class ArticleDetailView(APIView):
    """
    文章详情视图

    类比 FastAPI:
    @router.get("/articles/{slug}")
    async def get_article(slug: str):
        ...
    """

    def get(self, request, slug):
        """获取文章详情"""
        article = get_object_or_404(Article, slug=slug)
        serializer = ArticleDetailSerializer(article)
        return Response({"article": serializer.data})

    def put(self, request, slug):
        """
        更新文章

        类比 FastAPI:
        @router.put("/articles/{slug}")
        async def update_article(slug: str, data: ArticleInUpdate):
            ...
        """
        article = get_object_or_404(Article, slug=slug)

        # 权限检查（简化版）
        if article.author != request.user:
            return Response(
                {"error": "只有作者可以修改文章"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 更新字段
        article_data = request.data.get('article', request.data)
        if 'title' in article_data:
            article.title = article_data['title']
        if 'description' in article_data:
            article.description = article_data['description']
        if 'body' in article_data:
            article.body = article_data['body']

        article.save()

        serializer = ArticleDetailSerializer(article)
        return Response({"article": serializer.data})

    def delete(self, request, slug):
        """删除文章"""
        article = get_object_or_404(Article, slug=slug)

        if article.author != request.user:
            return Response(
                {"error": "只有作者可以删除文章"},
                status=status.HTTP_403_FORBIDDEN,
            )

        article.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArticleCommentsView(APIView):
    """
    文章评论视图

    类比 FastAPI:
    @router.get("/articles/{slug}/comments")
    async def list_comments(slug: str):
        ...
    """

    def get(self, request, slug):
        """获取文章评论"""
        article = get_object_or_404(Article, slug=slug)
        comments = article.comments.all().select_related('author') # type: ignore
        serializer = CommentSerializer(comments, many=True)
        return Response({
            "comments": serializer.data,
            "commentsCount": comments.count(),
        })

    def post(self, request, slug):
        """添加评论"""
        article = get_object_or_404(Article, slug=slug)

        body = request.data.get('comment', request.data).get('body')
        if not body:
            return Response(
                {"error": "评论内容不能为空"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = Comment.objects.create(
            body=body,
            article=article,
            author=request.user,
        )

        serializer = CommentSerializer(comment)
        return Response(
            {"comment": serializer.data},
            status=status.HTTP_201_CREATED,
        )


class TagListView(APIView):
    """标签列表视图"""

    def get(self, request):
        tags = Tag.objects.all()
        serializer = TagSerializer(tags, many=True)
        return Response({"tags": serializer.data})


class HealthCheckView(APIView):
    """健康检查"""
    permission_classes = []  # 不需要认证

    def get(self, request):
        return Response({
            "status": "ok",
            "framework": "Django + DRF",
            "version": "1.0",
        })