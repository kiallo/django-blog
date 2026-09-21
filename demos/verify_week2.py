"""
第二周验收脚本 —— 对应第12课的 10 条验收标准

运行：python demos/verify_week2.py

⚠️ 运行前请**重启一次 runserver**：限流计数器存在服务进程的内存里（LocMemCache），
   脚本清不掉它。不重启的话，前面几条登录可能直接撞 429 导致假失败。
⚠️ 会往数据库和 Redis 写测试数据，跑完自动清理。
⚠️ 第 10 条是限流测试（放最后），跑完这一分钟内别再用同一 IP 登录。
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth.models import User                     # noqa: E402
from django.test.utils import setup_test_environment            # noqa: E402
from rest_framework.test import APIClient                       # noqa: E402

from blog.session_store import get_session_store, get_redis_client  # noqa: E402

setup_test_environment()

BASE = "/api/v3"
PASSWORD = "verify123456"
AUTHOR = "verify_author"
OTHER = "verify_other"
STAFF = "verify_staff"
TMP = "verify_tmp"          # 注册检查用的临时账号

passed = []
failed = []


def _encodable(text):
    """
    当前 stdout 能否表示这些字符

    真实 Windows 控制台走 WriteConsoleW，encoding 是 utf-8，emoji 没问题；
    但输出被重定向到文件/管道时会退回 GBK，打印 ✅/❌ 直接抛 UnicodeEncodeError。
    """
    try:
        text.encode(sys.stdout.encoding or "utf-8")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


OK_MARK, FAIL_MARK = ("✅", "❌") if _encodable("✅❌") else ("[OK]", "[FAIL]")
PARTY = "🎉" if _encodable("🎉") else "**"


def check(no, desc, condition, detail=""):
    mark = OK_MARK if condition else FAIL_MARK
    (passed if condition else failed).append(no)
    print(f"  {mark} 【{no}】{desc}")
    if detail:
        print(f"       {detail}")


def login(client, username, password=PASSWORD):
    response = client.post(f"{BASE}/auth/login/",
                           {"username": username, "password": password},
                           format="json")
    return response


def main():
    print("=" * 70)
    print(" 第二周验收 —— Django 博客 API（第13课）")
    print("=" * 70)

    store = get_session_store()
    redis_client = get_redis_client()

    # ---------- 准备三个账号 ----------
    print("\n[准备] 创建测试账号：作者 / 他人 / 管理员")
    # ⚠️ TMP 也要在这里清掉：它是第 1 条注册检查创建的，而删除动作在最后的 cleanup 里。
    #    上次跑到一半崩掉的话 cleanup 不会执行，残留的账号会让这次的注册撞
    #    "该用户名已被注册"（400），第 1 条就成了假失败。
    User.objects.filter(username=TMP).delete()
    store.revoke_session(TMP)

    for name, is_staff in ((AUTHOR, False), (OTHER, False), (STAFF, True)):
        User.objects.filter(username=name).delete()
        store.revoke_session(name)
        User.objects.create_user(username=name, password=PASSWORD, is_staff=is_staff)
    print("       已创建并重置")

    author_client = APIClient()
    other_client = APIClient()

    # ---------- 1. 注册 → 登录 ----------
    print("\n[1] 注册 → 登录")
    register = author_client.post(f"{BASE}/auth/register/", {
        "username": TMP, "password": PASSWORD, "password2": PASSWORD,
    }, format="json")
    registered = register.status_code == 201
    login_resp = login(author_client, AUTHOR)
    logged_in = login_resp.status_code == 200
    check(1, "注册 201 + 登录返回 access/refresh",
          registered and logged_in,
          f"注册={register.status_code} 登录={login_resp.status_code}")

    access = login_resp.json()["access"]
    author_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    other_login = login(other_client, OTHER)
    other_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {other_login.json()['access']}"
    )

    # ---------- 2. 创建文章 ----------
    print("\n[2] 带 token 创建文章")
    created = author_client.post(f"{BASE}/articles/", {
        "title": "验收测试文章",
        "description": "由 verify_week2.py 创建",
        "body": "正文内容",
        "tag_list": ["验收"],
    }, format="json")
    body = created.json()
    has_envelope = "article" in body
    article = body.get("article", body)
    check(2, "创建返回 201 且带 slug（响应有 article 外壳）",
          created.status_code == 201 and bool(article.get("slug")),
          f"状态={created.status_code} 外壳={'有' if has_envelope else '无'} slug={article.get('slug')}")

    slug = article["slug"]

    # ---------- 3. 匿名列表 ----------
    print("\n[3] 匿名 GET 文章列表")
    anon = APIClient()
    listing = anon.get(f"{BASE}/articles/")
    ldata = listing.json()
    check(3, "200 且分页字段齐全",
          listing.status_code == 200 and "articlesCount" in ldata and "page" in ldata,
          f"状态={listing.status_code} 字段={list(ldata.keys())}")

    # ---------- 4. 匿名 POST → 401 ----------
    print("\n[4] 匿名 POST 文章")
    anon_post = anon.post(f"{BASE}/articles/", {"title": "x", "body": "y"}, format="json")
    check(4, "返回 401（不是 403）", anon_post.status_code == 401,
          f"状态={anon_post.status_code}")

    # ---------- 5. 他人改 → 403 ----------
    print("\n[5] 用别人的账号改这篇文章")
    other_put = other_client.patch(f"{BASE}/articles/{slug}/",
                                   {"title": "别人改的标题"}, format="json")
    check(5, "返回 403", other_put.status_code == 403,
          f"状态={other_put.status_code}")

    # ---------- 6. 管理员改 → 200 ----------
    print("\n[6] 管理员（is_staff）改这篇文章")
    staff_client = APIClient()
    staff_login = login(staff_client, STAFF)
    staff_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {staff_login.json()['access']}"
    )
    staff_put = staff_client.patch(f"{BASE}/articles/{slug}/",
                                   {"description": "管理员改的摘要"}, format="json")
    check(6, "返回 200（is_staff 后门生效）", staff_put.status_code == 200,
          f"状态={staff_put.status_code}")

    # ---------- 7. 评论 ----------
    print("\n[7] 评论：创建 / 他人评论 / 匿名 / 作者改 / 他人改")
    c_create = author_client.post(f"{BASE}/articles/{slug}/comments/",
                                  {"body": "验收评论"}, format="json")
    comment_id = c_create.json().get("comment", {}).get("id")

    # ★ 这条是 3.5 节那个 bug 的回归测试：
    #   other 用户给别人（author）的文章评论，必须是 201 而不是 403
    c_other_create = other_client.post(f"{BASE}/articles/{slug}/comments/",
                                       {"body": "我来评论别人的文章"}, format="json")

    c_anon = anon.post(f"{BASE}/articles/{slug}/comments/",
                       {"body": "匿名评论"}, format="json")
    c_update = author_client.patch(f"{BASE}/comments/{comment_id}/",
                                   {"body": "改过的评论"}, format="json")
    c_other = other_client.patch(f"{BASE}/comments/{comment_id}/",
                                 {"body": "别人改评论"}, format="json")
    ok = (c_create.status_code == 201 and c_other_create.status_code == 201
          and c_anon.status_code == 401
          and c_update.status_code == 200 and c_other.status_code == 403)
    check(7, "作者创建 201 / 他人评论 201 / 匿名 401 / 作者改 200 / 他人改 403", ok,
          f"作者创建={c_create.status_code} 他人评论={c_other_create.status_code} "
          f"匿名={c_anon.status_code} 作者改={c_update.status_code} "
          f"他人改={c_other.status_code}")

    # ---------- 8. 收藏 ----------
    print("\n[8] 收藏文章")
    fav = author_client.post(f"{BASE}/articles/{slug}/favorite/", {}, format="json")
    fav_data = fav.json().get("article", {})
    check(8, "favorites_count 变成 1，favorited=True",
          fav.status_code == 200
          and fav_data.get("favorites_count") == 1
          and fav_data.get("favorited") is True,
          f"状态={fav.status_code} count={fav_data.get('favorites_count')} "
          f"favorited={fav_data.get('favorited')}")

    # ---------- 9. 登出 ----------
    print("\n[9] 登出后同一个 access 立刻失效")
    before = author_client.get(f"{BASE}/auth/me/")
    author_client.post(f"{BASE}/auth/logout/", {}, format="json")
    after = author_client.get(f"{BASE}/auth/me/")
    check(9, "登出前 200，登出后 401",
          before.status_code == 200 and after.status_code == 401,
          f"登出前={before.status_code} 登出后={after.status_code}")

    # ---------- 10. 限流（必须放最后，会锁住登录接口一分钟） ----------
    print("\n[10] 用错误密码反复登录，直到触发限流")
    # 不用固定次数，而是"一直打直到出现 429"——
    # 因为前面几条检查已经消耗了一部分配额，固定次数会误报
    codes = []
    for _ in range(30):
        code = login(APIClient(), AUTHOR, "wrong_password").status_code
        codes.append(code)
        if code == 429:
            break
    check(10, "触发了 429 限流", codes[-1] == 429,
          f"第 {len(codes)} 次触发，状态序列={codes}")

    # ---------- 清理 ----------
    print("\n[清理] 删除测试账号与 Redis 会话")
    for name in (AUTHOR, OTHER, STAFF, TMP):
        User.objects.filter(username=name).delete()
        store.revoke_session(name)
    print(f"       Redis 残留: {redis_client.keys('django:*')}")

    # ---------- 汇总 ----------
    print("\n" + "=" * 70)
    total = len(passed) + len(failed)
    print(f" 结果：{len(passed)}/{total} 通过")
    if failed:
        print(f" ❌ 未通过：{failed}")
    else:
        print(f" {PARTY} 全部通过 —— 第二周的知识已经串成一条完整的流水线了")
    print("=" * 70)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()