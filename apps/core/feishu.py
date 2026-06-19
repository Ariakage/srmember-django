from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests


FEISHU_OPEN_API_BASE = 'https://open.feishu.cn/open-apis'
LARK_OPEN_API_BASE = 'https://open.larksuite.com/open-apis'
FEISHU_DOC_TYPES = {'doc', 'docx', 'sheet', 'bitable', 'base', 'mindnotes', 'file', 'slides', 'wiki'}


class PageMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.title = ''
        self._reading_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title':
            self._reading_title = True
            return
        if tag != 'meta':
            return

        key = attrs.get('property') or attrs.get('name')
        content = attrs.get('content')
        if key and content:
            self.meta[key.lower()] = content.strip()

    def handle_endtag(self, tag):
        if tag == 'title':
            self._reading_title = False

    def handle_data(self, data):
        if self._reading_title:
            self.title += data.strip()


def fetch_feishu_document_metadata(document_url, app_id='', app_key='', timeout=8):
    api_metadata = {}
    if app_id and app_key:
        try:
            api_metadata = fetch_feishu_drive_metadata(document_url, app_id, app_key, timeout=timeout)
        except (requests.RequestException, ValueError, KeyError):
            api_metadata = {}

    guest_metadata = fetch_guest_page_metadata(document_url, timeout=timeout)
    return {
        'title': api_metadata.get('title') or guest_metadata.get('title', ''),
        'description': guest_metadata.get('description', ''),
        'cover': guest_metadata.get('cover', ''),
    }


def fetch_guest_page_metadata(document_url, timeout=8):
    response = requests.get(
        document_url,
        headers={'User-Agent': 'SRMember/1.0 (+https://sr-studio.cn)'},
        timeout=timeout,
    )
    response.raise_for_status()

    parser = PageMetadataParser()
    parser.feed(response.text)
    cover = (
        parser.meta.get('og:image')
        or parser.meta.get('twitter:image')
        or parser.meta.get('twitter:image:src')
        or ''
    )
    description = (
        parser.meta.get('og:description')
        or parser.meta.get('description')
        or parser.meta.get('twitter:description')
        or ''
    )
    title = parser.meta.get('og:title') or parser.meta.get('twitter:title') or parser.title

    return {
        'title': clean_page_title(title),
        'description': description,
        'cover': urljoin(document_url, cover) if cover else '',
    }


def fetch_feishu_drive_metadata(document_url, app_id, app_key, timeout=8):
    doc_token, doc_type = parse_feishu_doc_token(document_url)
    if not doc_token or not doc_type:
        return {}

    api_base = get_open_api_base(document_url)
    token_response = requests.post(
        f'{api_base}/auth/v3/tenant_access_token/internal',
        json={'app_id': app_id, 'app_secret': app_key},
        timeout=timeout,
    )
    token_response.raise_for_status()
    tenant_access_token = token_response.json().get('tenant_access_token', '')
    if not tenant_access_token:
        return {}

    metadata_response = requests.post(
        f'{api_base}/drive/v1/metas/batch_query',
        headers={'Authorization': f'Bearer {tenant_access_token}'},
        json={'request_docs': [{'doc_token': doc_token, 'doc_type': doc_type}]},
        timeout=timeout,
    )
    metadata_response.raise_for_status()
    data = metadata_response.json().get('data', {})
    metas = data.get('metas') or []
    if not metas:
        return {}
    return {'title': metas[0].get('title', '')}


def parse_feishu_doc_token(document_url):
    parsed = urlparse(document_url)
    parts = [part for part in parsed.path.split('/') if part]
    for index, part in enumerate(parts[:-1]):
        if part not in FEISHU_DOC_TYPES:
            continue
        doc_type = 'bitable' if part == 'base' else part
        return parts[index + 1], doc_type
    return '', ''


def get_open_api_base(document_url):
    host = urlparse(document_url).netloc.lower()
    if 'larksuite.com' in host:
        return LARK_OPEN_API_BASE
    return FEISHU_OPEN_API_BASE


def clean_page_title(title):
    title = (title or '').strip()
    for suffix in (' - 飞书云文档', ' - Lark Docs'):
        if title.endswith(suffix):
            return title[: -len(suffix)].strip()
    return title
