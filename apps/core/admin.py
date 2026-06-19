import requests

from django import forms
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .feishu import fetch_feishu_document_metadata
from .forms import BioProfileAdminForm
from .models import BioProfile, FeishuDocument, FeishuDocumentSetting, MemberProfile, OAuthLookupCode, ShortcutLink, SiteSetting


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
    form = BioProfileAdminForm
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

    class Media:
        css = {'all': ('core/css/markdown.css', 'admin/css/bio_admin.css')}
        js = (
            'core/js/mathjax_config.js',
            'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js',
            'core/js/markdown_tools.js',
        )

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


@admin.register(ShortcutLink)
class ShortcutLinkAdmin(admin.ModelAdmin):
    list_display = ('title', 'url', 'sort_order', 'is_active', 'open_new_tab', 'updated_at')
    list_editable = ('sort_order', 'is_active', 'open_new_tab')
    list_filter = ('is_active', 'open_new_tab', 'created_at', 'updated_at')
    search_fields = ('title', 'url', 'description')
    fields = ('title', 'url', 'description', 'sort_order', 'is_active', 'open_new_tab')
    ordering = ('sort_order', 'title')


@admin.register(FeishuDocumentSetting)
class FeishuDocumentSettingAdmin(admin.ModelAdmin):
    fields = ('app_id', 'app_key')
    list_display = ('app_id', 'updated_at')

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'app_key':
            kwargs['widget'] = forms.PasswordInput(render_value=True)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return not FeishuDocumentSetting.objects.exists()


@admin.register(FeishuDocument)
class FeishuDocumentAdmin(admin.ModelAdmin):
    list_display = ('cover_preview', 'display_name', 'document_url', 'is_pinned', 'sort_order', 'is_active', 'updated_at')
    list_editable = ('is_pinned', 'sort_order', 'is_active')
    list_filter = ('is_active', 'is_pinned', 'open_new_tab', 'created_at', 'updated_at')
    search_fields = ('title', 'document_url', 'description')
    readonly_fields = ('cover_preview_large', 'auto_cover', 'last_synced_at')
    fields = (
        'cover_preview_large',
        'title',
        'document_url',
        'description',
        'manual_cover',
        'auto_cover',
        'app_id',
        'app_key',
        'is_pinned',
        'sort_order',
        'is_active',
        'open_new_tab',
        'last_synced_at',
    )
    ordering = ('-is_pinned', 'sort_order', 'title')
    actions = ('refresh_metadata',)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'app_key':
            kwargs['widget'] = forms.PasswordInput(render_value=True)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        refresh_feishu_document(obj)
        super().save_model(request, obj, form, change)

    @admin.action(description='刷新飞书元数据')
    def refresh_metadata(self, request, queryset):
        updated_count = 0
        for document in queryset:
            if refresh_feishu_document(document):
                document.save(update_fields=('title', 'description', 'auto_cover', 'last_synced_at', 'updated_at'))
                updated_count += 1
        self.message_user(request, f'已刷新 {updated_count} 个飞书文档。')

    @admin.display(description='头图')
    def cover_preview(self, obj):
        if not obj.cover_url:
            return '-'
        return format_html('<img src="{}" alt="{}" style="width:64px;height:36px;border-radius:8px;object-fit:cover;">', obj.cover_url, obj.display_title)

    @admin.display(description='头图')
    def cover_preview_large(self, obj):
        if not obj or not obj.cover_url:
            return '-'
        return format_html('<img src="{}" alt="{}" style="width:180px;height:102px;border-radius:12px;object-fit:cover;">', obj.cover_url, obj.display_title)

    @admin.display(description='标题', ordering='title')
    def display_name(self, obj):
        return obj.display_title


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ('avatar_preview', 'display_name', 'oauth_account', 'sort_order', 'is_active', 'updated_at')
    list_editable = ('sort_order', 'is_active')
    list_filter = ('is_active', 'created_at', 'updated_at')
    list_select_related = ('lookup_code',)
    search_fields = (
        'nickname',
        'intro',
        'lookup_code__identification_code',
        'lookup_code__sr_user_id',
        'lookup_code__nickname',
        'lookup_code__email',
    )
    autocomplete_fields = ('lookup_code',)
    fields = ('avatar_preview_large', 'lookup_code', 'nickname', 'avatar', 'intro', 'sort_order', 'is_active')
    readonly_fields = ('avatar_preview_large',)
    ordering = ('sort_order', 'nickname', 'id')

    @admin.display(description='头像')
    def avatar_preview(self, obj):
        avatar = obj.display_avatar
        if not avatar:
            return '-'
        return format_html('<img src="{}" alt="{}" style="width:36px;height:36px;border-radius:12px;object-fit:cover;">', avatar, obj.display_nickname)

    @admin.display(description='头像')
    def avatar_preview_large(self, obj):
        if not obj:
            return '-'
        avatar = obj.display_avatar
        if not avatar:
            return '-'
        return format_html('<img src="{}" alt="{}" style="width:72px;height:72px;border-radius:16px;object-fit:cover;">', avatar, obj.display_nickname)

    @admin.display(description='昵称', ordering='nickname')
    def display_name(self, obj):
        return obj.display_nickname

    @admin.display(description='绑定账号', ordering='lookup_code__identification_code')
    def oauth_account(self, obj):
        if not obj.lookup_code_id:
            return '手动成员'
        return f'{obj.lookup_code.nickname} ({obj.lookup_code.identification_code})'


def refresh_feishu_document(document):
    app_id, app_key = document.get_credentials()
    try:
        metadata = fetch_feishu_document_metadata(document.document_url, app_id=app_id, app_key=app_key)
    except (requests.RequestException, ValueError, KeyError):
        return False

    changed = False
    if not document.title and metadata.get('title'):
        document.title = metadata['title'][:120]
        changed = True
    if not document.description and metadata.get('description'):
        document.description = metadata['description'][:240]
        changed = True
    if metadata.get('cover') and document.auto_cover != metadata['cover']:
        document.auto_cover = metadata['cover']
        changed = True
    if changed:
        document.last_synced_at = timezone.now()
    return changed
