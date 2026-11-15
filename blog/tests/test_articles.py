"""
文章接口测试：分页契约、三种过滤器、搜索排序、详情 404、创建回显、标签同步、删除。

分页是这里最值得钉死的部分：响应契约是 {articles, articlesCount, page,
totalPages, next, previous}，前端整个列表页都依赖这六个字段，
任何一个人改了 pagination.py 的 get_paginated_response，这里会立刻红。
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status

from blog.models import Article, Comment, Tag
from .base import BaseAPITestCase


class ArticleListTests(BaseAPITestCase):
    """8 篇文章：7 篇属于 lister（标签 python/go 交替），1 篇属于 otherwriter"""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(username='lister', password='pass12345')
        cls.other = User.objects.create_user(username='otherwriter', password='pass12345')
        cls.tag_py = Tag.objects.create(name='python')
        cls.tag_go = Tag.objects.create(name='go')

        cls.articles = []
        for i in range(7):
            article = Article.objects.create(
                title=f'文章{i}', body=f'body {i}', author=cls.author
            )
            article.tags.add(cls.tag_py if i % 2 == 0 else cls.tag_go)
            cls.articles.append(article)

        cls.other_article = Article.objects.create(
            title='别人的文章', body='x', author=cls.other
        )

        # 手动错开 created_at：7 篇在同一瞬间创建的话，-created_at 排序不稳定，
        # 断言「第一篇是哪篇」就会时对时错。
        base = timezone.now()
        for offset, article in enumerate(cls.articles + [cls.other_article]):
            Article.objects.filter(pk=article.pk).update(
                created_at=base - timedelta(minutes=offset)
            )

    def test_list_returns_full_pagination_envelope(self):
        resp = self.client.get('/api/v3/articles/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ('articles', 'articlesCount', 'page', 'totalPages', 'next', 'previous'):
            self.assertIn(key, resp.data)

        self.assertEqual(resp.data['articlesCount'], 8)
        self.assertEqual(resp.data['page'], 1)
        self.assertEqual(resp.data['totalPages'], 2)      # 8 条 / page_size 5
        self.assertEqual(len(resp.data['articles']), 5)
        self.assertIsNone(resp.data['previous'])          # 第一页没有上一页
        self.assertIsNotNone(resp.data['next'])

    def test_second_page_has_remaining_items(self):
        resp = self.client.get('/api/v3/articles/?page=2')
        self.assertEqual(resp.data['page'], 2)
        self.assertEqual(len(resp.data['articles']), 3)
        self.assertIsNone(resp.data['next'])              # 最后一页没有下一页
        self.assertIsNotNone(resp.data['previous'])

    def test_limit_overrides_default_page_size(self):
        resp = self.client.get('/api/v3/articles/?limit=2')
        self.assertEqual(len(resp.data['articles']), 2)
        self.assertEqual(resp.data['totalPages'], 4)      # 8 / 2

    def test_limit_is_capped_by_max_page_size(self):
        """边界：?limit=999 会被 max_page_size=50 截断，8 篇全部落在一页"""
        resp = self.client.get('/api/v3/articles/?limit=999')
        self.assertEqual(len(resp.data['articles']), 8)
        self.assertEqual(resp.data['totalPages'], 1)

    def test_filter_by_tag(self):
        resp = self.client.get('/api/v3/articles/?tag=python')
        self.assertEqual(resp.data['articlesCount'], 4)   # i = 0,2,4,6
        for item in resp.data['articles']:
            self.assertIn('python', item['tag_list'])

    def test_filter_by_author(self):
        resp = self.client.get('/api/v3/articles/?author=otherwriter')
        self.assertEqual(resp.data['articlesCount'], 1)
        self.assertEqual(resp.data['articles'][0]['title'], '别人的文章')

    def test_search_matches_title(self):
        resp = self.client.get('/api/v3/articles/?search=文章3')
        self.assertEqual(resp.data['articlesCount'], 1)
        self.assertEqual(resp.data['articles'][0]['title'], '文章3')

    def test_ordering_by_created_at_desc(self):
        resp = self.client.get('/api/v3/articles/?ordering=-created_at')
        self.assertEqual(resp.data['articles'][0]['title'], '文章0')   # 最新

    def test_ordering_by_created_at_asc(self):
        resp = self.client.get('/api/v3/articles/?ordering=created_at')
        self.assertEqual(resp.data['articles'][0]['title'], '别人的文章')  # 最早


class ArticleDetailTests(BaseAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='detailer', password='pass12345')
        cls.article = Article.objects.create(
            title='详情文章', body='正文内容', author=cls.user
        )

    def test_detail_wrapped_in_article_envelope(self):
        """envelope('article', ...) 的外壳不能丢，前端按 data.article 取值"""
        resp = self.client.get(f'/api/v3/articles/{self.article.slug}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('article', resp.data)
        self.assertEqual(resp.data['article']['slug'], self.article.slug)
        self.assertEqual(resp.data['article']['body'], '正文内容')

    def test_unknown_slug_returns_404(self):
        resp = self.client.get('/api/v3/articles/no-such-article/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('detail', resp.data)   # DRF 的统一错误结构


class ArticleWriteTests(BaseAPITestCase):
    """创建 / 局部更新 / 删除，全部以作者身份操作"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='writer', password='pass12345')

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def test_create_returns_201_with_slug_and_author(self):
        """回显的不只是写入字段：必须带 slug 和嵌套 author"""
        resp = self.client.post(
            '/api/v3/articles/',
            {'title': '新文章标题', 'body': '正文', 'tag_list': ['django', 'drf']},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('article', resp.data)

        data = resp.data['article']
        self.assertTrue(data['slug'])
        self.assertEqual(data['author']['username'], 'writer')
        self.assertEqual(sorted(data['tag_list']), ['django', 'drf'])

    def test_create_short_title_returns_400(self):
        """ArticleWriteSerializer.validate_title：strip 后少于 3 字符"""
        resp = self.client.post(
            '/api/v3/articles/', {'title': 'ab', 'body': 'x'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_creates_missing_tags(self):
        """_sync_tags 里是 get_or_create，标签不存在要自动建"""
        self.client.post(
            '/api/v3/articles/',
            {'title': '带新标签的文章', 'body': 'x', 'tag_list': ['brand-new-tag']},
            format='json',
        )
        self.assertTrue(Tag.objects.filter(name='brand-new-tag').exists())

    def test_patch_without_tag_list_keeps_existing_tags(self):
        """
        update() 里用 pop('tag_list', None) 而不是 default=[]，
        就是为了这个：PATCH 不带 tag_list 应该是「不改标签」，不是「清空标签」。
        """
        article = Article.objects.create(title='保留标签', body='x', author=self.user)
        article.tags.add(Tag.objects.create(name='keep-me'))

        resp = self.client.patch(
            f'/api/v3/articles/{article.slug}/', {'title': '改个标题'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        article.refresh_from_db()
        self.assertEqual([tag.name for tag in article.tags.all()], ['keep-me'])

    def test_patch_with_tag_list_replaces_all_tags(self):
        """反过来：传了就整体替换（set() 会自己处理增删）"""
        article = Article.objects.create(title='替换标签', body='x', author=self.user)
        article.tags.add(Tag.objects.create(name='old-tag'))

        resp = self.client.patch(
            f'/api/v3/articles/{article.slug}/', {'tag_list': ['new-tag']}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        article.refresh_from_db()
        self.assertEqual([tag.name for tag in article.tags.all()], ['new-tag'])

    def test_delete_own_article(self):
        article = Article.objects.create(title='待删除文章', body='x', author=self.user)
        resp = self.client.delete(f'/api/v3/articles/{article.slug}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Article.objects.filter(pk=article.pk).exists())


class StatsTests(BaseAPITestCase):
    def test_counts_are_not_inflated_by_join(self):
        """
        stats() 里两个 Count 都写了 distinct=True。

        不写的话，Article 和 Comment 的 JOIN 会让 totalArticles 变成
        「文章数 × 评论数」。这里特意让 1 篇文章挂 3 条评论：
        正确值是 2 篇文章，写错了会变成 4。
        """
        author = User.objects.create_user(username='stat-author', password='pass12345')
        commenter = User.objects.create_user(username='stat-commenter', password='pass12345')
        article_a = Article.objects.create(title='统计一', body='x', author=author)
        Article.objects.create(title='统计二', body='x', author=author)
        Tag.objects.create(name='t1')
        for i in range(3):
            Comment.objects.create(body=f'c{i}', article=article_a, author=commenter)

        resp = self.client.get('/api/v3/articles/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['totalArticles'], 2)
        self.assertEqual(resp.data['totalComments'], 3)
        self.assertEqual(resp.data['totalTags'], 1)
        self.assertEqual(resp.data['totalAuthors'], 1)   # 只有 author 写过文章
