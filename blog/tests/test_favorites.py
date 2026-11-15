"""
收藏功能测试。

⚠️ 与教案不一致的地方：教案验收表写的是「重复 favorite 返回 400；
unfavorite 未收藏返回 400」，但代码里是

    article.favorited_by.add(request.user)      # 幂等
    article.favorited_by.remove(request.user)   # 幂等

两个操作天然幂等，永远返回 200。这里按**代码实际行为**写断言。

如果哪天有人把接口改成「重复收藏报 400」，这组测试会红 —— 那说明契约被改动了。
前端可能依赖幂等语义（双击收藏不该报错），改之前要想清楚，
不要因为"测试红了"就直接改测试。
"""
from django.contrib.auth.models import User
from rest_framework import status

from blog.models import Article
from .base import BaseAPITestCase


class FavoriteTests(BaseAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(username='fauthor', password='pass12345')
        cls.fan = User.objects.create_user(username='ffan', password='pass12345')
        cls.article = Article.objects.create(
            title='收藏测试', body='x', author=cls.author
        )

    def _url(self):
        return f'/api/v3/articles/{self.article.slug}/favorite/'

    def test_favorite_marks_article_for_current_user(self):
        self.client.force_authenticate(self.fan)
        resp = self.client.post(self._url())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['article']['favorited'])
        self.assertEqual(resp.data['article']['favorites_count'], 1)

    def test_favorite_twice_is_idempotent(self):
        self.client.force_authenticate(self.fan)
        self.client.post(self._url())
        resp = self.client.post(self._url())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['article']['favorites_count'], 1)   # 不重复计数

    def test_unfavorite_removes_mark(self):
        self.client.force_authenticate(self.fan)
        self.client.post(self._url())
        resp = self.client.delete(self._url())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['article']['favorited'])
        self.assertEqual(resp.data['article']['favorites_count'], 0)

    def test_unfavorite_when_not_favorited_is_idempotent(self):
        """没收藏过也能删，不报错"""
        self.client.force_authenticate(self.fan)
        resp = self.client.delete(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_favorite_requires_auth(self):
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_articles_by_favorited_username(self):
        """?favorited=<username> 走 get_queryset 里的 favorited_by__username 过滤"""
        self.client.force_authenticate(self.fan)
        self.client.post(self._url())

        self.client.force_authenticate(None)   # 取消认证，按匿名查
        resp = self.client.get('/api/v3/articles/?favorited=ffan')

        self.assertEqual(resp.data['articlesCount'], 1)
        self.assertEqual(resp.data['articles'][0]['slug'], self.article.slug)
