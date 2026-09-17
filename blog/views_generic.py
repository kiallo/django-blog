"""
GenericAPIView + Mixins 版本（对比用）

和第9课的 APIView 版本功能相同，但省掉了所有重复代码：
- 分页        → pagination_class 一行
- 过滤/搜索/排序 → filter_backends + search_fields 两行
- 校验失败返回400 → serializer.is_valid(raise_exception=True) 自动处理
- 404         → get_object_or_404 由 get_object() 内置
"""

from rest_framework import generics, mixins, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Article
from .pagination import ArticlePagination
from .permissions import IsAuthorOrReadOnly
from .serializers import (
    ArticleDetailSerializer,
    ArticleListSerializer,
    ArticleWriteSerializer,
    CommentSerializer,
    CommentWriteSerializer,
)


class ArticleMixinBase(generics.GenericAPIView):
    """把两个视图共用的配置抽出来（DRF 项目里很常见的写法）"""
    pagination_class = ArticlePagination
    # filter_backends 不写 → 自动用 settings 里的全局配置（Search + Ordering）
    search_fields = ['title', 'description', 'body', 'author__username']
    ordering_fields = ['created_at', 'updated_at', 'title']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        查询集：一次性写好 select_related / prefetch_related，避免 N+1 查询

        类比 FastAPI：repository 层的 get_articles()
        """
        queryset = Article.objects.select_related('author').prefetch_related('tags')

        # 手写过滤（不装 django-filter 也能用）
        tag = self.request.query_params.get('tag') # type: ignore
        author = self.request.query_params.get('author') # type: ignore
        if tag:
            queryset = queryset.filter(tags__name=tag)
        if author:
            queryset = queryset.filter(author__username=author)
        return queryset


class ArticleListCreateView(mixins.ListModelMixin,
                            mixins.CreateModelMixin,
                            ArticleMixinBase):
    """
    GET  /generic/articles/   → list()
    POST /generic/articles/   → create()
    """
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_serializer_class(self):
        """POST 用写入版，GET 用列表版"""
        if self.request.method == 'POST':
            return ArticleWriteSerializer
        return ArticleListSerializer

    def perform_create(self, serializer):
        """保存前注入作者 —— 只读字段 author 不能由前端传"""
        serializer.save(author=self.request.user)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class ArticleDetailView(mixins.RetrieveModelMixin,
                        mixins.UpdateModelMixin,
                        mixins.DestroyModelMixin,
                        ArticleMixinBase):
    """
    GET/PUT/PATCH/DELETE /generic/articles/<slug>/
    """
    lookup_field = 'slug'          # URL 用 slug 而不是 id
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ArticleWriteSerializer
        return ArticleDetailSerializer

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class ArticleCommentsView(generics.GenericAPIView):
    """
    GET/POST /generic/articles/<slug>/comments/
    """
    queryset = Article.objects.all()
    lookup_field = 'slug'
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, *args, **kwargs):
        article = self.get_object()
        comments = article.comments.select_related('author')
        serializer = CommentSerializer(comments, many=True)
        return Response({
            'comments': serializer.data,
            'commentsCount': comments.count(),
        })

    def post(self, request, *args, **kwargs):
        article = self.get_object()
        serializer = CommentWriteSerializer(
            data=request.data.get('comment', request.data)
        )
        serializer.is_valid(raise_exception=True)   # 校验失败自动返回 400
        serializer.save(article=article, author=request.user)

        # 写入序列化器只有 body 字段，返回时要用展示序列化器重新序列化
        return Response(
            {'comment': CommentSerializer(serializer.instance).data},
            status=status.HTTP_201_CREATED,
        )