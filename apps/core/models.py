from django.db import models


class SiteSetting(models.Model):
    footer_copyright = models.CharField(
        max_length=120,
        default='© 2026 Ariakage 保留所有权利.',
        verbose_name='页脚版权文案',
    )
    footer_record_text = models.CharField(
        max_length=120,
        default='湘ICP备2025108132号-2',
        verbose_name='备案文案',
    )
    footer_record_url = models.URLField(
        default='https://beian.miit.gov.cn/',
        verbose_name='备案链接',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '站点设置'
        verbose_name_plural = '站点设置'

    def __str__(self):
        return '站点设置'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting
