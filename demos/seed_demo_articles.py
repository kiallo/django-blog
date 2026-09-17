"""
第10课测试数据：批量创建演示文章
运行：python seed_demo_articles.py
"""
import os
import sys

import django

# 把项目根目录加入模块搜索路径，保证在 demos/ 下也能 import mysite / blog
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth.models import User          # noqa: E402
from django.utils.text import slugify                # noqa: E402
from blog.models import Article, Tag                 # noqa: E402

TOPICS = [
    ("Python 装饰器入门", ["Python", "基础"]),
    ("Python 生成器与协程", ["Python", "异步"]),
    ("FastAPI 依赖注入详解", ["FastAPI", "Python"]),
    ("FastAPI 中间件实战", ["FastAPI"]),
    ("Redis 缓存穿透与雪崩", ["Redis", "缓存"]),
    ("Redis 分布式锁实现", ["Redis"]),
    ("Django ORM 查询优化", ["Django", "ORM"]),
    ("Django 信号机制", ["Django"]),
    ("DRF 序列化器进阶", ["Django", "DRF"]),
    ("DRF 视图与路由", ["Django", "DRF"]),
    ("SQL 索引原理", ["数据库"]),
    ("Docker 部署 Python 应用", ["部署"]),
]

author = User.objects.get(username="kiallo")
created = 0

for index, (title, tag_names) in enumerate(TOPICS, start=1):
    slug = slugify(title, allow_unicode=True)
    if Article.objects.filter(slug=slug).exists():
        continue

    article = Article.objects.create(
        slug=slug,
        title=title,
        description=f"{title} 的摘要说明，用于列表页展示。",
        body=f"这是《{title}》的正文内容。\n\n" + "正文段落。\n" * 5,
        author=author,
    )
    for name in tag_names:
        tag, _ = Tag.objects.get_or_create(name=name)
        article.tags.add(tag)
    created += 1

print(f"✅ 新增 {created} 篇文章，当前共 {Article.objects.count()} 篇")