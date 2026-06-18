from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('favicon.ico', views.favicon, name='favicon'),
    path('oauth/login/', views.oauth_login, name='oauth_login'),
    path('oauth/callback/', views.oauth_callback, name='oauth_callback'),
    path('oauth/logout/', views.oauth_logout, name='oauth_logout'),
    path('', views.home, name='home'),
]
