"""
ModelViewSet 版本 —— 本课终极形态

一个类 = 6 个标准接口 + N 个自定义接口
配合 Router 自动生成路由，不用再写 urls。
"""

from .responses import envelope
from django.db.models import Count
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import filters, serializers, status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response

from .models import Article, Tag, Comment
from .pagination import ArticlePagination
from .permissions import IsAuthorOrAdminOrReadOnly, IsCommentAuthorOrReadOnly
from .serializers import (
    ArticleDetailSerializer,
    ArticleListSerializer,
    ArticleWriteSerializer,
    CommentSerializer,
    CommentWriteSerializer,
    TagSerializer,
)


# ---------- 文档专用的"响应外壳" ----------
# 自定义动作返回的不是裸对象，而是 {"article": {...}} / {"comments": [...]} 这种包一层的结构。
# 直接写 responses={200: ArticleListSerializer} 的话，文档里会少掉最外面那层，
# inline_serializer 就是用来把外壳一起描述出来的。
# 只在 schema 生成时用得到，不影响任何运行时逻辑。

ArticleEnvelope = inline_serializer(
    'ArticleEnvelope',
    {'article': ArticleListSerializer()},
)

StatsResponse = inline_serializer(
    'StatsResponse',
    {
        'totalArticles': serializers.IntegerField(),
        'totalComments': serializers.IntegerField(),
        'totalTags': serializers.IntegerField(),
        'totalAuthors': serializers.IntegerField(),
    },
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
        queryset = Article.objects.select_related('author').prefetch_related('tags', 'favorited_by')

        # 支持 ?favorited=<username> —— 查某人收藏过的文章
        favorited_by = self.request.query_params.get('favorited') # type: ignore
        if favorited_by:
            queryset = queryset.filter(favorited_by__username=favorited_by)

        tag = self.request.query_params.get('tag') # type: ignore
        author = self.request.query_params.get('author') # type: ignore
        if tag:
            queryset = queryset.filter(tags__name=tag)
        if author:
            queryset = queryset.filter(author__username=author)
        return queryset

    def get_permissions(self):
        """
        三种动作三套规则：

        - favorite  : 收藏别人的文章 → 只要登录，不要文章作者身份
        - comments  : 对文章只做读取，不修改文章 → 只要登录（不满足的话会被
                      get_object() 里的对象级权限误判成 403）
        - feed      : 只看自己的关注流 → 只要登录
        - 其余      : 走类级配置（IsAuthenticatedOrReadOnly + IsAuthorOrAdminOrReadOnly）
        """
        if self.action in ('favorite', 'feed', 'comments'):
            return [IsAuthenticated()]
        return super().get_permissions()

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
        POST —— 用写序列化器入库，用详情序列化器回显

        默认的 CreateModelMixin 会回显 ArticleWriteSerializer 的那几个字段
        （title/description/body/tag_list），连 id、slug 都没有，
        客户端拿不到刚创建的资源，所以这里覆写。
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        detail = ArticleDetailSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        return envelope('article', detail.data, status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        """
        GET /articles/<slug>/

        这个写法值得记：父类逻辑一行不改，只把它的返回值重新包一层。
        比抄一遍 RetrieveModelMixin 的源码干净得多。
        """
        response = super().retrieve(request, *args, **kwargs)
        return envelope('article', response.data)

    def update(self, request, *args, **kwargs):
        """
        PUT / PATCH 共用这一个方法

        因为 UpdateModelMixin.partial_update() 内部就是
        `kwargs['partial'] = True; return self.update(...)`，
        所以覆写 update 等于同时覆盖了 PUT 和 PATCH。
        """
        response = super().update(request, *args, **kwargs)
        return envelope('article', response.data)

    # ---------- 自定义动作 ----------

    # ⚠️ 一个 @action 接两种方法时，@extend_schema 要写两遍，
    #    再用 methods=[...] 指明各自描述的是哪个方法（没有 methods 的话两遍会互相覆盖）
    @extend_schema(
        methods=['GET'],
        summary='文章评论列表',
        description='GET /api/v3/articles/<slug>/comments/ 返回该文章的全部评论及总数。',
        request=None,
        responses={200: inline_serializer(
            'CommentListResponse',
            {
                'comments': CommentSerializer(many=True),
                'commentsCount': serializers.IntegerField(),
            },
        )},
    )
    @extend_schema(
        methods=['POST'],
        summary='发表评论',
        description=(
            'POST /api/v3/articles/<slug>/comments/ 给这篇文章新增一条评论。\n\n'
            '请求体两种写法都支持：{"comment": {"body": "..."}} 或 {"body": "..."}。'
        ),
        request=inline_serializer(
            'CommentCreateBody',
            {'comment': CommentWriteSerializer()},
        ),
        responses={201: inline_serializer(
            'CommentCreateResponse',
            {'comment': CommentSerializer()},
        )},
    )
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

    @extend_schema(
        summary='站点统计',
        description='GET /api/v3/articles/stats/ 返回文章 / 评论 / 标签 / 作者的总数。',
        request=None,
        responses={200: StatsResponse},
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

    @extend_schema(
        methods=['POST'],
        summary='收藏文章',
        description='POST /api/v3/articles/<slug>/favorite/ 收藏这篇文章（幂等，重复收藏不报错）。',
        request=None,
        responses={200: ArticleEnvelope},
    )
    @extend_schema(
        methods=['DELETE'],
        summary='取消收藏文章',
        description='DELETE /api/v3/articles/<slug>/favorite/ 取消收藏（没收藏过也不报错）。',
        request=None,
        responses={200: ArticleEnvelope},
    )
    @action(detail=True, methods=['post', 'delete'], url_path='favorite')
    def favorite(self, request, slug=None):
        """
        POST   /api/v3/articles/<slug>/favorite/   收藏
        DELETE /api/v3/articles/<slug>/favorite/   取消收藏

        一个 @action 接两种方法，用 request.method 分流 ——
        这和 comments() 的写法一样。
        """
        article = self.get_object()

        if request.method == 'POST':
            article.favorited_by.add(request.user)      # 幂等：重复收藏不报错
        else:
            article.favorited_by.remove(request.user)   # 没收藏过也不报错

        # ⚠️ 关键一步：见下面的说明
        article.refresh_from_db()

        serializer = self.get_serializer(article)
        return envelope('article', serializer.data)


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


class CommentViewSet(mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     viewsets.GenericViewSet):
    """
    评论 ViewSet —— 只有"详情 / 改 / 删"，没有 list 和 create

    第10课学的 Mixin 组合在这里派上用场：
    评论的"列表 + 创建"挂在文章下面（/articles/<slug>/comments/），
    顶层资源只需要三个动作，用 mixins 精确拼装，比 ModelViewSet 更贴切。

    对比一下三个选择：
      ModelViewSet         → 6 个动作全给，list/create 是多余的
      ReadOnlyModelViewSet → 少了改和删
      Mixin 手工组合       → 刚刚好 ✅
    """
    queryset = Comment.objects.select_related('author', 'article')
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsCommentAuthorOrReadOnly]

    def get_serializer_class(self):
        """改评论用只含 body 的写序列化器"""
        if self.action in ('update', 'partial_update'):
            return CommentWriteSerializer
        return CommentSerializer

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return envelope('comment', response.data)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return envelope('comment', response.data)