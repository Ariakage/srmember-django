import hashlib
import string

from django.conf import settings
from django.db import models


class OAuthLookupCode(models.Model):
    CODE_LENGTH = 8
    CODE_LETTERS = string.ascii_uppercase
    CODE_DIGITS = string.digits
    CODE_ALPHABET = CODE_LETTERS + CODE_DIGITS

    identification_code = models.CharField(max_length=8, unique=True, db_index=True, verbose_name='识别码')
    sr_user_id = models.CharField(max_length=128, unique=True, db_index=True, verbose_name='SR 用户 ID')
    nickname = models.CharField(max_length=150, verbose_name='昵称')
    avatar = models.URLField(max_length=500, blank=True, verbose_name='头像')
    email = models.EmailField(blank=True, verbose_name='邮箱')
    is_admin = models.BooleanField(default=False, verbose_name='组织管理员')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = 'OAuth 用户查找码'
        verbose_name_plural = 'OAuth 用户查找码'

    def __str__(self):
        return f'{self.nickname} ({self.identification_code})'

    def save(self, *args, **kwargs):
        if not self.identification_code:
            self.identification_code = self.generate_unique_code(self.sr_user_id)
        super().save(*args, **kwargs)

    @classmethod
    def find_by_code(cls, code):
        return cls.objects.get(identification_code=str(code).upper())

    @classmethod
    def generate_unique_code(cls, sr_user_id):
        for _ in range(100):
            code = cls.generate_code(sr_user_id, salt=_)
            if not cls.objects.exclude(sr_user_id=sr_user_id).filter(identification_code=code).exists():
                return code
        raise RuntimeError('Unable to generate a unique OAuth lookup code')

    @classmethod
    def generate_code(cls, sr_user_id, salt=0):
        digest = hashlib.sha256(f'{sr_user_id}:{salt}'.encode('utf-8')).digest()
        number = int.from_bytes(digest, 'big')
        chars = []
        for _ in range(cls.CODE_LENGTH):
            number, index = divmod(number, len(cls.CODE_ALPHABET))
            chars.append(cls.CODE_ALPHABET[index])
        if not any(char in cls.CODE_LETTERS for char in chars):
            chars[0] = cls.CODE_LETTERS[digest[0] % len(cls.CODE_LETTERS)]
        if not any(char in cls.CODE_DIGITS for char in chars):
            chars[-1] = cls.CODE_DIGITS[digest[1] % len(cls.CODE_DIGITS)]
        return ''.join(chars)


class BioProfile(models.Model):
    lookup_code = models.OneToOneField(
        OAuthLookupCode,
        on_delete=models.CASCADE,
        related_name='bio_profile',
        verbose_name='识别码',
    )
    sr_user_id = models.CharField(max_length=128, unique=True, db_index=True, verbose_name='SR 用户 ID')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='关联后台用户',
    )
    markdown = models.TextField(blank=True, verbose_name='Bio Markdown')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '用户 Bio'
        verbose_name_plural = '用户 Bio'

    def __str__(self):
        return f'{self.lookup_code.nickname} Bio'

    def save(self, *args, **kwargs):
        self.sr_user_id = self.lookup_code.sr_user_id
        super().save(*args, **kwargs)


class ShortcutLink(models.Model):
    title = models.CharField(max_length=80, verbose_name='标题')
    url = models.CharField(max_length=500, verbose_name='链接')
    description = models.CharField(max_length=180, blank=True, verbose_name='说明')
    is_pinned = models.BooleanField(default=False, verbose_name='置顶')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    open_new_tab = models.BooleanField(default=True, verbose_name='新窗口打开')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        ordering = ('-is_pinned', 'sort_order', 'title')
        verbose_name = '快捷链接'
        verbose_name_plural = '快捷链接'

    def __str__(self):
        return self.title


class FeishuDocumentSetting(models.Model):
    app_id = models.CharField(max_length=120, blank=True, verbose_name='全局飞书 App ID')
    app_key = models.CharField(max_length=240, blank=True, verbose_name='全局飞书 App Key')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '飞书文档配置'
        verbose_name_plural = '飞书文档配置'

    def __str__(self):
        return '飞书文档配置'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting


class FeishuDocument(models.Model):
    title = models.CharField(max_length=120, blank=True, verbose_name='标题')
    document_url = models.URLField(max_length=800, verbose_name='飞书文档链接')
    description = models.CharField(max_length=240, blank=True, verbose_name='简介')
    manual_cover = models.URLField(max_length=800, blank=True, verbose_name='手动头图')
    auto_cover = models.URLField(max_length=800, blank=True, verbose_name='自动头图')
    app_id = models.CharField(max_length=120, blank=True, verbose_name='单独飞书 App ID')
    app_key = models.CharField(max_length=240, blank=True, verbose_name='单独飞书 App Key')
    is_pinned = models.BooleanField(default=False, verbose_name='置顶')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    open_new_tab = models.BooleanField(default=True, verbose_name='新窗口打开')
    last_synced_at = models.DateTimeField(null=True, blank=True, verbose_name='最近同步时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        ordering = ('-is_pinned', 'sort_order', 'title')
        verbose_name = '飞书文档'
        verbose_name_plural = '飞书文档'

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return self.title or self.document_url

    @property
    def cover_url(self):
        return self.manual_cover or self.auto_cover

    def get_credentials(self):
        if self.app_id and self.app_key:
            return self.app_id, self.app_key
        setting = FeishuDocumentSetting.load()
        if setting.app_id and setting.app_key:
            return setting.app_id, setting.app_key
        return '', ''


class MemberProfile(models.Model):
    lookup_code = models.OneToOneField(
        OAuthLookupCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='member_profile',
        verbose_name='绑定 OAuth 账号',
    )
    nickname = models.CharField(max_length=150, blank=True, verbose_name='手动昵称')
    avatar = models.URLField(max_length=500, blank=True, verbose_name='手动头像')
    intro = models.TextField(blank=True, verbose_name='简介')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        ordering = ('sort_order', 'nickname', 'id')
        verbose_name = '成员资料'
        verbose_name_plural = '成员资料'

    def __str__(self):
        return self.display_nickname

    @property
    def display_nickname(self):
        return self.nickname or (self.lookup_code.nickname if self.lookup_code_id else '') or '未命名成员'

    @property
    def display_avatar(self):
        return self.avatar or (self.lookup_code.avatar if self.lookup_code_id else '')

    @property
    def display_sr_user_id(self):
        return self.lookup_code.sr_user_id if self.lookup_code_id else ''

    @property
    def display_lookup_code(self):
        return self.lookup_code.identification_code if self.lookup_code_id else ''


class SiteSetting(models.Model):
    site_name = models.CharField(
        max_length=80,
        default='SR思锐',
        verbose_name='网站名称',
    )
    nav_logo_url = models.CharField(
        max_length=500,
        default='/static/images/logo.png',
        verbose_name='导航 Logo 地址',
    )
    nav_link_url = models.CharField(
        max_length=500,
        default='/',
        verbose_name='导航跳转地址',
    )
    support_email = models.EmailField(
        default='support@sr-studio.cn',
        verbose_name='支持邮箱',
    )
    sr_user_id_label = models.CharField(
        max_length=60,
        default='SR 用户 ID',
        verbose_name='SR 用户 ID 字样',
    )
    home_dashboard_description = models.CharField(
        max_length=180,
        default='集中管理团队成员、快捷链接与协作资料。',
        verbose_name='首页 Dashboard 说明',
    )
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

    @property
    def nav_link_is_external(self):
        return self.nav_link_url.startswith(('http://', 'https://'))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting
