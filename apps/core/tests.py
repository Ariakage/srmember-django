import base64
import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase

from . import views
from .markdown import render_markdown
from .models import BioProfile, OAuthLookupCode


class CoreViewTests(TestCase):
    def test_home_shows_guest_state(self):
        response = self.client.get('/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '未登录')
        self.assertContains(response, '登录')
        self.assertContains(response, '/static/images/logo.png')
        self.assertContains(response, '/favicon.ico')

    def test_home_shows_logged_in_user(self):
        session = self.client.session
        session[views.OAUTH_USER_SESSION_KEY] = {
            'sub': 'user-1',
            'nickname': 'Ariakage',
            'avatar': 'https://example.com/avatar.png',
            'email': 'ariakage@example.com',
        }
        session.save()

        response = self.client.get('/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '已登录')
        self.assertContains(response, 'Ariakage')
        self.assertContains(response, 'https://example.com/avatar.png')
        self.assertContains(response, 'href="/bio/"')

    def test_favicon_route(self):
        response = self.client.get('/favicon.ico', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'image/x-icon')

    def test_oauth_login_uses_callback_redirect_uri(self):
        captured = {}

        def authorize_redirect(request, redirect_uri):
            captured['redirect_uri'] = redirect_uri
            return HttpResponse('ok')

        with patch.object(views.oauth.sr_united, 'authorize_redirect', authorize_redirect):
            response = self.client.get('/oauth/login/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured['redirect_uri'], 'http://127.0.0.1/oauth/callback/')

    def test_oauth_client_posts_client_credentials_to_token_endpoint(self):
        self.assertEqual(
            views.oauth.sr_united.client_kwargs['token_endpoint_auth_method'],
            'client_secret_post',
        )

    def test_fetch_oauth_access_token_skips_id_token_jwks_validation(self):
        request = Mock(
            method='GET',
            GET={'code': 'code-1', 'state': 'state-1'},
            session={},
        )
        token = {
            'access_token': 'token-1',
            'id_token': 'bad-id-token',
        }
        client = views.oauth.sr_united

        with (
            patch.object(
                client.framework,
                'get_state_data',
                return_value={
                    'redirect_uri': 'http://127.0.0.1/oauth/callback/',
                    'nonce': 'nonce-1',
                },
            ),
            patch.object(client.framework, 'clear_state_data'),
            patch.object(client, 'fetch_access_token', return_value=token) as fetch_access_token,
            patch.object(client, 'parse_id_token', side_effect=AssertionError('JWKS should not be fetched')),
        ):
            result = views.fetch_oauth_access_token(request)

        self.assertEqual(result, token)
        fetch_access_token.assert_called_once_with(
            code='code-1',
            state='state-1',
            redirect_uri='http://127.0.0.1/oauth/callback/',
        )

    def test_oauth_callback_stores_normalized_user(self):
        token = {
            'userinfo': {
                'sub': 'user-1',
                'nickname': 'SR Member',
                'picture': 'https://example.com/avatar.png',
                'email': 'member@example.com',
            },
        }

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertEqual(oauth_user['nickname'], 'SR Member')
        self.assertEqual(oauth_user['avatar'], 'https://example.com/avatar.png')

    def test_oauth_callback_supports_nested_access_token(self):
        token = {
            'data': {
                'access_token': 'token-1',
                'token_type': 'access_token',
            },
        }
        response = Mock()
        response.json.return_value = {
            'data': {
                'id': 'user-1',
                'displayName': 'SR User',
                'picture': 'https://example.com/avatar.png',
            },
        }
        response.raise_for_status.return_value = None

        with (
            patch.object(views, 'fetch_oauth_access_token', return_value=token),
            patch.object(views.oauth.sr_united, 'load_server_metadata', return_value={'userinfo_endpoint': 'https://example.com/userinfo'}),
            patch('apps.core.views.requests.get', return_value=response) as get,
        ):
            callback_response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(callback_response.status_code, 302)
        get.assert_called_once_with(
            'https://example.com/userinfo',
            headers={'Authorization': 'Bearer token-1'},
            timeout=10,
        )
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertEqual(oauth_user['nickname'], 'user-1')
        self.assertEqual(oauth_user['avatar'], 'https://example.com/avatar.png')

    def test_oauth_callback_prefers_userinfo_endpoint_over_sparse_embedded_userinfo(self):
        token = {
            'access_token': 'token-1',
            'userinfo': {
                'iss': 'https://united.sr-studio.cn',
                'aud': 'client-id',
            },
        }
        response = Mock()
        response.json.return_value = {'id': 'endpoint-user-id', 'picture': 'https://example.com/endpoint.png'}
        response.raise_for_status.return_value = None

        with (
            patch.object(views, 'fetch_oauth_access_token', return_value=token),
            patch.object(views.oauth.sr_united, 'load_server_metadata', return_value={'userinfo_endpoint': 'https://example.com/userinfo'}),
            patch('apps.core.views.requests.get', return_value=response),
        ):
            callback_response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(callback_response.status_code, 302)
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertEqual(oauth_user['nickname'], 'endpoint-user-id')
        self.assertEqual(oauth_user['avatar'], 'https://example.com/endpoint.png')

    def test_oauth_callback_uses_picture_and_id_fields(self):
        token = {
            'userinfo': {
                'id': 'ariakage',
                'picture': 'https://example.com/avatar.png',
            },
        }

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertEqual(oauth_user['sub'], 'ariakage')
        self.assertEqual(oauth_user['nickname'], 'ariakage')
        self.assertEqual(oauth_user['avatar'], 'https://example.com/avatar.png')

    def test_oauth_callback_creates_lookup_code_for_user(self):
        token = {
            'userinfo': {
                'id': 'member-code-user',
                'picture': 'https://example.com/code.png',
                'email': 'code@example.com',
            },
        }

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        lookup_code = OAuthLookupCode.objects.get(sr_user_id='member-code-user')
        expected_code = OAuthLookupCode.generate_code('member-code-user')
        self.assertEqual(len(lookup_code.identification_code), 8)
        self.assertEqual(lookup_code.identification_code, expected_code)
        self.assertTrue(lookup_code.identification_code.isalnum())
        self.assertEqual(lookup_code.nickname, 'member-code-user')
        self.assertEqual(lookup_code.avatar, 'https://example.com/code.png')
        self.assertEqual(lookup_code.email, 'code@example.com')
        self.assertNotIn('lookup_code', self.client.session[views.OAUTH_USER_SESSION_KEY])
        self.assertNotIn('identification_code', self.client.session[views.OAUTH_USER_SESSION_KEY])

    def test_oauth_lookup_code_is_derived_from_sub(self):
        first_code = OAuthLookupCode.generate_code('derived-user')
        second_code = OAuthLookupCode.generate_code('derived-user')
        other_code = OAuthLookupCode.generate_code('other-derived-user')

        self.assertEqual(first_code, second_code)
        self.assertNotEqual(first_code, other_code)
        self.assertEqual(len(first_code), 8)
        self.assertTrue(first_code.isalnum())
        self.assertEqual(first_code, first_code.upper())

    def test_oauth_callback_reuses_lookup_code_for_same_user(self):
        token = {
            'userinfo': {
                'id': 'stable-user',
                'picture': 'https://example.com/first.png',
            },
        }

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        lookup_code = OAuthLookupCode.objects.get(sr_user_id='stable-user')
        original_code = lookup_code.identification_code
        token['userinfo']['picture'] = 'https://example.com/second.png'

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        lookup_code.refresh_from_db()
        self.assertEqual(lookup_code.identification_code, original_code)
        self.assertEqual(lookup_code.avatar, 'https://example.com/second.png')
        self.assertEqual(OAuthLookupCode.objects.filter(sr_user_id='stable-user').count(), 1)

    def test_oauth_lookup_code_can_be_found_by_code(self):
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='lookup-user',
            nickname='Lookup User',
            avatar='https://example.com/lookup.png',
        )

        found_lookup_code = OAuthLookupCode.find_by_code(lookup_code.identification_code.lower())

        self.assertEqual(found_lookup_code, lookup_code)

    def test_bio_redirects_guest_to_oauth_login(self):
        response = self.client.get('/bio/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/oauth/login/?next=%2Fbio%2F')

    def test_bio_shows_current_user_and_generates_lookup_code(self):
        session = self.client.session
        session[views.OAUTH_USER_SESSION_KEY] = {
            'sub': 'current-bio-user',
            'nickname': 'Bio User',
            'avatar': 'https://example.com/bio.png',
            'email': 'bio@example.com',
            'is_admin': False,
        }
        session.save()

        response = self.client.get('/bio/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        lookup_code = OAuthLookupCode.objects.get(sr_user_id='current-bio-user')
        self.assertTrue(BioProfile.objects.filter(lookup_code=lookup_code, sr_user_id='current-bio-user').exists())
        self.assertContains(response, 'Bio User')
        self.assertContains(response, 'current-bio-user')
        self.assertContains(response, 'https://example.com/bio.png')
        self.assertContains(response, lookup_code.identification_code)
        self.assertContains(response, '编辑 Bio')

    def test_bio_can_be_viewed_by_lookup_code(self):
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='lookup-bio-user',
            nickname='Lookup Bio',
            avatar='https://example.com/lookup-bio.png',
            email='lookup-bio@example.com',
        )

        response = self.client.get(f'/bio/{lookup_code.identification_code.lower()}/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lookup Bio')
        self.assertContains(response, 'lookup-bio-user')
        self.assertContains(response, lookup_code.identification_code)

    def test_bio_can_be_viewed_by_sub_and_generates_missing_lookup_code(self):
        response = self.client.get('/bio/direct-sub-user/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        lookup_code = OAuthLookupCode.objects.get(sr_user_id='direct-sub-user')
        self.assertContains(response, 'direct-sub-user')
        self.assertContains(response, lookup_code.identification_code)

    def test_bio_does_not_show_edit_button_for_other_user(self):
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='someone-else',
            nickname='Someone Else',
        )
        session = self.client.session
        session[views.OAUTH_USER_SESSION_KEY] = {
            'sub': 'viewer-user',
            'nickname': 'Viewer',
            'is_admin': False,
        }
        session.save()

        response = self.client.get(f'/bio/{lookup_code.identification_code}/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '编辑 Bio')

    def test_bio_edit_redirects_guest_to_oauth_login(self):
        response = self.client.get('/bio/edit/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/oauth/login/?next=%2Fbio%2Fedit%2F')

    def test_bio_edit_saves_markdown_profile(self):
        session = self.client.session
        session[views.OAUTH_USER_SESSION_KEY] = {
            'sub': 'markdown-user',
            'nickname': 'Markdown User',
            'avatar': 'https://example.com/markdown.png',
            'email': 'markdown@example.com',
            'is_admin': False,
        }
        session.save()

        markdown = '# Hello Bio\n\n- [x] Done\n\n> [!NOTE]\n> Alert body\n\nInline $x^2$ and :smile:'
        response = self.client.post('/bio/edit/', {'markdown': markdown}, HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/bio/')
        lookup_code = OAuthLookupCode.objects.get(sr_user_id='markdown-user')
        bio_profile = BioProfile.objects.get(lookup_code=lookup_code)
        self.assertEqual(bio_profile.sr_user_id, 'markdown-user')
        self.assertEqual(bio_profile.markdown, markdown)

        response = self.client.get('/bio/', HTTP_HOST='127.0.0.1')

        self.assertContains(response, '<h1 id="hello-bio">Hello Bio</h1>', html=True)
        self.assertContains(response, 'class="admonition note"')
        self.assertContains(response, 'class="arithmatex"')
        self.assertContains(response, '😄')

    def test_bio_preview_renders_advanced_markdown(self):
        markdown = '| A | B |\n| --- | --- |\n| 1 | 2 |\n\n- [x] Done\n\n$$x^2$$'

        response = self.client.post('/bio/preview/', {'markdown': markdown}, HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('<table>', payload['html'])
        self.assertIn('task-list', payload['html'])
        self.assertIn('arithmatex', payload['html'])

    def test_markdown_github_alerts_ignore_fenced_code_examples(self):
        html = render_markdown('> [!NOTE]\n> Alert body\n\n```markdown\n> [!NOTE]\n> Literal body\n```')

        self.assertIn('class="admonition note"', html)
        self.assertIn('[!NOTE]', html)
        self.assertIn('Literal body', html)
        self.assertNotIn('!!! note "Note"', html)

    def test_bio_help_page_shows_markdown_examples(self):
        response = self.client.get('/bio/help/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/bio/help')
        for extension_name in (
            'SuperFences',
            'Highlight',
            'InlineHilite',
            'Arithmatex',
            'Emoji',
            'Tasklist',
            'ProgressBar',
            'MagicLink',
            'BetterEm',
            'Caret',
            'Mark',
            'Tilde',
            'SmartSymbols',
            'Critic',
            'Blocks',
            'Keys',
            'Extra',
            'FancyLists',
            'SaneHeaders',
            'B64',
        ):
            self.assertContains(response, extension_name)
        self.assertContains(response, 'Markdown 源码')
        self.assertContains(response, 'class="admonition note"')
        self.assertContains(response, 'class="progress')
        self.assertContains(response, 'class="tabbed-set tabbed-alternate"')
        self.assertContains(response, 'data:image/svg+xml;base64')
        self.assertContains(response, 'class="critic')
        self.assertContains(response, 'class="keys"')

    def test_oauth_callback_logs_is_admin_user_into_django_admin(self):
        session = self.client.session
        session[views.OAUTH_NEXT_SESSION_KEY] = '/admin/'
        session.save()
        token = {
            'userinfo': {
                'id': 'admin-user',
                'picture': 'https://example.com/admin.png',
                'email': 'admin@example.com',
                'isorganizationadmin': True,
            },
        }

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/admin/')
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertTrue(oauth_user['is_admin'])
        admin_user = get_user_model().objects.get(pk=self.client.session['_auth_user_id'])
        self.assertEqual(admin_user.email, 'admin@example.com')
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertFalse(admin_user.has_usable_password())

    def test_oauth_callback_blocks_non_admin_user_from_admin_next_url(self):
        session = self.client.session
        session[views.OAUTH_NEXT_SESSION_KEY] = '/admin/'
        session.save()
        token = {
            'userinfo': {
                'id': 'member-user',
                'picture': 'https://example.com/member.png',
                'isorganizationadmin': False,
            },
        }

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertFalse(oauth_user['is_admin'])
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_oauth_callback_accepts_string_is_admin_value(self):
        token = {
            'userinfo': {
                'id': 'admin-string-user',
                'isorganizationadmin': 'true',
            },
        }

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertTrue(oauth_user['is_admin'])
        self.assertIn('_auth_user_id', self.client.session)

    def test_oauth_callback_uses_nested_picture_and_id_fields(self):
        token = {
            'userinfo': {
                'data': {
                    'id': 'nested-user',
                    'picture': 'https://example.com/nested.png',
                },
            },
        }

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertEqual(oauth_user['sub'], 'nested-user')
        self.assertEqual(oauth_user['nickname'], 'nested-user')
        self.assertEqual(oauth_user['avatar'], 'https://example.com/nested.png')

    def test_token_data_with_access_token_is_not_userinfo(self):
        token = {
            'data': {
                'id': 'token-row-id',
                'access_token': 'token-1',
            },
        }
        response = Mock()
        response.json.return_value = {'data': {'id': 'real-user-id', 'picture': 'https://example.com/avatar.png'}}
        response.raise_for_status.return_value = None

        with (
            patch.object(views, 'fetch_oauth_access_token', return_value=token),
            patch.object(views.oauth.sr_united, 'load_server_metadata', return_value={'userinfo_endpoint': 'https://example.com/userinfo'}),
            patch('apps.core.views.requests.get', return_value=response),
        ):
            callback_response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(callback_response.status_code, 302)
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertEqual(oauth_user['nickname'], 'real-user-id')
        self.assertEqual(oauth_user['avatar'], 'https://example.com/avatar.png')

    def test_oauth_callback_supports_token_string_in_data(self):
        token = {
            'token_type': 'access_token',
            'data': 'token-1',
        }
        response = Mock()
        response.json.return_value = {'data': [{'id': 'list-user-id', 'picture': 'https://example.com/list.png'}]}
        response.raise_for_status.return_value = None

        with (
            patch.object(views, 'fetch_oauth_access_token', return_value=token),
            patch.object(views.oauth.sr_united, 'load_server_metadata', return_value={'userinfo_endpoint': 'https://example.com/userinfo'}),
            patch('apps.core.views.requests.get', return_value=response),
        ):
            callback_response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(callback_response.status_code, 302)
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertEqual(oauth_user['nickname'], 'list-user-id')
        self.assertEqual(oauth_user['avatar'], 'https://example.com/list.png')

    def test_oauth_callback_supports_deep_userinfo_payloads(self):
        token = {
            'userinfo': {
                'payload': json.dumps(
                    {
                        'member': {
                            'id': 'json-user-id',
                            'picture': 'https://example.com/json.png',
                        },
                    }
                ),
            },
        }

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertEqual(oauth_user['nickname'], 'json-user-id')
        self.assertEqual(oauth_user['avatar'], 'https://example.com/json.png')

    def test_oauth_callback_can_fallback_to_id_token_claims(self):
        payload = {'sub': 'user-1', 'displayName': 'ID Token User', 'permanentAvatar': 'https://example.com/id.png'}
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        token = {'id_token': f'header.{body}.signature'}

        with patch.object(views, 'fetch_oauth_access_token', return_value=token):
            response = self.client.get('/oauth/callback/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        oauth_user = self.client.session[views.OAUTH_USER_SESSION_KEY]
        self.assertEqual(oauth_user['nickname'], 'ID Token User')
        self.assertEqual(oauth_user['avatar'], 'https://example.com/id.png')

    def test_oauth_logout_clears_user(self):
        user = get_user_model().objects.create_user(username='staff', password='password', is_staff=True)
        self.client.force_login(user)
        session = self.client.session
        session[views.OAUTH_USER_SESSION_KEY] = {'nickname': 'Ariakage'}
        session.save()

        response = self.client.get('/oauth/logout/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(views.OAUTH_USER_SESSION_KEY, self.client.session)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_admin_login_redirects_to_oauth_login(self):
        response = self.client.get('/admin/login/?next=/admin/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/oauth/login/?next=%2Fadmin%2F')

    def test_admin_login_redirects_staff_user_to_admin(self):
        user = get_user_model().objects.create_user(username='staff', password='password', is_staff=True)
        self.client.force_login(user)

        response = self.client.get('/admin/login/?next=/admin/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/admin/')

    def test_admin_index_uses_srmember_branding(self):
        user = get_user_model().objects.create_user(username='staff', password='password', is_staff=True)
        self.client.force_login(user)

        response = self.client.get('/admin/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin/css/srmember_admin.css')
        self.assertContains(response, '/static/images/logo.png')
        self.assertContains(response, 'SR思锐 管理后台')
        self.assertContains(response, '最近动作')
        self.assertContains(response, '注销')

    def test_admin_oauth_lookup_code_list_shows_code_avatar_and_nickname(self):
        user = get_user_model().objects.create_user(username='admin', password='password', is_staff=True, is_superuser=True)
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='admin-list-user',
            nickname='后台用户',
            avatar='https://example.com/admin-list.png',
            email='admin-list@example.com',
        )
        self.client.force_login(user)

        response = self.client.get('/admin/core/oauthlookupcode/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, lookup_code.identification_code)
        self.assertContains(response, '后台用户')
        self.assertContains(response, 'https://example.com/admin-list.png')

    def test_admin_bio_profile_list_shows_avatar_nickname_and_code(self):
        user = get_user_model().objects.create_user(username='admin', password='password', is_staff=True, is_superuser=True)
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='admin-bio-user',
            nickname='Bio 后台用户',
            avatar='https://example.com/admin-bio.png',
            email='admin-bio@example.com',
        )
        BioProfile.objects.create(lookup_code=lookup_code, markdown='# Admin Bio')
        self.client.force_login(user)

        response = self.client.get('/admin/core/bioprofile/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, lookup_code.identification_code)
        self.assertContains(response, 'Bio 后台用户')
        self.assertContains(response, 'https://example.com/admin-bio.png')

    def test_admin_bio_profile_change_form_has_markdown_modes(self):
        user = get_user_model().objects.create_user(username='admin', password='password', is_staff=True, is_superuser=True)
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='admin-editor-user',
            nickname='Admin Editor',
        )
        bio_profile = BioProfile.objects.create(lookup_code=lookup_code, markdown='# Admin Title')
        self.client.force_login(user)

        response = self.client.get(f'/admin/core/bioprofile/{bio_profile.pk}/change/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bindAdminEditor')
        self.assertContains(response, '/bio/preview/')
        self.assertContains(response, 'core/js/markdown_tools.js')
        self.assertContains(response, 'admin/css/bio_admin.css')
        self.assertContains(response, 'sr-admin-markdown-source')
        self.assertContains(response, '# Admin Title')
        self.assertNotContains(response, '渲染预览')
