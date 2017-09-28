from django.contrib import admin

# Register your models here.

from .models import Track, Playlist

admin.site.register(Track)
admin.site.register(Playlist)