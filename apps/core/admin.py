from django import forms
from django.contrib import admin
from django.db import models
from django.utils.html import format_html

from .models import BioProfile, OAuthLookupCode, SiteSetting


@admin.register(OAuthLookupCode)
class OAuthLookupCodeAdmin(admin.ModelAdmin):
    list_display = ('avatar_preview', 'identification_code', 'nickname', 'sr_user_id', 'email', 'is_admin', 'updated_at')
    list_filter = ('is_admin', 'created_at', 'updated_at')
    search_fields = ('identification_code', 'sr_user_id', 'nickname', 'email')
    readonly_fields = (
        'avatar_preview_large',
        'identification_code',
        'sr_user_id',
        'nickname',
        'avatar',
        'email',
        'is_admin',
        'created_at',
        'updated_at',
    )
    fields = (
        'avatar_preview_large',
        'identification_code',
        'sr_user_id',
        'nickname',
        'avatar',
        'email',
        'is_admin',
        'created_at',
        'updated_at',
    )
    ordering = ('-updated_at',)

    @admin.display(description='头像')
    def avatar_preview(self, obj):
        if not obj.avatar:
            return '-'
        return format_html('<img src="{}" alt="{}" style="width:36px;height:36px;border-radius:999px;object-fit:cover;">', obj.avatar, obj.nickname)

    @admin.display(description='头像')
    def avatar_preview_large(self, obj):
        if not obj.avatar:
            return '-'
        return format_html('<img src="{}" alt="{}" style="width:72px;height:72px;border-radius:999px;object-fit:cover;">', obj.avatar, obj.nickname)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    fields = ('footer_copyright', 'footer_record_text', 'footer_record_url')
    list_display = ('footer_copyright', 'footer_record_text', 'updated_at')

    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()


@admin.register(BioProfile)
class BioProfileAdmin(admin.ModelAdmin):
    change_form_template = 'admin/core/bioprofile/change_form.html'
    list_display = ('avatar_preview', 'nickname', 'identification_code', 'sr_user_id', 'updated_at')
    list_select_related = ('lookup_code', 'user')
    search_fields = ('lookup_code__identification_code', 'lookup_code__nickname', 'lookup_code__email', 'sr_user_id')
    autocomplete_fields = ('lookup_code', 'user')
    readonly_fields = ('avatar_preview_large', 'sr_user_id', 'created_at', 'updated_at')
    fields = (
        'avatar_preview_large',
        'lookup_code',
        'sr_user_id',
        'user',
        'markdown',
        'created_at',
        'updated_at',
    )
    ordering = ('-updated_at',)
    formfield_overrides = {
        models.TextField: {
            'widget': forms.Textarea(
                attrs={
                    'class': 'vLargeTextField sr-admin-markdown-source',
                    'rows': 24,
                },
            ),
        },
    }

    @admin.display(description='头像')
    def avatar_preview(self, obj):
        if not obj or not obj.lookup_code.avatar:
            return '-'
        return format_html('<img src="{}" alt="{}" style="width:36px;height:36px;border-radius:999px;object-fit:cover;">', obj.lookup_code.avatar, obj.lookup_code.nickname)

    @admin.display(description='头像')
    def avatar_preview_large(self, obj):
        if not obj or not obj.lookup_code.avatar:
            return '-'
        return format_html('<img src="{}" alt="{}" style="width:72px;height:72px;border-radius:999px;object-fit:cover;">', obj.lookup_code.avatar, obj.lookup_code.nickname)

    @admin.display(description='昵称', ordering='lookup_code__nickname')
    def nickname(self, obj):
        return obj.lookup_code.nickname

    @admin.display(description='识别码', ordering='lookup_code__identification_code')
    def identification_code(self, obj):
        return obj.lookup_code.identification_code
