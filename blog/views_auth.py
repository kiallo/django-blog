"""
认证接口：注册 / 登录 / 刷新 / 登出 / 当前用户

对标 FastAPI 项目的 app/api/routes/authentication.py
"""

import logging
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    EmptySerializer,
    LoginSerializer,
    RefreshSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .session_store import get_session_store

logger = logging.getLogger(__name__)


# ---------- 文档专用 ----------
# 注意这里用 inline_serializer 而不是直接写某个序列化器类：
# 这些接口返回的是 {"access": "...", "user": {...}} 这种拼出来的字典，
# 不是某个序列化器本身，inline_serializer 才能把整体结构描述出来。
# 只在生成 schema 时用到，不影响运行时逻辑。


class AuthViewSet(viewsets.GenericViewSet):
    """
    认证 ViewSet

    只放 @action，不放标准 CRUD，所以继承 GenericViewSet 就够了。
    （GenericViewSet 不带任何 Mixin，一个标准动作都没有）
    """
    serializer_class = EmptySerializer
    # 默认要求登录；register/login/refresh 在 get_permissions 里单独放行
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'register':
            return RegisterSerializer
        if self.action == 'login':
            return LoginSerializer
        if self.action == 'refresh':
            return RefreshSerializer
        if self.action == 'me':
            return UserSerializer
        return EmptySerializer

    def get_permissions(self):
        """
        动态权限 —— 公开接口和需登录接口混在同一个 ViewSet 里时用这个

        比在 @action 里写 permission_classes=[...] 更通用：
        后者只在通过 Router 注册时生效（Router 会把 kwargs 传给 as_view）。
        """
        if self.action in ('list', 'register', 'login', 'refresh'):
            return [AllowAny()]
        if self.action in ('force_logout', 'online'):
            return [IsAdminUser()]
        return super().get_permissions()

    def get_throttles(self):
        """登录接口单独限流，防暴力破解"""
        if self.action == 'login':
            return [ScopedRateThrottle()]
        return super().get_throttles()

    # ScopedRateThrottle 会读这个属性，去 settings 的 DEFAULT_THROTTLE_RATES['login'] 取速率
    throttle_scope = 'login'

    # ---------- 接口目录 ----------

    @extend_schema(
        summary='认证接口目录',
        description='GET /api/v3/auth/ 列出本 ViewSet 全部接口的 URL。',
        request=None,
        responses={200: inline_serializer(
            'AuthIndexResponse',
            {
                'register': serializers.CharField(),
                'login': serializers.CharField(),
                'refresh': serializers.CharField(),
                'logout': serializers.CharField(),
                'me': serializers.CharField(),
                'mySession': serializers.CharField(),
                'forceLogout': serializers.CharField(),
                'online': serializers.CharField(),
            },
        )},
    )
    def list(self, request):
        """
        GET /api/v3/auth/

        ⚠️ 这个方法存在的意义不只是"做个目录"：

        DefaultRouter 的 API 根页面（/api/v3/）里，每个 ViewSet 只按
        "{basename}-list" 这个路由名去 reverse（见 routers.py 的
        get_api_root_view）。本 ViewSet 全是 @action 动作、没有 list，
        于是 "auth-list" 不存在 → NoReverseMatch → 根页面静默跳过 auth。

        补上这个 list 动作，根页面才会出现 auth 这一项。
        """
        return Response({
            'register': reverse('auth-register', request=request),
            'login': reverse('auth-login', request=request),
            'refresh': reverse('auth-refresh', request=request),
            'logout': reverse('auth-logout', request=request),
            'me': reverse('auth-me', request=request),
            'mySession': reverse('auth-my-session', request=request),
            'forceLogout': reverse('auth-force-logout', request=request),
            'online': reverse('auth-online', request=request),
        })

    # ---------- 注册 ----------

    @extend_schema(
        summary='注册',
        description='POST /api/v3/auth/register/ 创建新用户。注册成功后不会自动登录，需要再调 login。',
        request=RegisterSerializer,
        responses={
            201: inline_serializer(
                'RegisterResponse',
                {
                    'user': UserSerializer(),
                    'detail': serializers.CharField(),
                },
            ),
            400: OpenApiResponse(description='用户名已存在 / 两次密码不一致 / 密码少于 6 位'),
        },
    )
    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request):
        """POST /api/v3/auth/register/"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'user': UserSerializer(user).data,
                'detail': '注册成功，请登录',
            },
            status=status.HTTP_201_CREATED,
        )

    # ---------- 登录 ----------

    @extend_schema(
        summary='登录',
        description=(
            'POST /api/v3/auth/login/ 校验用户名密码，返回 access + refresh，\n'
            '同时把会话写进 Redis 白名单（带限流，见 throttle_scope = "login"）。'
        ),
        request=LoginSerializer,
        responses={
            200: inline_serializer(
                'LoginResponse',
                {
                    'access': serializers.CharField(),
                    'refresh': serializers.CharField(),
                    'user': UserSerializer(),
                },
            ),
            400: OpenApiResponse(description='用户名或密码错误 / 账号已被禁用'),
            429: OpenApiResponse(description='登录过于频繁，被限流'),
        },
    )
    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        """
        POST /api/v3/auth/login/
        返回 access + refresh，同时在 Redis 建立白名单会话
        """
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # 生成会话 ID
        sid = uuid.uuid4().hex

        # 签发 Token
        refresh = RefreshToken.for_user(user)
        # 自定义 claim：会被自动复制到 access token 里
        refresh['username'] = user.username
        refresh['sid'] = sid
        access = refresh.access_token     # ⚠️ 必须在设置 claim 之后再取

        # 写入 Redis 白名单
        # TTL 用 refresh 的有效期：白名单要活得比 access 久，refresh 才有意义
        ttl = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
        store = get_session_store()
        store.save_session(
            username=user.username,
            sid=sid,
            expire_seconds=ttl,
            device_info=request.META.get('HTTP_USER_AGENT', 'unknown')[:200],
        )

        return Response({
            'access': str(access),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        })

    # ---------- 刷新 ----------

    @extend_schema(
        summary='刷新 access token',
        description='POST /api/v3/auth/refresh/ 用 refresh token 换一个新的 access token（会话已失效则 401）。',
        request=RefreshSerializer,
        responses={
            200: inline_serializer(
                'RefreshResponse',
                {'access': serializers.CharField()},
            ),
            401: OpenApiResponse(description='刷新令牌无效或已过期，或会话已被登出 / 强制下线'),
        },
    )
    @action(detail=False, methods=['post'], url_path='refresh')
    def refresh(self, request):
        """POST /api/v3/auth/refresh/  用 refresh 换新 access"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh = RefreshToken(serializer.validated_data['refresh'])
        except TokenError as exc:
            raise AuthenticationFailed(f'刷新令牌无效或已过期: {exc}')

        # ⚠️ 光验签名不够：还得确认这个会话没被登出/强制下线
        store = get_session_store()
        username = refresh.get('username')
        if not store.is_session_valid(username, refresh.get('sid')):
            raise AuthenticationFailed('会话已失效，请重新登录')

        # refresh.access_token 会复制自定义 claim（sid / username）
        return Response({'access': str(refresh.access_token)})

    # ---------- 登出 ----------

    @extend_schema(
        summary='登出',
        description=(
            'POST /api/v3/auth/logout/ 删除 Redis 里的会话记录。\n'
            'JWT 签名本身依然有效，但白名单查不到 → 之后的请求一律 401。'
        ),
        request=None,
        responses={
            200: inline_serializer(
                'LogoutResponse',
                {'detail': serializers.CharField()},
            ),
            401: OpenApiResponse(description='未登录，或会话已失效（白名单里查不到）'),
        },
    )
    @action(detail=False, methods=['post'], url_path='logout')
    def logout(self, request):
        """
        POST /api/v3/auth/logout/

        只做一件事：删掉 Redis 里的会话记录。
        用户手里的 JWT 签名依然有效，但认证类查白名单查不到 → 直接 401。
        这就是白名单策略的价值。
        """
        store = get_session_store()
        revoked = store.revoke_session(request.user.username)

        return Response({
            'detail': '已登出' if revoked else '会话已失效',
        })

    # ---------- 当前用户 ----------

    @extend_schema(
        summary='当前登录用户',
        description='GET /api/v3/auth/me/ 前端刷新页面时用它恢复登录状态。',
        request=None,
        responses={
            200: UserSerializer,
            401: OpenApiResponse(description='未登录，或会话已失效（白名单里查不到）'),
        },
    )
    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """GET /api/v3/auth/me/  前端刷新页面时用它恢复登录状态"""
        return Response(self.get_serializer(request.user).data)

    @extend_schema(
        summary='我的会话详情',
        description='GET /api/v3/auth/my-session/ 查看自己的会话信息与剩余时间（sid 不会返回给客户端）。',
        request=None,
        responses={
            200: inline_serializer(
                'MySessionResponse',
                {
                    'username': serializers.CharField(),
                    'login_time': serializers.DateTimeField(
                        help_text='登录时间（UTC，ISO 8601 字符串）',
                    ),
                    'device_info': serializers.CharField(
                        help_text='登录时的 User-Agent',
                    ),
                    'ttl_seconds': serializers.IntegerField(
                        help_text='会话剩余秒数，-1 表示没有设置过期时间',
                    ),
                },
            ),
            401: OpenApiResponse(description='会话不存在（未登录或已登出）'),
        },
    )
    @action(detail=False, methods=['get'], url_path='my-session')
    def my_session(self, request):
        """GET /api/v3/auth/my-session/  查看自己的会话详情（含剩余时间）"""
        store = get_session_store()
        info = store.get_session_info(request.user.username)
        if info is None:
            raise AuthenticationFailed('会话不存在')

        # sid 是服务端凭据，没必要回传给客户端
        info.pop('sid', None)
        return Response(info)

    # ---------- 管理员：强制下线 ----------

    @extend_schema(
        summary='强制用户下线【管理员】',
        description=(
            'POST /api/v3/auth/force-logout/ 把指定用户的会话从白名单删掉。\n'
            '权限：仅 is_staff 用户可用。'
        ),
        request=inline_serializer(
            'ForceLogoutBody',
            {'username': serializers.CharField(help_text='要强制下线的用户名')},
        ),
        responses={
            200: inline_serializer(
                'ForceLogoutResponse',
                {
                    'detail': serializers.CharField(),
                    'revoked': serializers.BooleanField(
                        help_text='true = 确实踢下线了；false = 该用户当时不在线',
                    ),
                },
            ),
            400: OpenApiResponse(description='没传 username'),
            401: OpenApiResponse(description='未登录，或会话已失效（白名单里查不到）'),
            403: OpenApiResponse(description='当前用户不是管理员'),
        },
    )
    @action(detail=False, methods=['post'], url_path='force-logout')
    def force_logout(self, request):
        """
        POST /api/v3/auth/force-logout/  {"username": "zhangsan"}

        无状态 JWT 做不到、只有白名单才能做到的事。
        权限：仅 is_staff 用户可用（见 get_permissions）
        """
        username = request.data.get('username')
        if not username:
            return Response(
                {'detail': '请提供 username'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        store = get_session_store()
        revoked = store.revoke_session(username)

        return Response({
            'detail': f'已强制 {username} 下线' if revoked else f'{username} 当前不在线',
            'revoked': revoked,
        })

    @extend_schema(
        summary='在线用户列表【管理员】',
        description='GET /api/v3/auth/online/ 从 Redis 的在线集合里取当前在线用户名。权限：仅 is_staff 用户可用。',
        request=None,
        responses={
            200: inline_serializer(
                'OnlineUsersResponse',
                {
                    'onlineUsers': serializers.ListField(child=serializers.CharField()),
                    'count': serializers.IntegerField(),
                },
            ),
            401: OpenApiResponse(description='未登录，或会话已失效（白名单里查不到）'),
            403: OpenApiResponse(description='当前用户不是管理员'),
        },
    )
    @action(detail=False, methods=['get'], url_path='online')
    def online(self, request):
        """GET /api/v3/auth/online/  在线用户列表（权限：见 get_permissions → IsAdminUser）"""
        store = get_session_store()
        users = store.get_online_users()
        return Response({'onlineUsers': users, 'count': len(users)})