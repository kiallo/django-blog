from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import uuid


class Tag(models.Model):
    """
    标签模型

    类比 FastAPI 中的 Tag 表：
    class Tag(Base):
        __tablename__ = "tags"
        id = Column(Integer, primary_key=True)
        name = Column(String, unique=True)
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="标签名称",
    )

    class Meta:
        # 数据库表名（不指定则自动生成 blog_tag）
        db_table = "tags"
        # 排序方式
        ordering = ["name"]
        # Admin 后台显示名称
        verbose_name = "标签"
        verbose_name_plural = "标签"

    def __str__(self):
        return self.name


class Article(models.Model):
    """
    文章模型

    类比 FastAPI 中的 Article 表：
    class Article(Base):
        __tablename__ = "articles"
        slug = Column(String, unique=True)
        title = Column(String)
        ...
    """

    # SlugField: URL 友好的唯一标识（如 "django-basics"）
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name="URL 标识",
        help_text="用于 URL 的友好标识，如 django-basics",
    )

    title = models.CharField(
        max_length=255,
        verbose_name="标题",
    )

    description = models.TextField(
        blank=True,
        default="",
        verbose_name="摘要",
        help_text="文章摘要，用于列表展示",
    )

    body = models.TextField(
        verbose_name="正文",
    )

    # 多对一关系：多篇文章 → 一个作者
    # on_delete=CASCADE: 删除作者时，其文章也删除
    # related_name: 反向查询名称（user.articles.all()）
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="articles",
        verbose_name="作者",
    )

    # 多对多关系：文章 ↔ 标签
    # Django 自动创建中间表 article_tags
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="articles",
        verbose_name="标签",
    )

    # 收藏：多对多（Django 自动建中间表 articles_favorited_by）
    # related_name="favorite_articles" → user.favorite_articles.all() 拿到该用户收藏的文章
    favorited_by = models.ManyToManyField(
        User,
        related_name="favorite_articles",
        blank=True,
        verbose_name="收藏者",
    )

    # 自动时间字段
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间",
    )

    class Meta:
        db_table = "articles"
        ordering = ["-created_at"]  # 默认按创建时间倒序
        verbose_name = "文章"
        verbose_name_plural = "文章"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        重写 save 方法，自动生成 slug

        如果 slug 为空，根据 title 生成
        """
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True)
            if not base_slug:
                base_slug = str(uuid.uuid4())[:8]
            slug = base_slug
            # 处理 slug 冲突
            counter = 1
            while Article.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Comment(models.Model):
    """
    评论模型

    类比 FastAPI 中的 Comment 表
    """
    body = models.TextField(
        verbose_name="评论内容",
    )

    # 多对一：多条评论 → 一篇文章
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="所属文章",
    )

    # 多对一：多条评论 → 一个用户
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="评论者",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间",
    )

    class Meta:
        db_table = "comments"
        ordering = ["-created_at"]
        verbose_name = "评论"
        verbose_name_plural = "评论"

    def __str__(self):
        return f"{self.author.username}: {self.body[:30]}"

    