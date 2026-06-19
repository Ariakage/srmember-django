from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('favicon.ico', views.favicon, name='favicon'),
    path('members/', views.members, name='members'),
    path('links/', views.quick_links, name='quick_links'),
    path('docs/', views.documents, name='documents'),
    path('bio/help/', views.bio_help, name='bio_help'),
    path('bio/preview/', views.bio_preview, name='bio_preview'),
    path('bio/edit/', views.bio_edit, name='bio_edit'),
    path('bio/', views.bio, name='bio'),
    path('bio/<str:identifier>/', views.bio, name='bio_detail'),
    path('oauth/login/', views.oauth_login, name='oauth_login'),
    path('oauth/callback/', views.oauth_callback, name='oauth_callback'),
    path('oauth/logout/', views.oauth_logout, name='oauth_logout'),
    path('', views.home, name='home'),
]
