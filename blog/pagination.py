from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ArticlePagination(PageNumberPagination):
    """
    文章分页器

    类比 FastAPI：
    class PageParams(BaseModel):
        page: int = 1
        limit: int = 5

    DRF 把"读取分页参数"这件事也自动化了。
    """
    page_size = 5                    # 每页默认条数
    page_query_param = 'page'        # ?page=2
    page_size_query_param = 'limit'  # ?limit=10（客户端可覆盖）
    max_page_size = 50               # 上限，防止 ?limit=999999 拖垮数据库

    def get_paginated_response(self, data):
        """
        自定义分页响应格式

        默认格式：{"count": 15, "next": "...", "previous": null, "results": [...]}
        这里改成和 FastAPI 项目一致的格式，保持前后端约定统一
        """
        return Response({
            'articles': data,
            'articlesCount': self.page.paginator.count,
            'page': self.page.number,
            'totalPages': self.page.paginator.num_pages,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
        })

    