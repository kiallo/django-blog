"""
权限测试：重点是 401 和 403 的分水岭。

401 = 你没证明你是谁（未认证）
403 = 你证明了，但你没这个权力（已认证但非作者）

这两者的边界由「第一个认证器的 authenticate_header() 有没有返回值」决定。
settings 里 RedisJWTAuthentication 排在 SessionAuthentication 前面，
所以未认证访问受保护接口拿到的是 401；一旦顺序被调换，会变成 403。
下面第一条测试就是用来钉住这个顺序的。

⚠️ 这一组全部用 force_authenticate，不经过 token 解析和 Redis 白名单。
认证和权限是两件事，分开测才能定位问题：
  · 这里红了 → 权限类写错了
  · test_auth 红了 → 认证链路坏了
"""
from django.contrib.auth.models import User
from rest_framework import status

from blog.models import Article, Comment
from .base import BaseAPITestCase


class ArticlePermissionTests(BaseAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(username='author', password='pass12345')
        cls.other = User.objects.create_user(username='other', password='pass12345')
        cls.admin = User.objects.create_user(
            username='admin', password='pass12345', is_staff=True
        )
        cls.article = Article.objects.create(
            title='权限测试', body='x', author=cls.author
        )

    def test_anonymous_write_returns_401_not_403(self):
        """认证器顺序的守门测试：JWT 在前 → 401；SessionAuthentication 在前 → 403"""
        resp = self.client.post(
            '/api/v3/articles/',
            {'title': '趁乱发一篇', 'body': 'x'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_author_cannot_update(self):
        """非作者改别人的文章：403，不是 404，也不是 401"""
        self.client.force_authenticate(self.other)
        resp = self.client.patch(
            f'/api/v3/articles/{self.article.slug}/',
            {'title': 'hacked'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_author_can_update_own_article(self):
        self.client.force_authenticate(self.author)
        resp = self.client.patch(
            f'/api/v3/articles/{self.article.slug}/',
            {'title': '作者改的'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_staff_can_update_others_article(self):
        """IsAuthorOrAdminOrReadOnly 给 is_staff 开的那个后门"""
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            f'/api/v3/articles/{self.article.slug}/',
            {'title': '管理员改的'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_anonymous_can_read_list(self):
        """IsAuthenticatedOrReadOnly：读操作对匿名开放"""
        resp = self.client.get('/api/v3/articles/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class CommentPermissionTests(BaseAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(username='cauthor', password='pass12345')
        cls.other = User.objects.create_user(username='cother', password='pass12345')
        cls.article = Article.objects.create(
            title='评论权限文章', body='x', author=cls.author
        )
        cls.comment = Comment.objects.create(
            body='原始评论', article=cls.article, author=cls.author
        )

    def test_non_author_cannot_delete_comment(self):
        self.client.force_authenticate(self.other)
        resp = self.client.delete(f'/api/v3/comments/{self.comment.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_author_can_delete_own_comment(self):
        self.client.force_authenticate(self.author)
        resp = self.client.delete(f'/api/v3/comments/{self.comment.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_anonymous_delete_comment_returns_401(self):
        resp = self.client.delete(f'/api/v3/comments/{self.comment.id}/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
