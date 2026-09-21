from rest_framework.response import Response


def envelope(key, data, status_code=None):
    """
    统一响应外壳

    约定（第12课定下的契约）：
        单个资源 → {"article": {...}} / {"comment": {...}} / {"user": {...}}
        列表     → {"articles": [...], "articlesCount": n, ...}（由分页器负责，不用这个函数）

    为什么要抽成函数：
        create / retrieve / update / favorite ... 都要包一层，
        写第 3 遍的时候就该抽出来了。

    status_code 传 None 时 Response 会用默认的 200
    （看 Response.__init__ 源码：`if status is not None: self.status_code = status`）
    """
    return Response({key: data}, status=status_code)