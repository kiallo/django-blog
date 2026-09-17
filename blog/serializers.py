from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Article, Tag, Comment


class TagSerializer(serializers.ModelSerializer):
    """
    标签序列化器

    类比 FastAPI:
    class TagSchema(BaseModel):
        id: int
        name: str
    """
    class Meta:
        model = Tag
        fields = ['id', 'name']


class UserSerializer(serializers.ModelSerializer):
    """
    用户序列化器（简化版）

    类比 FastAPI:
    class UserResponse(BaseModel):
        username: str
        email: str
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email']
        read_only_fields = ['id']


class AuthorSerializer(serializers.ModelSerializer):
    """作者序列化器（用于文章中的作者嵌套）"""
    class Meta:
        model = User
        fields = ['username']


class CommentSerializer(serializers.ModelSerializer):
    """
    评论序列化器

    类比 FastAPI:
    class CommentResponse(BaseModel):
        id: int
        body: str
        author: AuthorResponse
        created_at: datetime
    """
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'body', 'author', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ArticleListSerializer(serializers.ModelSerializer):
    """
    文章列表序列化器（轻量版，不含正文）

    类比 FastAPI:
    class ArticleForResponse(BaseModel):
        slug: str
        title: str
        description: str
        # 不含 body
    """
    # 嵌套序列化器
    author = AuthorSerializer(read_only=True)

    # 自定义字段名
    tag_list = serializers.SerializerMethodField()
    favorites_count = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'id', 'slug', 'title', 'description',
            'tag_list', 'created_at', 'updated_at',
            'author', 'favorites_count',
        ]

    def get_tag_list(self, obj):
        """
        获取标签列表

        类似 FastAPI 中的 @validator 或自定义属性
        """
        return list(obj.tags.values_list('name', flat=True))

    def get_favorites_count(self, obj):
        """获取收藏数（暂时返回 0）"""
        return 0


class ArticleDetailSerializer(serializers.ModelSerializer):
    """
    文章详情序列化器（包含正文和评论）

    类比 FastAPI:
    class ArticleInResponse(BaseModel):
        article: ArticleForResponse
    """
    author = AuthorSerializer(read_only=True)
    tag_list = serializers.SerializerMethodField()
    comments = CommentSerializer(many=True, read_only=True)
    favorites_count = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'id', 'slug', 'title', 'description', 'body',
            'tag_list', 'created_at', 'updated_at',
            'author', 'comments', 'favorites_count',
        ]

    def get_tag_list(self, obj):
        return list(obj.tags.values_list('name', flat=True))

    def get_favorites_count(self, obj):
        return 0


class ArticleCreateSerializer(serializers.Serializer):
    """
    文章创建序列化器（用于输入验证）

    类比 FastAPI:
    class ArticleInCreate(BaseModel):
        title: str
        description: str = ""
        body: str
        tag_list: list[str] = []
    """
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, default="", allow_blank=True)
    body = serializers.CharField()
    tag_list = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[],
    )

    def create(self, validated_data):
        """
        创建文章

        类比 FastAPI 中 Repository 的 create_article 方法
        """
        tags_data = validated_data.pop('tag_list', [])
        request = self.context.get('request')

        # 创建文章
        assert request is not None
        article = Article.objects.create(
            author=request.user,
            **validated_data,
        )

        # 处理标签（get_or_create：存在则获取，不存在则创建）
        for tag_name in tags_data:
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            article.tags.add(tag)

        return article

    def validate_title(self, value):
        """验证标题（类似 FastAPI 的 Pydantic validator）"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("标题至少需要3个字符")
        return value.strip()


class ArticleWriteSerializer(serializers.ModelSerializer):
    """
    文章写入序列化器（create / update / partial_update 共用）

    与 ArticleCreateSerializer 的区别：
    - 继承 ModelSerializer，字段自动从模型来
    - 支持 update（ArticleCreateSerializer 只有 create）

    注意 tag_list 是"只写"字段：POST 进来，但不序列化出去
    """
    tag_list = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Article
        fields = ['title', 'description', 'body', 'tag_list']
        extra_kwargs = {
            'description': {'required': False, 'allow_blank': True},
        }

    def validate_title(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("标题至少需要3个字符")
        return value.strip()

    def _sync_tags(self, article, tag_names):
        """同步标签：不存在就新建，最后整体替换（set 会自动处理增删）"""
        tags = []
        for name in tag_names:
            name = name.strip()
            if name:
                tag, _ = Tag.objects.get_or_create(name=name)
                tags.append(tag)
        article.tags.set(tags)

    def create(self, validated_data):
        # author 不在 fields 里，由视图的 perform_create 通过 serializer.save(author=...) 注入
        tag_names = validated_data.pop('tag_list', [])
        article = Article.objects.create(**validated_data)
        self._sync_tags(article, tag_names)
        return article

    def update(self, instance, validated_data):
        # 用 pop(..., None) 而不是 default=[]：
        # PATCH 没传 tag_list 时应该是"不改标签"，而不是"清空标签"
        tag_names = validated_data.pop('tag_list', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tag_names is not None:
            self._sync_tags(instance, tag_names)
        return instance


class CommentWriteSerializer(serializers.ModelSerializer):
    """评论写入序列化器"""

    class Meta:
        model = Comment
        fields = ['body']

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("评论内容不能为空")
        return value
