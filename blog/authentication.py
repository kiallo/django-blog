"""
JWT 认证 + Redis 白名单校验

对标 FastAPI 项目的 app/api/dependencies/authentication.py 里的 _get_current_user：

    FastAPI 版本的手工流程：
      1. 从 Header 取 token
      2. 解析 JWT → 拿 username
      3. 查 Redis 白名单           ← 我们要插入的这一步
      4. 查数据库拿 User

    DRF 里第 1、2、4 步 simplejwt 全帮你做了，
    我们只需要继承并覆写 authenticate()，插入第 3 步。
"""
import logging

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .session_store import get_session_store

logger = logging.getLogger(__name__)


class RedisJWTAuthentication(JWTAuthentication):
    """
    在 simplejwt 的基础上增加 Redis 白名单校验

    换成这个类之后：
      - 登出能真的登出（JWT 本身还有效，但白名单没了）
      - 支持强制下线
      - 支持单点登录（同一账号只保留最新会话）
    """

    def authenticate(self, request):
        # 父类做的事：
        #   ① 从 Authorization: Bearer xxx 里取 token，取不到 → 返回 None（匿名）
        #   ② 验证签名和过期时间，失败 → 抛 AuthenticationFailed / InvalidToken
        #   ③ 按 user_id claim 查数据库拿 User
        result = super().authenticate(request)

        if result is None:
            # 没带凭据 → 匿名用户，交给权限类去判断要不要拦
            return None

        user, validated_token = result

        # 从自定义 claim 里取出会话 ID
        sid = validated_token.get("sid")
        if not sid:
            raise AuthenticationFailed("令牌缺少会话标识，请重新登录")

        # 查 Redis 白名单
        store = get_session_store()
        if not store.is_session_valid(user.username, sid):
            raise AuthenticationFailed("会话已失效，请重新登录")

        return result