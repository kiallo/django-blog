"""
Redis 会话存储 —— 白名单策略

直接对标 FastAPI 项目的 app/services/token_storage.py，
区别只有一点：Django 是同步框架，这里用同步的 redis 客户端（那边是 redis.asyncio）。
"""
import json
import logging
from datetime import datetime, timezone

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# 模块级单例：整个进程复用一个连接池
_client = None


def get_redis_client():
    """
    获取 Redis 客户端（连接池复用）

    类比 FastAPI 项目的 app/core/dependencies.py 里的 get_redis 依赖
    """
    global _client
    if _client is None:
        _client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,      # 直接返回 str，省掉手动 decode
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _client


class SessionStore:
    """
    Redis 会话存储管理器

    白名单策略：会话记录在 Redis 里存在，Token 才算有效
    """

    # Key 前缀（加 django: 是为了和 FastAPI 项目的 session:user: 区分开）
    SESSION_PREFIX = "django:session:user:"
    ONLINE_USERS_KEY = "django:online:users"      # 在线用户集合

    def __init__(self, client=None):
        self.redis = client or get_redis_client()

    # ---------- 写 ----------

    def save_session(
        self,
        username: str,
        sid: str,
        expire_seconds: int,
        device_info: str = "unknown",
    ) -> bool:
        """
        保存会话（登录时调用）

        参数：
            username:       用户名（也是 Redis key 的一部分）
            sid:            会话 ID（随机串，会塞进 JWT 的 sid claim）
            expire_seconds: 过期时间。⚠️ 必须 >= refresh token 的有效期，
                            否则用户 refresh 时会因为白名单已过期而被踢下线
            device_info:    设备信息（记录用）
        """
        key = f"{self.SESSION_PREFIX}{username}"
        data = {
            "sid": sid,
            "username": username,
            "login_time": datetime.now(timezone.utc).isoformat(),
            "device_info": device_info,
        }

        try:
            # setex = SET + EXPIRE，一条命令搞定
            self.redis.setex(key, expire_seconds, json.dumps(data))
            # 加入在线用户集合（Set 自动去重）
            self.redis.sadd(self.ONLINE_USERS_KEY, username)
            logger.info(f"✅ 会话已创建: {username} (TTL: {expire_seconds}s)")
            return True
        except redis.RedisError as exc:
            logger.error(f"❌ 会话保存失败: {exc}")
            return False

    def revoke_session(self, username: str) -> bool:
        """
        撤销会话（登出时调用）

        删掉这一条，用户手里的 access 和 refresh 就同时失效了。
        """
        key = f"{self.SESSION_PREFIX}{username}"

        try:
            deleted = self.redis.delete(key)
            self.redis.srem(self.ONLINE_USERS_KEY, username)

            if deleted:
                logger.info(f"🚪 会话已撤销: {username}")
            else:
                logger.warning(f"⚠️ 会话不存在: {username}")
            return bool(deleted)
        except redis.RedisError as exc:
            logger.error(f"❌ 会话撤销失败: {exc}")
            return False

    # ---------- 读 ----------

    def get_session(self, username: str) -> dict | None:
        """获取会话详情，不存在返回 None"""
        try:
            raw = self.redis.get(f"{self.SESSION_PREFIX}{username}")
            return json.loads(raw) if raw else None
        except (redis.RedisError, json.JSONDecodeError) as exc:
            logger.error(f"❌ 读取会话失败: {exc}")
            return None

    def is_session_valid(self, username: str, sid: str) -> bool:
        """
        校验会话是否有效（每次请求都会调用）

        Redis 里存的 sid 和 JWT 里的 sid 必须对得上。
        """
        if not username or not sid:
            return False

        session = self.get_session(username)
        if session is None:
            return False

        return session.get("sid") == sid

    def get_session_info(self, username: str) -> dict | None:
        """会话详情 + 剩余 TTL（给"我的登录设备"这类页面用）"""
        session = self.get_session(username)
        if session is None:
            return None

        try:
            session["ttl_seconds"] = self.redis.ttl(f"{self.SESSION_PREFIX}{username}")
        except redis.RedisError:
            session["ttl_seconds"] = -1
        return session

    def get_online_users(self) -> list[str]:
        """在线用户列表"""
        try:
            return sorted(self.redis.smembers(self.ONLINE_USERS_KEY)) # type: ignore
        except redis.RedisError as exc:
            logger.error(f"❌ 获取在线用户失败: {exc}")
            return []


# 模块级单例（视图和认证类共用同一个实例）
_store = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store