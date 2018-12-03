from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'playlists/$', views.playlists, name='playlists'),
    url(r'ajax/backup/$', views.backup, name='backup'),
    url(r'ajax/delete/$', views.delete, name='delete'),
    url(r'ajax/restore$', views.restore, name='restore'),
    url(r'ajax/backup_all/$', views.backup_all, name='backup_all'),
    url(r'ajax/setlist/$', views.setlist, name='setlist'),
]
