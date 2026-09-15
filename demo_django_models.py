# demo_django_models.py
"""
Django 模型演示脚本

演示 Django ORM 的核心操作
"""
import os
import django

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.contrib.auth.models import User
from blog.models import Article, Tag, Comment


def demo_create():
    """演示创建数据"""
    print("=" * 60)
    print("📌 创建数据演示")
    print("=" * 60)

    # 创建用户
    user, created = User.objects.get_or_create(
        username='demo_user',
        defaults={'email': 'demo@example.com'}
    )
    if created:
        user.set_password('demo123')
        user.save()
        print(f"  创建用户: {user.username}")
    else:
        print(f"  用户已存在: {user.username}")

    # 创建标签
    for tag_name in ['Python', 'Django', 'DRF', 'Redis']:
        Tag.objects.get_or_create(name=tag_name)
    print(f"  标签数量: {Tag.objects.count()}")

    # 创建文章
    article, created = Article.objects.get_or_create(
        slug='demo-article',
        defaults={
            'title': 'Django ORM 演示文章',
            'description': '这是一篇演示文章',
            'body': 'Django ORM 让数据库操作变得简单...',
            'author': user,
        }
    )
    if created:
        article.tags.add(Tag.objects.get(name='Python'))
        article.tags.add(Tag.objects.get(name='Django'))
        print(f"  创建文章: {article.title}")
    else:
        print(f"  文章已存在: {article.title}")


def demo_query():
    """演示查询数据"""
    print("\n" + "=" * 60)
    print("📌 查询数据演示")
    print("=" * 60)

    # 基本查询
    articles = Article.objects.all()
    print(f"  文章总数: {articles.count()}")

    # 条件查询
    python_articles = Article.objects.filter(tags__name='Python')
    print(f"  Python 相关: {python_articles.count()} 篇")

    # 关联查询
    for article in articles[:3]:
        tags = ', '.join(article.tags.values_list('name', flat=True))
        comments = article.comments.count() # type: ignore
        print(f"  [{article.id}] {article.title}") # type: ignore
        print(f"      标签: {tags or '无'}")
        print(f"      评论: {comments} 条")
        print(f"      作者: {article.author.username}")

    # 聚合查询
    from django.db.models import Count
    tag_stats = Tag.objects.annotate(num_articles=Count('articles'))
    print(f"\n  标签统计:")
    for tag in tag_stats:
        print(f"    {tag.name}: {tag.num_articles} 篇") # type: ignore


def demo_update():
    """演示更新数据"""
    print("\n" + "=" * 60)
    print("📌 更新数据演示")
    print("=" * 60)

    article = Article.objects.first()
    if article:
        old_title = article.title
        article.title = article.title + " (已更新)"
        article.save()
        print(f"  更新标题: {old_title} → {article.title}")

        # 批量更新
        count = Article.objects.filter(author__username='demo_user').update(
            description="批量更新的描述"
        )
        print(f"  批量更新: {count} 篇文章")


def demo_delete():
    """演示删除数据"""
    print("\n" + "=" * 60)
    print("📌 删除数据演示")
    print("=" * 60)

    # 删除最后一篇文章
    last = Article.objects.last()
    if last:
        print(f"  删除文章: {last.title}")
        last.delete()

    print(f"  剩余文章: {Article.objects.count()} 篇")


if __name__ == '__main__':
    demo_create()
    demo_query()
    demo_update()
    demo_delete()

    print("\n" + "=" * 60)
    print("✅ 演示完成！")
    print("=" * 60)