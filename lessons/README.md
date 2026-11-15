# lessons — 教学版本存档

这里存放第 7–10 课逐步演进过程中留下的三套旧实现，**不参与线上运行**，
也不会出现在 `/api/docs/` 的接口文档或 `/api/v3/` 的可浏览 API 首页里。

## 目录

| 文件 | 原位置 | 对应课程 | 技术形态 |
|---|---|---|---|
| `views_v1_native.py` | `blog/views.py` | 第 7–8 课 | 原生 Django 视图 + `JsonResponse`，手写 JSON |
| `urls_v1_native.py` | `blog/urls.py` | 第 7–8 课 | 原 `/api/blog/` 的路由 |
| `views_v2_apiview.py` | `blog/views_drf.py` | 第 9 课 | DRF `APIView`，手写序列化与响应 |
| `urls_v2_apiview.py` | `blog/urls_drf.py` | 第 9 课 | 原 `/api/v2/` 的路由 |
| `views_v3_generic.py` | `blog/views_generic.py` | 第 10 课 | `GenericAPIView` + Mixin 组合，原 `/api/v3/generic/` |

正式实现是 `blog/viewsets.py`（`ModelViewSet`），挂在 `/api/v3/` 下。

## 为什么移出来

1. **接口文档干净**：此前 `/api/docs/` 里混着 v1 / v2 / generic 三套重复接口，
   而且 drf-spectacular 对裸 `APIView` 推断不出序列化器，每次生成都会刷一串
   `unable to guess serializer` 警告。移走后文档只剩 v3 一套。
2. **可浏览 API 首页干净**：`/api/v3/` 的根页面不再出现 `generic/` 这一项。
3. **主目录职责单一**：`blog/` 只留正式实现和基础设施，读代码时不会被教学版本干扰。

## 还能跑吗

文件本身是完整可运行的，导入已改成绝对路径（`from blog.models import ...`），
`blog/` 里的 `models`、`serializers`、`permissions`、`pagination` 也都还在。

如果想临时复活某个版本做对比，在 `mysite/urls.py` 的 `urlpatterns` 里加回一行即可：

```python
path('api/legacy/', include('lessons.urls_v1_native')),
```

不需要改 `lessons/` 下任何文件的导入。
