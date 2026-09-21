from rest_framework import serializers
from rest_framework.validators import UniqueValidator
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


class ArticleFavoriteMixin(serializers.Serializer):
    """
    收藏相关的只读字段 —— 列表序列化器和详情序列化器共用

    DRF 的元类会沿着 MRO 收集所有基类里的 _declared_fields，
    所以在 Mixin 的类体里声明字段，子类自动就拥有它。
    （注意：这是个"抽象"的 Mixin，不会被实例化，所以不需要 Meta）
    """
    favorites_count = serializers.SerializerMethodField()
    favorited = serializers.SerializerMethodField()

    def get_favorites_count(self, obj):
        """
        收藏总数

        ⚠️ 用 len(obj.favorited_by.all()) 而不是 obj.favorited_by.count()：
        view 的 get_queryset() 里加了 prefetch_related('favorited_by')，
        .all() 直接命中预取缓存，len() 是内存操作，0 次查询；
        .count() 在预取场景下虽然也走缓存，但换成 filter().exists() 就必然查库了。
        """
        return len(obj.favorited_by.all())

    def get_favorited(self, obj):
        """
        当前登录用户是否收藏了这一篇

        这里在 Python 里遍历判断，而不是
        `obj.favorited_by.filter(pk=request.user.pk).exists()` ——
        后者会无视预取缓存，每篇文章多一次查询（页面上 5 篇就是 5 次）。
        """
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return any(user.pk == request.user.pk for user in obj.favorited_by.all())


class ArticleListSerializer(ArticleFavoriteMixin, serializers.ModelSerializer):
    """
    文章列表序列化器（轻量版，不含正文）

    类比 FastAPI:
    class ArticleForResponse(BaseModel):
        slug: str
        title: str
        description: str
        # 不含 body

    ⚠️ Mixin 必须写在 ModelSerializer 前面：DRF 的元类按 MRO 收集字段，
       Meta.fields 里的 'favorites_count' / 'favorited' 只有从 Mixin 拿到声明，
       才不会被当成"模型上不存在的字段"而报 ImproperlyConfigured。
    """
    author = AuthorSerializer(read_only=True)
    tag_list = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'id', 'slug', 'title', 'description',
            'tag_list', 'created_at', 'updated_at',
            'author', 'favorites_count', 'favorited',
        ]

    def get_tag_list(self, obj):
        """
        获取标签列表

        类似 FastAPI 中的 @validator 或自定义属性
        """
        return list(obj.tags.values_list('name', flat=True))


class ArticleDetailSerializer(ArticleFavoriteMixin, serializers.ModelSerializer):
    """
    文章详情序列化器（包含正文和评论）

    类比 FastAPI:
    class ArticleInResponse(BaseModel):
        article: ArticleForResponse
    """
    author = AuthorSerializer(read_only=True)
    tag_list = serializers.SerializerMethodField()
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Article
        fields = [
            'id', 'slug', 'title', 'description', 'body',
            'tag_list', 'created_at', 'updated_at',
            'author', 'comments', 'favorites_count', 'favorited',
        ]

    def get_tag_list(self, obj):
        return list(obj.tags.values_list('name', flat=True))



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


# ==================== 认证相关（第11课）====================

class RegisterSerializer(serializers.ModelSerializer):
    """注册序列化器"""
    # ⚠️ 显式声明 username 是为了替换掉 ModelSerializer 自动加的 UniqueValidator
    # 自动加的那个报错信息是英文的（"This field must be unique."），这里换成中文
    username = serializers.CharField(
        max_length=150,
        validators=[UniqueValidator(
            queryset=User.objects.all(),
            message='该用户名已被注册',
        )],
    )
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        style={'input_type': 'password'},
        error_messages={'min_length': '密码至少需要6位'},
    )
    password2 = serializers.CharField(
        write_only=True,
        label='确认密码',
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'password2']
        read_only_fields = ['id']

    def validate(self, attrs):
        """
        跨字段校验：写在 validate 里（不是 validate_xxx）

        调用顺序：字段级校验 → 字段级 validate_xxx → 对象级 validate
        """
        if attrs['password'] != attrs.pop('password2'):
            # 抛 ValidationError 时指定字段名，前端好定位
            raise serializers.ValidationError({'password2': '两次输入的密码不一致'})
        return attrs

    def create(self, validated_data):
        # ⚠️ 必须用 create_user，它负责密码哈希
        # 用 User.objects.create 会把密码明文存进数据库
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    """登录序列化器（只做校验，不涉及模型保存）"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        from django.contrib.auth import authenticate

        user = authenticate(
            request=self.context.get('request'),
            username=attrs['username'],
            password=attrs['password'],
        )

        # ⚠️ 不要区分"用户不存在"和"密码错误" —— 防止攻击者枚举用户名
        if user is None:
            raise serializers.ValidationError('用户名或密码错误')

        if not user.is_active:
            raise serializers.ValidationError('该账号已被禁用')

        attrs['user'] = user
        return attrs


class RefreshSerializer(serializers.Serializer):
    """刷新 Token 序列化器"""
    refresh = serializers.CharField()


class EmptySerializer(serializers.Serializer):
    """占位序列化器：给没有请求体的接口用（让可浏览 API 正常渲染）"""
    pass