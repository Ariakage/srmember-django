from django.shortcuts import render

from .models import SiteSetting


def home(request):
    nav_items = [
        {'label': '首页', 'url': '/', 'active': True},
        {'label': '成员', 'url': '#', 'active': False},
        {'label': '公告', 'url': '#', 'active': False},
        {'label': '文档', 'url': '#', 'active': False},
    ]
    return render(
        request,
        'core/home.html',
        {
            'nav_items': nav_items,
            'site_setting': SiteSetting.load(),
        },
    )
