import base64
import hashlib
import json
from collections.abc import Mapping
from json import JSONDecodeError
from urllib.parse import urlencode, urlsplit

import requests
from authlib.integrations.base_client import OAuthError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import SiteSetting
from .oauth import oauth


OAUTH_USER_SESSION_KEY = 'oauth_user'
OAUTH_NEXT_SESSION_KEY = 'oauth_next_url'
OAUTH_ADMIN_USERNAME_PREFIX = 'sr_oauth_'
ACCESS_TOKEN_KEYS = ('access_token', 'accessToken', 'token', 'access')
ACCESS_TOKEN_CONTAINER_KEYS = ('data', 'result', 'payload')
USERINFO_KEYS = (
    'sub',
    'id',
    'displayName',
    'nickname',
    'name',
    'preferred_username',
    'email',
    'picture',
    'avatar',
    'permanentAvatar',
    'isorganizationadmin',
    'isAdmin',
)


def home(request):
    nav_items = [
        {'label': '首页', 'url': '/', 'active': True},
        {'label': '成员', 'url': '#', 'active': False},
        {'label': '公告', 'url': '#', 'active': False},
        {'label': '文档', 'url': '#', 'active': False},
    ]
    return render(
        request,
        'core/home.html',
        {
            'nav_items': nav_items,
            'oauth_user': request.session.get(OAUTH_USER_SESSION_KEY),
            'site_setting': SiteSetting.load(),
        },
    )


def favicon(request):
    favicon_path = settings.BASE_DIR / 'static' / 'images' / 'favicon.ico'
    return FileResponse(favicon_path.open('rb'), content_type='image/x-icon')


def oauth_login(request):
    next_url = get_safe_redirect_url(request, request.GET.get('next'))
    if next_url:
        request.session[OAUTH_NEXT_SESSION_KEY] = next_url
    else:
        request.session.pop(OAUTH_NEXT_SESSION_KEY, None)
    redirect_uri = request.build_absolute_uri(reverse('core:oauth_callback'))
    return oauth.sr_united.authorize_redirect(request, redirect_uri)


def oauth_callback(request):
    token = fetch_oauth_access_token(request)
    userinfo = resolve_oauth_userinfo(token)
    print_oauth_payload('oauth resolved userinfo payload', userinfo)
    normalized_user = normalize_oauth_user(userinfo)
    redirect_url = get_oauth_callback_redirect_url(request, normalized_user)
    django_logout(request)
    request.session[OAUTH_USER_SESSION_KEY] = normalized_user
    if normalized_user['is_admin']:
        login_oauth_admin_user(request, normalized_user)
    return redirect(redirect_url)


def oauth_logout(request):
    django_logout(request)
    return redirect('core:home')


def admin_oauth_login(request):
    next_url = get_safe_redirect_url(request, request.GET.get('next')) or reverse('admin:index')
    if request.user.is_authenticated and request.user.is_staff:
        return redirect(next_url)
    return redirect(f"{reverse('core:oauth_login')}?{urlencode({'next': next_url})}")


def fetch_oauth_access_token(request):
    if request.method == 'GET':
        error = request.GET.get('error')
        if error:
            description = request.GET.get('error_description')
            raise OAuthError(error=error, description=description)
        params = {
            'code': request.GET.get('code'),
            'state': request.GET.get('state'),
        }
    else:
        params = {
            'code': request.POST.get('code'),
            'state': request.POST.get('state'),
        }

    client = oauth.sr_united
    state_data = client.framework.get_state_data(request.session, params.get('state'))
    client.framework.clear_state_data(request.session, params.get('state'))
    params = client._format_state_params(state_data, params)
    return client.fetch_access_token(**params)


def normalize_oauth_user(userinfo):
    payloads = list(iter_userinfo_payloads(userinfo))
    nickname = (
        first_oauth_value(payloads, ('id',))
        or first_oauth_value(payloads, ('nickname', 'name', 'displayName', 'preferred_username', 'email', 'sub'))
        or 'SR 用户'
    )
    avatar = (
        first_oauth_value(payloads, ('picture',))
        or first_oauth_value(payloads, ('avatar', 'permanentAvatar', 'avatar_url', 'headimgurl'))
    )
    return {
        'sub': first_oauth_value(payloads, ('sub', 'id')),
        'nickname': nickname,
        'avatar': avatar,
        'email': first_oauth_value(payloads, ('email',)),
        'is_admin': first_oauth_bool(payloads, ('isorganizationadmin', 'isAdmin')),
    }


def login_oauth_admin_user(request, oauth_user):
    User = get_user_model()
    username = build_oauth_admin_username(oauth_user)
    user, created = User.objects.get_or_create(username=username)
    if created:
        user.set_unusable_password()
    user.email = oauth_user.get('email', '')
    user.first_name = oauth_user.get('nickname', '')[:150]
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.save()
    django_login(request, user, backend='django.contrib.auth.backends.ModelBackend')


def build_oauth_admin_username(oauth_user):
    identifier = oauth_user.get('sub') or oauth_user.get('email') or oauth_user.get('nickname') or 'unknown'
    digest = hashlib.sha256(identifier.encode('utf-8')).hexdigest()[:32]
    return f'{OAUTH_ADMIN_USERNAME_PREFIX}{digest}'


def get_oauth_callback_redirect_url(request, oauth_user):
    next_url = get_safe_redirect_url(request, request.session.pop(OAUTH_NEXT_SESSION_KEY, ''))
    if next_url and (oauth_user['is_admin'] or not is_admin_redirect_url(next_url)):
        return next_url
    return reverse('core:home')


def get_safe_redirect_url(request, url):
    if not url:
        return ''
    if url_has_allowed_host_and_scheme(
        url=url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return ''


def is_admin_redirect_url(url):
    return urlsplit(url).path.startswith(reverse('admin:index'))


def resolve_oauth_userinfo(token):
    access_token = find_access_token(token)
    if access_token:
        try:
            userinfo = fetch_userinfo(access_token)
        except requests.RequestException:
            userinfo = None
        if contains_userinfo_payload(userinfo):
            return userinfo

    embedded_userinfo = find_embedded_userinfo(token)
    if embedded_userinfo:
        return embedded_userinfo

    id_token = find_token_value(token, ('id_token', 'idToken'))
    if id_token:
        return decode_jwt_payload(id_token)

    return token


def find_embedded_userinfo(token):
    for payload in iter_token_payloads(token):
        for key in ('userinfo', 'user_info', 'user', 'profile'):
            value = payload.get(key)
            if contains_userinfo_payload(value):
                return value
        data = payload.get('data')
        if contains_userinfo_payload(data):
            return data
    return None


def is_userinfo_payload(payload):
    if any(key in payload for key in (*ACCESS_TOKEN_KEYS, 'id_token', 'idToken')):
        return False
    return any(key in payload for key in USERINFO_KEYS)


def contains_userinfo_payload(payload):
    return any(is_userinfo_payload(value) for value in iter_nested_mappings(payload))


def iter_userinfo_payloads(payload):
    yield from iter_nested_mappings(payload)


def first_oauth_value(payloads, keys):
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            value = str(value).strip()
            if value:
                return value
    return ''


def first_oauth_bool(payloads, keys):
    for payload in payloads:
        for key in keys:
            if key not in payload:
                continue
            value = payload[key]
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                return value != 0
            value = str(value).strip().lower()
            if value in {'1', 'true', 'yes', 'y', 'on'}:
                return True
            if value in {'0', 'false', 'no', 'n', 'off', ''}:
                return False
    return False


def find_access_token(token):
    access_token = find_token_value(token, ACCESS_TOKEN_KEYS)
    if access_token:
        return access_token

    for payload in iter_token_payloads(token):
        if not has_access_token_marker(payload):
            continue
        for key in ACCESS_TOKEN_CONTAINER_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return clean_token_value(value)
    return ''


def find_token_value(token, keys):
    for payload in iter_token_payloads(token):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return clean_token_value(value)
            if isinstance(value, Mapping):
                nested_value = find_token_value(value, keys + ('value',))
                if nested_value:
                    return nested_value
    return ''


def iter_token_payloads(token):
    yield from iter_nested_mappings(token)


def iter_nested_mappings(value):
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from iter_nested_mappings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_nested_mappings(item)
    elif isinstance(value, str):
        parsed_value = parse_json_value(value)
        if parsed_value is not None:
            yield from iter_nested_mappings(parsed_value)


def parse_json_value(value):
    value = value.strip()
    if not value or value[0] not in '[{':
        return None
    try:
        return json.loads(value)
    except JSONDecodeError:
        return None


def has_access_token_marker(payload):
    token_type = str(payload.get('token_type') or payload.get('tokenType') or '').lower()
    if 'access' in token_type and 'token' in token_type:
        return True
    return any(key in payload for key in ACCESS_TOKEN_KEYS)


def clean_token_value(value):
    value = value.strip().strip('"')
    if value.lower().startswith('bearer '):
        return value[7:].strip()
    return value


def fetch_userinfo(access_token):
    metadata = oauth.sr_united.load_server_metadata()
    response = requests.get(
        metadata['userinfo_endpoint'],
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    print_oauth_payload('oauth userinfo response payload', payload)
    if isinstance(payload, Mapping) and isinstance(payload.get('data'), Mapping):
        return payload['data']
    return payload


def decode_jwt_payload(token):
    payload = token.split('.')[1]
    payload += '=' * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def print_oauth_payload(label, payload):
    print(f'\n[{label}]')
    print(json.dumps(mask_oauth_payload(payload), ensure_ascii=False, indent=2, default=str))


def mask_oauth_payload(value):
    if isinstance(value, Mapping):
        return {
            key: mask_oauth_value(key, item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_oauth_payload(item) for item in value]
    if isinstance(value, tuple):
        return [mask_oauth_payload(item) for item in value]
    return value


def mask_oauth_value(key, value):
    if key in {'access_token', 'accessToken', 'refresh_token', 'refreshToken', 'id_token', 'idToken', 'token'}:
        return f'<redacted:{len(str(value))} chars>'
    return mask_oauth_payload(value)
