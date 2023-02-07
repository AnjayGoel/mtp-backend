import logging

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.db import close_old_connections

from api.models import Player
from api.utils import get_user_info


class JwtAuthMiddleware(BaseMiddleware):
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        close_old_connections()

        token = str(scope["query_string"]).split("=")[1] + "=="

        logging.info(token)

        user_info = get_user_info(token)

        logging.info(user_info)
        logging.info('user info')

        if user_info is None:
            return None

        player = await database_sync_to_async(Player.get_if_exists)(user_info['email'])
        if player is None:
            return None

        scope["user"] = player
        return await super().__call__(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    return JwtAuthMiddleware(AuthMiddlewareStack(inner))
