"""
教学版本存档。

这里放的是第 7–10 课逐步演进过程中留下的三套实现，**不参与运行时**：

    views_v1_native.py   原生 Django 视图（JsonResponse），第 7–8 课
    views_v2_apiview.py  DRF APIView + 手写序列化，第 9 课
    views_v3_generic.py  GenericAPIView + Mixin 组合，第 10 课

正式实现是 blog/viewsets.py（ModelViewSet），挂在 /api/v3/ 下。
这些文件的相对导入已改为绝对导入（from blog.xxx import ...），
但路由挂载已从 mysite/urls.py 和 blog/urls_v3.py 移除，
所以 /api/blog/、/api/v2/、/api/v3/generic/ 都不再可访问。
"""
