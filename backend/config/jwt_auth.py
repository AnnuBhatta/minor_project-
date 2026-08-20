from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError


@database_sync_to_async
def get_user(user_id):
    try:
        return get_user_model().objects.get(id=user_id)
    except get_user_model().DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticate browser WebSockets using the access token query parameter."""

    async def __call__(self, scope, receive, send):
        user = scope.get('user')
        if not user or not user.is_authenticated:
            token = parse_qs(scope.get('query_string', b'').decode()).get('token', [None])[0]
            if token:
                try:
                    validated_token = JWTAuthentication().get_validated_token(token)
                    user_id = validated_token['user_id']
                    scope['user'] = await get_user(user_id)
                except (TokenError, KeyError):
                    scope['user'] = AnonymousUser()
        return await super().__call__(scope, receive, send)
