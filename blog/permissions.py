from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    对象级权限：所有人可读，只有作者本人可改可删

    类比 FastAPI：
    async def get_article_for_edit(
        article: Article = Depends(get_article),
        user: User = Depends(get_current_user),
    ):
        if article.author_id != user.id:
            raise HTTPException(403, "只有作者可以修改")
        return article

    DRF 把这种检查抽象成了 has_object_permission。
    """
    message = "只有作者本人可以修改或删除这篇文章"

    def has_object_permission(self, request, view, obj):
        # SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS') —— 只读请求直接放行
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class IsAuthorOrAdminOrReadOnly(permissions.BasePermission):
    """
    读放行；写操作要求：作者本人 或 管理员

    和 IsAuthorOrReadOnly 的区别：给 is_staff 开了后门。
    实际项目里后台管理员经常需要下架违规内容。
    """
    message = "只有作者本人或管理员可以修改/删除"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # ⚠️ is_staff 不会自动放行任何权限类，必须自己写这个判断
        if request.user.is_staff:
            return True
        return obj.author == request.user


class IsCommentAuthorOrReadOnly(permissions.BasePermission):
    """评论：只有评论作者能改删"""
    message = "只有评论作者本人可以修改/删除这条评论"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class ReadOnly(permissions.BasePermission):
    """只读权限：任何写操作都拒绝"""
    message = "该接口只读"

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS