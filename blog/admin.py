from django.contrib import admin
from .models import Article, Comment, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """标签管理"""
    list_display = ['name', 'id']
    search_fields = ['name']


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """文章管理"""
    list_display = ['title', 'author', 'created_at', 'updated_at']
    list_filter = ['created_at', 'author', 'tags']
    search_fields = ['title', 'body']
    prepopulated_fields = {'slug': ('title',)}  # 根据标题自动生成 slug
    filter_horizontal = ['tags']  # 多对多选择器（更好用的 UI）


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """评论管理"""
    list_display = ['body', 'author', 'article', 'created_at']
    list_filter = ['created_at', 'author']
    search_fields = ['body']