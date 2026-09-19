# demos/demo_drf_auth.py
"""
第11课演示：认证 + 权限 + Redis 白名单全流程

这个脚本会真的跑一遍：
  注册 → 登录 → 带 token 访问 → 建文章 → 登出 → 验证 token 已失效

运行：python demos/demo_drf_auth.py
"""
import json
import os
import sys

import django

# 把项目根目录加入模块搜索路径，保证在 demos/ 下也能 import mysite / blog
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows 控制台默认 GBK，编码不了 ⚠️ 这类符号，强制 UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

import jwt                                                        # noqa: E402
from django.contrib.auth.models import User                       # noqa: E402
from django.test.utils import setup_test_environment              # noqa: E402
from rest_framework.test import APIClient                         # noqa: E402

from blog.session_store import get_session_store, get_redis_client  # noqa: E402

setup_test_environment()

DEMO_USER = "demo_auth_user"
DEMO_PASS = "demo123456"
BASE = "/api/v3"


def line(char="─", n=68):
    print(char * n)


def title(text):
    print()
    print("╔" + "═" * 66 + "╗")
    print("║" + f" {text}".ljust(60) + "║")
    print("╚" + "═" * 66 + "╝")


def show_theory():
    title("认证 vs 权限")
    print("""
认证 Authentication：你是谁？  → 失败 401 Unauthorized
权限 Permission    ：你能干啥？→ 失败 403 Forbidden

DRF 的执行链：
  Request
    ↓ ① authentication_classes 逐个尝试 authenticate()
      → (user, auth) 认证成功 / None 换下一个 / AuthenticationFailed 立即 401
    ↓ ② permission_classes 的 has_permission()（AND 关系，全过才放行）
    ↓ ③ get_object() 时再查 has_object_permission()
    ↓ ④ 视图逻辑

⚠️ 第一个认证器的 authenticate_header() 决定 401 还是 403：
   JWTAuthentication（返回 Bearer realm）→ 401 ✅
   SessionAuthentication（返回 None）    → 403
""")


def step(n, text):
    print(f"\n【{n}】{text}")
    line()


def main():
    datastore = get_session_store()
    client = APIClient()

    show_theory()

    # ---------- 0. 准备用户 ----------
    step(0, f"准备测试账号 {DEMO_USER}")
    if User.objects.filter(username=DEMO_USER).exists():
        User.objects.filter(username=DEMO_USER).delete()
        print(f"  清理旧的 {DEMO_USER}")

    response = client.post(f"{BASE}/auth/register/", {
        "username": DEMO_USER,
        "email": f"{DEMO_USER}@example.com",
        "password": DEMO_PASS,
        "password2": DEMO_PASS,
    }, format="json")
    print(f"  POST /auth/register/  → {response.status_code}")
    print(f"  {json.dumps(response.json(), ensure_ascii=False)}")

    # ---------- 1. 登录 ----------
    step(1, "登录，拿 access + refresh")
    response = client.post(f"{BASE}/auth/login/", {
        "username": DEMO_USER,
        "password": DEMO_PASS,
    }, format="json")
    print(f"  POST /auth/login/     → {response.status_code}")
    data = response.json()
    access, refresh = data["access"], data["refresh"]

    # 解码 JWT 看 payload（不验签，只为展示）
    payload = jwt.decode(access, options={"verify_signature": False})
    print(f"  access  payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    print(f"  ⚠️ 注意 sid 是我们自己加的 claim，username 也是")

    # ---------- 2. 看 Redis 白名单 ----------
    step(2, "Redis 白名单里存了什么")
    redis_client = get_redis_client()
    key = f"{datastore.SESSION_PREFIX}{DEMO_USER}"
    print(f"  keys 'django:*'  → {redis_client.keys('django:*')}")
    print(f"  GET  {key}")
    print(f"       {redis_client.get(key)}")
    print(f"  TTL  {key}  → {redis_client.ttl(key)} 秒")
    print(f"  SMEMBERS {datastore.ONLINE_USERS_KEY} → {redis_client.smembers(datastore.ONLINE_USERS_KEY)}")

    # ---------- 3. 公开接口 vs 受保护接口 ----------
    step(3, "公开读 vs 需要认证")
    r1 = client.get(f"{BASE}/articles/")
    print(f"  GET  /articles/  （无 token）→ {r1.status_code}  （只读放行）")

    r2 = client.get(f"{BASE}/auth/me/")
    print(f"  GET  /auth/me/   （无 token）→ {r2.status_code}  {r2.json()}")

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    r3 = client.get(f"{BASE}/auth/me/")
    print(f"  GET  /auth/me/   （带 token）→ {r3.status_code}  {r3.json()}")

    r4 = client.get(f"{BASE}/auth/my-session/")
    print(f"  GET  /auth/my-session/       → {r4.status_code}  {r4.json()}")

    # ---------- 4. 写操作：作者自动绑定 ----------
    step(4, "创建文章：无 token 被拒，带 token 自动绑定作者")
    client.credentials()                       # 清掉 Header
    r_bad = client.post(f"{BASE}/articles/", {
        "title": "不该被创建",
        "body": "应该被拒绝",
    }, format="json")
    print(f"  POST /articles/  （无 token）→ {r_bad.status_code}  {r_bad.json()}")

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    r_ok = client.post(f"{BASE}/articles/", {
        "title": "认证演示文章",
        "description": "由 demo_drf_auth.py 创建",
        "body": "正文内容",
        "tag_list": ["认证", "演示"],
    }, format="json")
    print(f"  POST /articles/  （带 token）→ {r_ok.status_code}")

    article = r_ok.json()
    slug = article["slug"]
    print(f"  创建成功: slug={slug}  author={article['author']}")
    print(f"  ⚠️ author 由 perform_create 注入，请求体里根本没传")

    # ---------- 5. 登出 ----------
    step(5, "登出（只删 Redis 会话，JWT 本身还活着）")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    # 登出前先确认 token 还能用
    before = client.get(f"{BASE}/auth/me/")
    print(f"  登出前 GET /auth/me/ → {before.status_code}")

    logout = client.post(f"{BASE}/auth/logout/", {}, format="json")
    print(f"  POST /auth/logout/   → {logout.status_code}  {logout.json()}")
    print(f"  Redis 里还有会话吗？ {redis_client.get(key)}")

    after = client.get(f"{BASE}/auth/me/")
    print(f"  登出后 GET /auth/me/ → {after.status_code}  {after.json()}")
    print(f"  ⚠️ 同一个 access token，签名依然有效、exp 还没到，但白名单没了 → 401")

    # refresh 也应该失效
    r6 = APIClient().post(f"{BASE}/auth/refresh/", {"refresh": refresh}, format="json")
    print(f"  POST /auth/refresh/  → {r6.status_code}  {r6.json()}")

    # ---------- 6. 清理 ----------
    step(6, "清理演示数据")
    User.objects.filter(username=DEMO_USER).delete()
    print(f"  已删除用户 {DEMO_USER}（其文章会级联删除）")
    print(f"  Redis 残留: {redis_client.keys('django:*')}")

    title("本课结论")
    print("""
1. JWT 无状态 → 登出无解  →  Redis 白名单补上这一环
2. 白名单存 sid（不是 token 原文）→ refresh 不受影响，泄漏也无风险
3. 认证类负责"你是谁"，权限类负责"你能干啥"，职责别混
4. 权限类里 is_staff 不会自动放行，管理员后门要自己写
5. 登录接口必须单独限流，否则可以被无限次撞库
""")


if __name__ == "__main__":
    main()
