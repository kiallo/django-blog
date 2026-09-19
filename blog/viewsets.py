"""
ModelViewSet 版本 —— 本课终极形态

一个类 = 6 个标准接口 + N 个自定义接口
配合 Router 自动生成路由，不用再写 urls。
"""


from django.db.models import Count
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Article, Tag
from .pagination import ArticlePagination
from .permissions import IsAuthorOrAdminOrReadOnly
from .serializers import (
    ArticleDetailSerializer,
    ArticleListSerializer,
    ArticleWriteSerializer,
    CommentSerializer,
    CommentWriteSerializer,
    TagSerializer,
)


class ArticleViewSet(viewsets.ModelViewSet):
    """
    文章 ViewSet

    类比 FastAPI：相当于把 router + 所有 handler 合并到一个类里

    ModelViewSet = GenericViewSet + 全部 5 个 Mixin
    """
    # 基础查询集（Router 靠它推断 basename，所以这里必须写）
    queryset = Article.objects.all()

    # URL 用 slug：/api/v3/articles/django-basics/
    lookup_field = 'slug'

    pagination_class = ArticlePagination
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrAdminOrReadOnly]

    # 搜索 + 排序（filter_backends 在 settings 里全局配了）
    search_fields = ['title', 'description', 'body', 'author__username']
    ordering_fields = ['created_at', 'updated_at', 'title']
    ordering = ['-created_at']

    # ---------- 三个钩子 ----------

    def get_queryset(self):
        """按需过滤 + 预加载关联对象"""
        queryset = Article.objects.select_related('author').prefetch_related('tags')

        tag = self.request.query_params.get('tag') # type: ignore
        author = self.request.query_params.get('author') # type: ignore
        if tag:
            queryset = queryset.filter(tags__name=tag)
        if author:
            queryset = queryset.filter(author__username=author)
        return queryset

    def get_serializer_class(self):
        """
        按动作选序列化器 —— 这是 ModelViewSet 最关键的钩子

        action 的值就是动作名：list / create / retrieve / update / partial_update / destroy
        """
        if self.action in ('create', 'update', 'partial_update'):
            return ArticleWriteSerializer
        if self.action == 'retrieve':
            return ArticleDetailSerializer
        return ArticleListSerializer

    def perform_create(self, serializer):
        """创建时自动补上作者"""
        serializer.save(author=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        创建后返回详情表示

        默认实现会回显 ArticleWriteSerializer 的那几个字段（title/description/body/tag_list），
        连 id、slug 都没有，客户端拿不到刚创建的资源。
        所以写入用写序列化器，响应换回读序列化器。
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        article = ArticleDetailSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        headers = self.get_success_headers(article.data)
        return Response(article.data, status=status.HTTP_201_CREATED, headers=headers)

    # ---------- 自定义动作 ----------

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, slug=None):
        """
        嵌套资源：/api/v3/articles/<slug>/comments/

        detail=True 时，URL 里的参数名由 lookup_field 决定，所以形参是 slug
        """
        article = self.get_object()

        if request.method == 'GET':
            comments = article.comments.select_related('author')
            serializer = CommentSerializer(comments, many=True)
            return Response({
                'comments': serializer.data,
                'commentsCount': comments.count(),
            })

        # POST：新增评论
        serializer = CommentWriteSerializer(
            data=request.data.get('comment', request.data)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(article=article, author=request.user)

        return Response(
            {'comment': CommentSerializer(serializer.instance).data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        集合级动作：/api/v3/articles/stats/

        不需要具体文章，所以 detail=False
        """
        data = Article.objects.aggregate(
            # ⚠️ 必须 distinct=True：多个聚合会 JOIN，导致行数翻倍被重复计数
            totalArticles=Count('id', distinct=True),
            totalComments=Count('comments', distinct=True),
        )
        return Response({
            **data,
            'totalTags': Tag.objects.count(),
            'totalAuthors': Article.objects.values('author').distinct().count(),
        })


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    标签 ViewSet —— 只读版本

    ReadOnlyModelViewSet = GenericViewSet + ListModelMixin + RetrieveModelMixin
    只提供 list 和 retrieve，没有写操作（标签由文章写入时自动创建）
    """
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    lookup_field = 'name'           # /api/v3/tags/Django/
    pagination_class = None         # 标签总量少，不分页