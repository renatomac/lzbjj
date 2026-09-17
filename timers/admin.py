from django.contrib import admin
from .models import SpotifyAccount


@admin.register(SpotifyAccount)
class SpotifyAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'spotify_user_id', 'expires_at', 'updated_at')
    readonly_fields = ('access_token', 'refresh_token', 'expires_at', 'created_at', 'updated_at')
    search_fields = ('user__username', 'display_name', 'spotify_user_id')
