"""
评论接口测试：嵌套路由（挂在文章下）+ 顶层资源（只有详情/改/删）。

权限设计（改过一版，现在是统一的「读匿名、写登录」）：

  · GET  /articles/<slug>/comments/  → 匿名可读
    靠 ArticleViewSet.get_permissions 里单独给 comments 动作返回
    [IsAuthenticatedOrReadOnly()]，不带任何对象级权限。

  · POST /articles/<slug>/comments/  → 必须登录（未认证返回 401）
    如果这里误把 comments 交给 super()，类级的 IsAuthorOrAdminOrReadOnly
    会在 get_object() 阶段对 POST 做对象级检查，非文章作者评论会变成 403。
    test_create_comment_wrapped_format 用的正是「非作者」身份，
    它能过，就说明对象级权限没有被误加进来。

  · GET  /comments/<id>/             → 匿名可读（CommentViewSet 是 IsAuthenticatedOrReadOnly）
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

    def test_list_comments_allows_anonymous(self):
        """读匿名：comments 动作的权限是 IsAuthenticatedOrReadOnly，GET 属于 SAFE_METHODS"""
        resp = self.client.get(f'/api/v3/articles/{self.article.slug}/comments/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['commentsCount'], 2)

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
