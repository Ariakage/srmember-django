from authlib.integrations.django_client import OAuth
from django.conf import settings


oauth = OAuth()

oauth.register(
    name='sr_united',
    client_id=settings.OAUTH_CLIENT_ID,
    client_secret=settings.OAUTH_CLIENT_SECRET,
    server_metadata_url=settings.OAUTH_SERVER_METADATA_URL,
    client_kwargs={
        'scope': settings.OAUTH_SCOPE,
        'token_endpoint_auth_method': settings.OAUTH_TOKEN_ENDPOINT_AUTH_METHOD,
    },
)
