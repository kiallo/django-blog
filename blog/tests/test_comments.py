"""
评论接口测试：嵌套路由（挂在文章下）+ 顶层资源（只有详情/改/删）。

⚠️ 两条路由的权限不一致，这是代码当前行为，测试如实锁住：

  · GET /articles/<slug>/comments/   → 需要登录
    因为 comments 是 @action，get_permissions 里
    `if self.action in ('favorite', 'feed', 'comments')` 把它整体划进 IsAuthenticated。

  · GET /comments/<id>/              → 匿名可读
    CommentViewSet 的权限是 IsAuthenticatedOrReadOnly，GET 属于 SAFE_METHODS。

如果你以后认为评论列表也应该公开，改 get_permissions 之后，
test_list_comments_requires_auth 会红 —— 那是提醒你契约变了，不是测试坏了。
"""
from django.contrib.auth.models import User
from rest_framework import status

from blog.models import Article, Comment
from .base import BaseAPITestCase


class CommentTests(BaseAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(username='cauthor2', password='pass12345')
        cls.reader = User.objects.create_user(username='creader2', password='pass12345')
        cls.article = Article.objects.create(
            title='评论文章', body='x', author=cls.author
        )
        cls.c1 = Comment.objects.create(
            body='第一条', article=cls.article, author=cls.reader
        )
        cls.c2 = Comment.objects.create(
            body='第二条', article=cls.article, author=cls.author
        )

    # ---------- 嵌套路由：/articles/<slug>/comments/ ----------

    def test_list_comments_requires_auth(self):
        """comments 动作被划进 IsAuthenticated，GET 也不例外"""
        resp = self.client.get(f'/api/v3/articles/{self.article.slug}/comments/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_comments_returns_count(self):
        self.client.force_authenticate(self.reader)
        resp = self.client.get(f'/api/v3/articles/{self.article.slug}/comments/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['commentsCount'], 2)
        self.assertEqual(len(resp.data['comments']), 2)

    def test_create_comment_wrapped_format(self):
        """请求体写成 {"comment": {"body": ...}}"""
        self.client.force_authenticate(self.reader)
        resp = self.client.post(
            f'/api/v3/articles/{self.article.slug}/comments/',
            {'comment': {'body': '包一层格式'}},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['comment']['body'], '包一层格式')

    def test_create_comment_bare_format(self):
        """请求体写成 {"body": ...} 也要支持（viewsets.comments 里的 request.data.get 兜底）"""
        self.client.force_authenticate(self.reader)
        resp = self.client.post(
            f'/api/v3/articles/{self.article.slug}/comments/',
            {'body': '裸格式'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['comment']['body'], '裸格式')

    def test_create_blank_comment_returns_400(self):
        """边界：纯空格 strip 之后为空，CommentWriteSerializer.validate_body 要拦下"""
        self.client.force_authenticate(self.reader)
        resp = self.client.post(
            f'/api/v3/articles/{self.article.slug}/comments/',
            {'body': '   '},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_comment_requires_auth(self):
        resp = self.client.post(
            f'/api/v3/articles/{self.article.slug}/comments/',
            {'body': '匿名评论'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ---------- 顶层资源：/comments/<id>/ ----------

    def test_comment_detail_is_wrapped(self):
        """注意这里是匿名请求：CommentViewSet 是 IsAuthenticatedOrReadOnly，GET 放行"""
        resp = self.client.get(f'/api/v3/comments/{self.c1.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('comment', resp.data)
        self.assertEqual(resp.data['comment']['body'], '第一条')

    def test_update_comment_body(self):
        """改评论用 CommentWriteSerializer，只接受 body 一个字段"""
        self.client.force_authenticate(self.reader)
        resp = self.client.patch(
            f'/api/v3/comments/{self.c1.id}/',
            {'body': '改过的内容'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['comment']['body'], '改过的内容')
