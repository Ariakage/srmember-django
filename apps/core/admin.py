from django.contrib import admin

from .models import SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    fields = ('footer_copyright', 'footer_record_text', 'footer_record_url')
    list_display = ('footer_copyright', 'footer_record_text', 'updated_at')

    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()
