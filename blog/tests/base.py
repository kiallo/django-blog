"""
测试基类。

这里处理两个「不改业务代码就必须绕过」的环境问题：

1. ALLOWED_HOSTS 里没有 'testserver'
   Django 测试客户端默认发 Host: testserver，会被 DisallowedHost 拦成 400，
   于是所有用例一起变成假失败。这里在 client 的默认请求头里覆盖成 localhost，
   不动 settings.py，也不给生产配置开后门。

2. blog.session_store 里有**两个**模块级单例
   _client（redis 客户端）和 _store（SessionStore 实例）。
   上一个用例登出会写 Redis，下一个用例拿到同一个客户端，状态就串了。
   RedisIsolatedTestCase 把两者一并替换：_client 用 fakeredis 的内存实现，
   _store 置空，逼 get_session_store() 按新的 _client 重建一个干净的实例。
"""
from unittest import mock

import fakeredis
from django.core.cache import cache
from rest_framework.test import APITestCase

from blog import session_store


class BaseAPITestCase(APITestCase):
    """所有接口测试的父类：修正 Host、清理限流计数"""

    def setUp(self):
        super().setUp()
        # 见模块 docstring 第 1 条
        self.client.defaults['HTTP_HOST'] = 'localhost'
        # 登录接口挂了 ScopedRateThrottle（login: 5/minute），计数存在 Django 的
        # cache 里，同一进程内跨用例累积。不清掉的话第 6 次登录会莫名收到 429。
        cache.clear()


class RedisIsolatedTestCase(BaseAPITestCase):
    """
    需要走真实登录流程（发 token、查白名单）的用例继承它。

    只替换 _client 不够：SessionStore.__init__ 里执行的是
    `self.redis = client or get_redis_client()`，一旦 _store 已存在，
    它会一直握着**旧**的客户端，patch 就白做了。
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._client_patcher = mock.patch.object(
            session_store,
            '_client',
            fakeredis.FakeStrictRedis(decode_responses=True),
        )
        cls._client_patcher.start()
        cls._store_patcher = mock.patch.object(session_store, '_store', None)
        cls._store_patcher.start()

    @classmethod
    def tearDownClass(cls):
        # 后 start 的先 stop
        cls._store_patcher.stop()
        cls._client_patcher.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        # 每个用例一份干净的会话表，避免「上个用例登出，下个用例莫名 401」
        session_store.get_redis_client().flushdb()
