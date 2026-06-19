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
