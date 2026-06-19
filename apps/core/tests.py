import base64
import json
from pathlib import Path
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase

from . import admin as core_admin
from . import views
from .feishu import fetch_feishu_document_metadata, parse_feishu_doc_token
from .markdown import render_markdown
from .models import BioProfile, FeishuDocument, FeishuDocumentSetting, MemberProfile, OAuthLookupCode, ShortcutLink


class CoreViewTests(TestCase):
    def test_home_shows_guest_state(self):
        response = self.client.get('/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '未登录')
        self.assertContains(response, '登录')
        self.assertContains(response, '/static/images/logo.png')
        self.assertContains(response, '/favicon.ico')
        self.assertContains(response, '首页')
        self.assertContains(response, '成员')
        self.assertContains(response, 'href="/members/"')
        self.assertContains(response, '文档')
        self.assertContains(response, 'href="/docs/"')
        self.assertContains(response, 'Bio.')
        self.assertContains(response, '快捷链接')
        self.assertContains(response, 'href="/links/"')
        self.assertContains(response, '服务器状态')
        self.assertContains(response, 'https://status.srinternet.top/dashboard')
        self.assertContains(response, 'target="_blank" rel="noopener noreferrer"')
        self.assertContains(response, 'document.startViewTransition')
        self.assertContains(response, '@keyframes sr-theme-reveal')
        self.assertContains(response, 'animateThemeButton')

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

    def test_quick_links_page_shows_active_configured_links(self):
        ShortcutLink.objects.create(
            title='SR Studio',
            url='https://sr-studio.cn/',
            description='团队官网',
            sort_order=2,
        )
        ShortcutLink.objects.create(
            title='内部文档',
            url='/docs/',
            description='内部资料入口',
            sort_order=1,
            open_new_tab=False,
        )
        ShortcutLink.objects.create(
            title='隐藏入口',
            url='https://example.com/hidden',
            is_active=False,
        )

        response = self.client.get('/links/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '团队快捷链接')
        self.assertContains(response, '内部文档')
        self.assertContains(response, 'href="/docs/"')
        self.assertContains(response, 'SR Studio')
        self.assertContains(response, 'href="https://sr-studio.cn/" target="_blank" rel="noopener noreferrer"')
        self.assertNotContains(response, '隐藏入口')
        content = response.content.decode()
        self.assertLess(content.index('内部文档'), content.index('SR Studio'))

    def test_quick_links_page_shows_empty_state(self):
        response = self.client.get('/links/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '暂无快捷链接，请在后台添加。')

    def test_documents_page_shows_configured_feishu_documents(self):
        FeishuDocument.objects.create(
            title='普通文档',
            document_url='https://example.feishu.cn/docx/normal-token',
            description='普通文档简介',
            auto_cover='https://example.com/normal-cover.png',
            sort_order=1,
        )
        FeishuDocument.objects.create(
            title='置顶文档',
            document_url='https://example.feishu.cn/docx/pinned-token',
            description='置顶文档简介',
            manual_cover='https://example.com/manual-cover.png',
            is_pinned=True,
            sort_order=99,
            open_new_tab=False,
        )
        FeishuDocument.objects.create(
            title='隐藏文档',
            document_url='https://example.feishu.cn/docx/hidden-token',
            is_active=False,
        )

        response = self.client.get('/docs/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '团队文档')
        self.assertContains(response, '置顶文档')
        self.assertContains(response, '置顶文档简介')
        self.assertContains(response, '置顶')
        self.assertNotContains(response, '[err]')
        self.assertContains(response, 'border-purple-800 bg-purple-50')
        self.assertContains(response, 'https://example.com/manual-cover.png')
        self.assertContains(response, '普通文档')
        self.assertContains(response, '普通文档简介')
        self.assertContains(response, 'https://example.com/normal-cover.png')
        self.assertContains(response, 'href="https://example.feishu.cn/docx/normal-token" target="_blank" rel="noopener noreferrer"')
        self.assertNotContains(response, '隐藏文档')
        content = response.content.decode()
        self.assertLess(content.index('置顶文档'), content.index('普通文档'))

    def test_documents_page_shows_empty_state(self):
        response = self.client.get('/docs/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '暂无文档，请在后台添加。')

    def test_feishu_guest_metadata_uses_open_graph_fields(self):
        response = Mock()
        response.text = (
            '<html><head>'
            '<meta property="og:title" content="飞书标题 - 飞书云文档">'
            '<meta property="og:description" content="飞书简介">'
            '<meta property="og:image" content="/cover.png">'
            '</head></html>'
        )
        response.raise_for_status.return_value = None

        with patch('apps.core.feishu.requests.get', return_value=response):
            metadata = fetch_feishu_document_metadata('https://example.feishu.cn/docx/doc-token')

        self.assertEqual(metadata['title'], '飞书标题')
        self.assertEqual(metadata['description'], '飞书简介')
        self.assertEqual(metadata['cover'], 'https://example.feishu.cn/cover.png')

    def test_parse_feishu_doc_token_supports_docx_urls(self):
        doc_token, doc_type = parse_feishu_doc_token('https://example.feishu.cn/docx/doc-token?from=from_copylink')

        self.assertEqual(doc_token, 'doc-token')
        self.assertEqual(doc_type, 'docx')

    def test_members_page_shows_bound_and_manual_member_cards(self):
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='member-bound-user',
            nickname='OAuth 成员',
            avatar='https://example.com/oauth-member.png',
            email='oauth-member@example.com',
        )
        MemberProfile.objects.create(
            lookup_code=lookup_code,
            intro='绑定账号简介',
            sort_order=2,
        )
        MemberProfile.objects.create(
            nickname='手动成员',
            avatar='https://example.com/manual-member.png',
            intro='手动成员简介',
            sort_order=1,
        )
        MemberProfile.objects.create(
            nickname='隐藏成员',
            intro='隐藏简介',
            is_active=False,
        )

        response = self.client.get('/members/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '团队成员')
        self.assertContains(response, '手动成员')
        self.assertContains(response, 'https://example.com/manual-member.png')
        self.assertContains(response, '手动成员简介')
        self.assertContains(response, 'OAuth 成员')
        self.assertContains(response, 'https://example.com/oauth-member.png')
        self.assertContains(response, '绑定账号简介')
        self.assertContains(response, lookup_code.identification_code)
        self.assertContains(response, f'href="/bio/{lookup_code.identification_code}/"')
        self.assertNotContains(response, '隐藏成员')
        content = response.content.decode()
        self.assertLess(content.index('手动成员'), content.index('OAuth 成员'))

    def test_members_page_shows_manual_override_for_bound_account(self):
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='member-override-user',
            nickname='OAuth 原昵称',
            avatar='https://example.com/original.png',
        )
        MemberProfile.objects.create(
            lookup_code=lookup_code,
            nickname='覆盖昵称',
            avatar='https://example.com/override.png',
            intro='覆盖信息',
        )

        response = self.client.get('/members/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '覆盖昵称')
        self.assertContains(response, 'https://example.com/override.png')
        self.assertContains(response, '覆盖信息')
        self.assertNotContains(response, 'OAuth 原昵称')
        self.assertNotContains(response, 'https://example.com/original.png')

    def test_members_page_shows_empty_state(self):
        response = self.client.get('/members/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '暂无成员资料，请在后台添加。')

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

    def test_bio_edit_uses_martor_editor(self):
        session = self.client.session
        session[views.OAUTH_USER_SESSION_KEY] = {
            'sub': 'martor-user',
            'nickname': 'Martor User',
            'is_admin': False,
        }
        session.save()

        response = self.client.get('/bio/edit/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'martor/js/martor.tailwind')
        self.assertContains(response, 'plugins/js/ace.js')
        self.assertContains(response, 'data-markdownfy-url="/martor/markdownify/"')
        self.assertContains(response, 'name="markdown"')
        self.assertContains(response, 'core/css/martor.css')
        self.assertContains(response, 'core/js/markdown_tools.js')
        self.assertContains(response, '<main class="flex-1 bg-slate-50 transition-colors dark:bg-slate-950">')
        self.assertNotContains(response, 'plugins/css/tailwind.min.css')
        self.assertNotContains(response, 'plugins/js/tailwind.min.js')
        self.assertNotContains(response, 'bindEditor')

    def test_bio_preview_renders_advanced_markdown(self):
        markdown = (
            '| A | B |\n| --- | --- |\n| 1 | 2 |\n\n'
            '- [x] Done\n\n'
            '$$x^2$$\n\n'
            '/// details | Folded\n    open: true\n\nBody\n///\n\n'
            '/// tab | Python\n```python\nprint(1)\n```\n///\n\n'
            '/// tab | JS\n```javascript\nconsole.log(1)\n```\n///'
        )

        response = self.client.post('/bio/preview/', {'markdown': markdown}, HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('<table>', payload['html'])
        self.assertIn('task-list', payload['html'])
        self.assertIn('arithmatex', payload['html'])
        self.assertIn('<details open>', payload['html'])
        self.assertIn('class="tabbed-set tabbed-alternate"', payload['html'])

        content_response = self.client.post('/bio/preview/', {'content': '> [!NOTE]\n> Content field'}, HTTP_HOST='127.0.0.1')

        self.assertEqual(content_response.status_code, 200)
        self.assertIn('class="admonition note"', content_response.json()['html'])

    def test_martor_markdownify_uses_project_renderer(self):
        markdown = (
            '> [!NOTE]\n> Alert body\n\n'
            '- [x] Done\n\n'
            '$$x^2$$\n\n'
            ':smile:\n\n'
            '/// details | Folded\n    open: true\n\nBody\n///\n\n'
            '/// tab | Python\n```python\nprint(1)\n```\n///\n\n'
            '/// tab | JS\n```javascript\nconsole.log(1)\n```\n///'
        )

        response = self.client.post('/martor/markdownify/', {'content': markdown}, HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="admonition note"')
        self.assertContains(response, 'task-list')
        self.assertContains(response, 'arithmatex')
        self.assertContains(response, '😄')
        self.assertContains(response, '<details open>')
        self.assertContains(response, 'class="tabbed-set tabbed-alternate"')

    def test_markdown_normalizes_triple_single_quote_fences(self):
        html = render_markdown("'''python\nprint(1)\n'''")

        self.assertIn('class="language-python highlight"', html)
        self.assertIn('print', html)
        self.assertNotIn("'''", html)

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
        admin_response = self.client.get('/admin/', HTTP_HOST='127.0.0.1')
        self.assertContains(admin_response, "background-image: url('https://example.com/admin.png');")

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
        self.assertNotContains(response, 'admin/css/srmember_admin.css')
        self.assertNotContains(response, 'sr-admin-brand')
        self.assertContains(response, 'unfold/css/styles.css')
        self.assertContains(response, '/static/images/logo.png')
        self.assertContains(response, 'SRMember 管理后台')
        self.assertContains(response, '注销')

    def test_unfold_admin_settings_are_ready_for_installation(self):
        self.assertEqual(settings.UNFOLD['SITE_TITLE'], 'SRMember 管理后台')
        self.assertEqual(settings.UNFOLD['SITE_HEADER'], 'SR思锐 管理后台')
        self.assertEqual(settings.UNFOLD['SITE_SUBHEADER'], '团队内部成员系统')
        self.assertEqual(settings.UNFOLD['COLORS']['primary']['500'], '124 108 255')
        self.assertTrue(issubclass(core_admin.OAuthLookupCodeAdmin, core_admin.UnfoldModelAdmin))
        if settings.HAS_DJANGO_UNFOLD:
            self.assertLess(
                settings.INSTALLED_APPS.index('unfold'),
                settings.INSTALLED_APPS.index('django.contrib.admin'),
            )

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

    def test_admin_shortcut_link_list_shows_configured_links(self):
        user = get_user_model().objects.create_user(username='admin', password='password', is_staff=True, is_superuser=True)
        ShortcutLink.objects.create(
            title='后台快捷链接',
            url='https://example.com/admin-link',
            description='后台配置说明',
        )
        self.client.force_login(user)

        response = self.client.get('/admin/core/shortcutlink/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '后台快捷链接')
        self.assertContains(response, 'https://example.com/admin-link')

    def test_admin_feishu_document_list_shows_configured_documents(self):
        user = get_user_model().objects.create_user(username='admin', password='password', is_staff=True, is_superuser=True)
        FeishuDocument.objects.create(
            title='后台飞书文档',
            document_url='https://example.feishu.cn/docx/admin-token',
            description='后台文档说明',
            manual_cover='https://example.com/admin-doc-cover.png',
            is_pinned=True,
        )
        self.client.force_login(user)

        response = self.client.get('/admin/core/feishudocument/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '后台飞书文档')
        self.assertContains(response, 'https://example.feishu.cn/docx/admin-token')
        self.assertContains(response, 'https://example.com/admin-doc-cover.png')

    def test_admin_feishu_document_setting_allows_global_credentials(self):
        user = get_user_model().objects.create_user(username='admin', password='password', is_staff=True, is_superuser=True)
        FeishuDocumentSetting.objects.create(app_id='global-app-id', app_key='global-app-key')
        self.client.force_login(user)

        response = self.client.get('/admin/core/feishudocumentsetting/1/change/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'global-app-id')
        self.assertContains(response, 'type="password"')

    def test_admin_member_profile_list_shows_member_cards_data(self):
        user = get_user_model().objects.create_user(username='admin', password='password', is_staff=True, is_superuser=True)
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='admin-member-user',
            nickname='后台绑定成员',
            avatar='https://example.com/admin-member.png',
        )
        MemberProfile.objects.create(lookup_code=lookup_code, intro='后台简介')
        MemberProfile.objects.create(nickname='后台手动成员', avatar='https://example.com/manual-admin.png')
        self.client.force_login(user)

        response = self.client.get('/admin/core/memberprofile/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '后台绑定成员')
        self.assertContains(response, lookup_code.identification_code)
        self.assertContains(response, 'https://example.com/admin-member.png')
        self.assertContains(response, '后台手动成员')
        self.assertContains(response, '手动成员')

    def test_admin_bio_profile_change_form_uses_isolated_martor_editor(self):
        user = get_user_model().objects.create_user(username='admin', password='password', is_staff=True, is_superuser=True)
        lookup_code = OAuthLookupCode.objects.create(
            sr_user_id='admin-editor-user',
            nickname='Admin Editor',
        )
        bio_profile = BioProfile.objects.create(lookup_code=lookup_code, markdown='# Admin Title')
        self.client.force_login(user)

        response = self.client.get(f'/admin/core/bioprofile/{bio_profile.pk}/change/', HTTP_HOST='127.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'martor/js/martor.tailwind')
        self.assertContains(response, 'plugins/js/ace.js')
        self.assertContains(response, 'data-markdownfy-url="/martor/markdownify/"')
        self.assertContains(response, 'name="markdown"')
        self.assertContains(response, 'sr-admin-bio-editor')
        self.assertContains(response, 'core/css/markdown.css')
        self.assertContains(response, 'core/css/martor.css')
        self.assertContains(response, 'core/js/markdown_tools.js')
        self.assertNotContains(response, 'admin/css/bio_admin.css')
        self.assertNotContains(response, 'plugins/css/tailwind.min.css')
        self.assertNotContains(response, 'plugins/js/tailwind.min.js')
        self.assertNotContains(response, 'martor/css/martor-admin.min.css')
        self.assertContains(response, '# Admin Title')
        self.assertNotContains(response, 'bindAdminEditor')
        self.assertNotContains(response, 'sr-admin-markdown-source')
        self.assertNotContains(response, '渲染预览')
        html = response.content.decode()
        self.assertLess(html.index('martor/css/martor.tailwind.min.css'), html.index('core/css/markdown.css'))
        self.assertLess(html.index('core/css/markdown.css'), html.index('core/css/martor.css'))
        self.assertLess(html.index('martor/js/martor.tailwind.min.js'), html.index('core/js/markdown_tools.js'))

    def test_martor_styles_define_light_and_dark_editor_colors(self):
        frontend_css = Path(settings.BASE_DIR / 'static/core/css/martor.css').read_text()
        markdown_css = Path(settings.BASE_DIR / 'static/core/css/markdown.css').read_text()

        self.assertIn('--sr-martor-bg: #ffffff;', frontend_css)
        self.assertNotIn('.dark .sr-bio-editor', frontend_css)
        self.assertIn('--sr-martor-code-bg: #ffffff;', frontend_css)
        self.assertIn('.sr-bio-editor .martor-preview.sr-markdown-shell', frontend_css)
        self.assertIn('.martor-preview.sr-markdown-shell', frontend_css)
        self.assertIn('--sr-martor-active: #7c6cff;', frontend_css)
        self.assertIn('.sr-bio-editor .martor-preview.sr-markdown-body .admonition', frontend_css)
        self.assertIn('.sr-bio-editor .martor-preview.sr-markdown-body details', frontend_css)
        self.assertIn('.sr-bio-editor .ace_editor', frontend_css)
        self.assertIn('--sr-md-code-bg: #0b1020;', markdown_css)
        self.assertIn('.sr-markdown-body .highlight .nx', markdown_css)
