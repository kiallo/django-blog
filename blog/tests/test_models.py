"""
模型层测试。

重点在 Article.save() 里那段手写的 slug 生成逻辑：它不是 Django 提供的，
是自己写的 while 循环，迁移换了数据库之后最容易因为唯一约束或排序规则变化而失效。
另外覆盖唯一约束和两级级联删除。

⚠️ 这一组刻意继承 django.test.TestCase 而不是 base.py 里的 BaseAPITestCase：
这里只走 ORM，不发 HTTP 请求，不需要 HTTP_HOST 补丁，也不需要 fakeredis。
依赖越少，出问题越好定位。
"""
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from blog.models import Article, Comment, Tag


class ArticleSlugTests(TestCase):
    """slug 自动生成、冲突后缀、空 slugify 兜底"""

    @classmethod
    def setUpTestData(cls):
        # 类级准备：整个类只执行一次，比每个用例都 create_user 快
        cls.user = User.objects.create_user(username='alice', password='pass12345')

    def test_slug_auto_generated_from_chinese_title(self):
        """中文标题经 slugify(allow_unicode=True) 后应得到非空 slug"""
        article = Article.objects.create(title='Django 入门', body='x', author=self.user)
        self.assertTrue(article.slug)
        self.assertIn('django', article.slug)  # ASCII 部分被保留

    def test_same_title_gets_incrementing_suffix(self):
        """同标题连建三篇：第二篇 -1，第三篇 -2，且都不抛 IntegrityError"""
        first = Article.objects.create(title='Hello World', body='x', author=self.user)
        second = Article.objects.create(title='Hello World', body='y', author=self.user)
        third = Article.objects.create(title='Hello World', body='z', author=self.user)

        self.assertEqual(second.slug, f'{first.slug}-1')
        self.assertEqual(third.slug, f'{first.slug}-2')

    def test_slug_falls_back_to_uuid_when_title_has_no_slug_chars(self):
        """
        边界：标题全是标点时 slugify 返回空串，
        save() 里 `if not base_slug` 那一支应该回落到 uuid 前 8 位。
        不写这条的话，这个分支永远没人走过。
        """
        article = Article.objects.create(title='!!!???', body='x', author=self.user)
        self.assertEqual(len(article.slug), 8)
        self.assertTrue(article.slug)

    def test_explicit_slug_is_not_overwritten(self):
        """显式传了 slug 就不该被 title 重新生成覆盖"""
        article = Article.objects.create(
            slug='my-custom-slug', title='任意标题', body='x', author=self.user
        )
        self.assertEqual(article.slug, 'my-custom-slug')

    def test_duplicate_explicit_slug_raises_integrity_error(self):
        """唯一约束在数据库层兜底：显式传重复 slug 会被拦下"""
        Article.objects.create(slug='dup', title='a', body='x', author=self.user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(slug='dup', title='b', body='x', author=self.user)


class TagTests(TestCase):
    def test_tag_name_unique(self):
        Tag.objects.create(name='python')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Tag.objects.create(name='python')

    def test_tags_ordered_by_name(self):
        """Meta.ordering = ['name']，不依赖插入顺序"""
        for name in ['redis', 'django', 'python']:
            Tag.objects.create(name=name)
        self.assertEqual(
            [tag.name for tag in Tag.objects.all()],
            ['django', 'python', 'redis'],
        )


class CascadeDeleteTests(TestCase):
    """两个 on_delete=CASCADE：User→Article→Comment 的链式删除"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='bob', password='pass12345')
        cls.article = Article.objects.create(title='级联测试', body='x', author=cls.user)
        Comment.objects.create(body='c1', article=cls.article, author=cls.user)

    def test_delete_user_cascades_articles_and_comments(self):
        self.user.delete()
        self.assertEqual(Article.objects.count(), 0)
        self.assertEqual(Comment.objects.count(), 0)

    def test_delete_article_cascades_comments(self):
        self.article.delete()
        self.assertEqual(Comment.objects.count(), 0)
