import bleach
import markdown as markdown_lib
import pymdownx.emoji
from bleach.css_sanitizer import CSSSanitizer
from pathlib import Path


MARKDOWN_EXTENSIONS = [
    'markdown.extensions.toc',
    'pymdownx.arithmatex',
    'pymdownx.b64',
    'pymdownx.betterem',
    'pymdownx.blocks.admonition',
    'pymdownx.blocks.caption',
    'pymdownx.blocks.definition',
    'pymdownx.blocks.details',
    'pymdownx.blocks.html',
    'pymdownx.blocks.tab',
    'pymdownx.caret',
    'pymdownx.details',
    'pymdownx.emoji',
    'pymdownx.extra',
    'pymdownx.fancylists',
    'pymdownx.highlight',
    'pymdownx.inlinehilite',
    'pymdownx.keys',
    'pymdownx.magiclink',
    'pymdownx.mark',
    'pymdownx.progressbar',
    'pymdownx.quotes',
    'pymdownx.saneheaders',
    'pymdownx.smartsymbols',
    'pymdownx.superfences',
    'pymdownx.tabbed',
    'pymdownx.tasklist',
    'pymdownx.tilde',
    'pymdownx.critic',
]

MARKDOWN_EXTENSION_CONFIGS = {
    'pymdownx.arithmatex': {'generic': True},
    'pymdownx.b64': {'base_path': str(Path(__file__).resolve().parents[2])},
    'pymdownx.blocks.details': {
        'types': [
            {'name': 'spoiler', 'class': 'spoiler', 'title': 'Spoiler'},
        ],
    },
    'pymdownx.blocks.html': {
        'custom': [
            {'tag': 'div', 'mode': 'block'},
            {'tag': 'section', 'mode': 'block'},
            {'tag': 'aside', 'mode': 'block'},
        ],
    },
    'pymdownx.blocks.tab': {'alternate_style': True},
    'pymdownx.emoji': {
        'emoji_index': pymdownx.emoji.gemoji,
        'emoji_generator': pymdownx.emoji.to_alt,
    },
    'pymdownx.highlight': {
        'anchor_linenums': True,
        'line_spans': '__span',
        'pygments_lang_class': True,
        'use_pygments': True,
    },
    'pymdownx.superfences': {
        'preserve_tabs': True,
    },
    'pymdownx.quotes': {'callouts': True},
    'pymdownx.tabbed': {'alternate_style': True},
    'pymdownx.tasklist': {
        'clickable_checkbox': False,
        'custom_checkbox': True,
    },
}

ALLOWED_TAGS = {
    'a',
    'abbr',
    'admonition',
    'article',
    'aside',
    'b',
    'blockquote',
    'br',
    'caption',
    'code',
    'dd',
    'del',
    'details',
    'div',
    'dl',
    'dt',
    'em',
    'figcaption',
    'figure',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'hr',
    'i',
    'img',
    'input',
    'ins',
    'kbd',
    'label',
    'li',
    'mark',
    'ol',
    'p',
    'pre',
    'progress',
    's',
    'small',
    'span',
    'section',
    'strong',
    'sub',
    'summary',
    'sup',
    'table',
    'tbody',
    'td',
    'th',
    'thead',
    'tr',
    'ul',
}

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id', 'style', 'title', 'aria-hidden', 'aria-label'],
    'a': ['href', 'name', 'rel', 'target', 'title'],
    'img': ['alt', 'height', 'src', 'title', 'width'],
    'details': ['open'],
    'input': ['checked', 'disabled', 'id', 'name', 'type', 'value'],
    'label': ['for'],
    'li': ['value'],
    'ol': ['reversed', 'start', 'type'],
    'progress': ['max', 'value'],
    'td': ['align', 'colspan', 'rowspan'],
    'th': ['align', 'colspan', 'rowspan'],
}

ALLOWED_CSS_PROPERTIES = [
    'width',
]

ALLOWED_PROTOCOLS = ['data', 'http', 'https', 'mailto']


def render_markdown(source):
    html = markdown_lib.markdown(
        source or '',
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs=MARKDOWN_EXTENSION_CONFIGS,
        output_format='html',
    )
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES),
        strip=True,
    )
