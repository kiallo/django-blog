"""
认证链路测试：注册 → 登录 → 带 token 访问 → 登出 → 旧 token 失效。

⚠️ 两处断言和教案不一样，是按**代码实际行为**写的：

  · 密码错误返回 400，不是 401。
    原因：LoginSerializer.validate 抛的是 serializers.ValidationError，
    DRF 把它转成 400。401 只留给「凭据缺失/无效」这一层
    （未带 token、token 过期、白名单里查不到）。

  · 用户不存在也返回 400，且文案与密码错误完全相同。
    这是 LoginSerializer 里明确注释过的设计：不区分两种情况，防止用户名枚举。
    测试要锁住这个「不可区分性」，否则以后有人为了「友好提示」把它拆开，
    测试会提醒他这是在开倒车。
"""
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from blog.session_store import get_session_store
from .base import BaseAPITestCase, RedisIsolatedTestCase


class RegisterTests(BaseAPITestCase):
    """注册不写 Redis，用普通基类即可"""

    def test_register_success_returns_201_and_hashes_password(self):
        resp = self.client.post(
            '/api/v3/auth/register/',
            {'username': 'newbie', 'password': 'pass12345', 'password2': 'pass12345'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username='newbie')
        self.assertNotEqual(user.password, 'pass12345')   # 不能明文入库
        self.assertTrue(user.check_password('pass12345'))
        self.assertEqual(resp.data['user']['username'], 'newbie')

    def test_register_duplicate_username_returns_400(self):
        User.objects.create_user(username='dup', password='pass12345')
        resp = self.client.post(
            '/api/v3/auth/register/',
            {'username': 'dup', 'password': 'pass12345', 'password2': 'pass12345'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch_returns_400_and_creates_nothing(self):
        resp = self.client.post(
            '/api/v3/auth/register/',
            {'username': 'mismatch', 'password': 'pass12345', 'password2': 'other12345'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username='mismatch').exists())

    def test_register_short_password_returns_400(self):
        """RegisterSerializer 的 min_length=6"""
        resp = self.client.post(
            '/api/v3/auth/register/',
            {'username': 'shorty', 'password': '12345', 'password2': '12345'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(RedisIsolatedTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='alice', password='pass12345')

    def test_login_success_returns_tokens_and_user(self):
        resp = self.client.post(
            '/api/v3/auth/login/',
            {'username': 'alice', 'password': 'pass12345'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)
        self.assertEqual(resp.data['user']['username'], 'alice')

    def test_login_wrong_password_returns_400_not_401(self):
        resp = self.client.post(
            '/api/v3/auth/login/',
            {'username': 'alice', 'password': 'wrong-pass'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_unknown_user_is_indistinguishable_from_wrong_password(self):
        """防用户名枚举：两种失败的响应体和状态码必须一致"""
        wrong_pwd = self.client.post(
            '/api/v3/auth/login/',
            {'username': 'alice', 'password': 'wrong-pass'},
            format='json',
        )
        no_user = self.client.post(
            '/api/v3/auth/login/',
            {'username': 'nobody-here', 'password': 'wrong-pass'},
            format='json',
        )
        self.assertEqual(wrong_pwd.status_code, no_user.status_code)
        self.assertEqual(wrong_pwd.data, no_user.data)

    def test_login_writes_session_whitelist_to_redis(self):
        """登录成功后 Redis 必须有会话记录，否则后续请求全 401"""
        self.client.post(
            '/api/v3/auth/login/',
            {'username': 'alice', 'password': 'pass12345'},
            format='json',
        )
        info = get_session_store().get_session('alice')
        self.assertIsNotNone(info)
        self.assertEqual(info['username'], 'alice')
        self.assertIn('sid', info)


class TokenGuardTests(RedisIsolatedTestCase):
    """带 token 访问受保护接口的三条路径：正常、会话已删、token 缺 sid"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='carol', password='pass12345')

    def _login(self, username='carol', password='pass12345'):
        resp = self.client.post(
            '/api/v3/auth/login/',
            {'username': username, 'password': password},
            format='json',
        )
        return resp.data

    def test_me_requires_authentication(self):
        resp = self.client.get('/api/v3/auth/me/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user_with_valid_token(self):
        tokens = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = self.client.get('/api/v3/auth/me/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['username'], 'carol')

    def test_logout_invalidates_existing_token(self):
        """
        白名单策略的价值：JWT 签名本身仍然有效，
        但 Redis 里的会话被删掉 → 同一个 token 立刻 401。
        """
        tokens = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        logout_resp = self.client.post('/api/v3/auth/logout/')
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)

        me_resp = self.client.get('/api/v3/auth/me/')   # 同一个 client，token 没变
        self.assertEqual(me_resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_without_sid_claim_is_rejected(self):
        """
        直接 for_user 签出来的 token 没有 sid claim，
        RedisJWTAuthentication 应该明确拒绝，而不是放行。
        """
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        resp = self.client.get('/api/v3/auth/me/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_fails_after_logout(self):
        """refresh token 也要过白名单检查，登出后不能续命"""
        tokens = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.client.post('/api/v3/auth/logout/')

        resp = self.client.post(
            '/api/v3/auth/refresh/',
            {'refresh': tokens['refresh']},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
