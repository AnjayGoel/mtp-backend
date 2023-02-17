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
        user_info = get_user_info(token)

        if user_info is None:
            return None

        player = await database_sync_to_async(Player.get_if_exists)(user_info['email'])
        if player is None:
            logging.info(f"No Player found for {user_info['email']}")
            return None

        """
        has_played = await database_sync_to_async(Game.player_has_participated)(user_info['email'])

        if has_played and not settings.DEBUG:
            logging.info(f"Player {user_info['email']} has already player")
            return None
        """

        scope["user"] = player
        return await super().__call__(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    return JwtAuthMiddleware(AuthMiddlewareStack(inner))
