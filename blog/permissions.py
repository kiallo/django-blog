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


    