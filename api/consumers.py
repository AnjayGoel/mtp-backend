import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Player, Game
from .utils import random_str

log = logging.getLogger(__name__)


class Commands:
    GAME_START = "GAME_START"
    GAME_UPDATE = "GAME_UPDATE"
    CHAT = "CHAT"
    PLAYER_DISCONNECT = "PLAYER_DISCONNECT"


class GameConsumer(AsyncJsonWebsocketConsumer):
    channels_info = dict()

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.player: Player = None
        self.opponent: Player = None
        self.game: Game = None
        self.group_name = None

    async def connect(self):
        self.player = self.scope["user"]
        self.channels_info[self.channel_name] = self.player
        self.group_name = "lobby"

        log.info(self.channels_info)

        await self.channel_layer.group_add("lobby", self.channel_name)
        await self.accept()

        lobby_channels = list(self.channel_layer.groups["lobby"].keys())
        if len(lobby_channels) > 1:
            group_name = random_str()
            player_one = lobby_channels[0]
            player_two = lobby_channels[1]
            await self.channel_layer.group_add(group_name, player_one)
            await self.channel_layer.group_add(group_name, player_two)
            await self.channel_layer.group_discard("lobby", player_one)
            await self.channel_layer.group_discard("lobby", player_two)

            game = Game(
                player_one=self.channels_info[player_one],
                player_two=self.channels_info[player_two]
            )

            await database_sync_to_async(game.save)()

            await self.channel_layer.group_send(
                group_name,
                {
                    "type": "game_init",
                    "channels": [lobby_channels[0], lobby_channels[1]],
                    "group": group_name,
                    "game": game
                }
            )

    async def disconnect(self, close_code):
        if self.channel_name in self.channels_info:
            del self.channels_info[self.channel_name]
        await self.channel_layer.group_send(
            self.group_name, {
                "type": "group_disconnect",
                "sender": self.channel_name
            }
        )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, data, **kwargs):
        log.info(f"chanel: {self.channel_name}: received: {json.dumps(data)}")

        if data["event"] == Commands.CHAT:
            await self.channel_layer.group_send(
                self.group_name, data
            )

    async def chat(self, event):
        log.info(f"chat: {event}, receiver: {self.player.name}")
        await self.send_json(event)

    async def game_init(self, event):
        log.info(f"event: {event}")
        self.game = event["game"]
        if self.channel_name == event["channels"][0]:
            self.opponent = self.channels_info[event["channels"][1]]
        else:
            self.opponent = self.channels_info[event["channels"][0]]
        await self.send_json({
            "event": Commands.GAME_START,
            "data": {
                "game_type": self.game.game_type,
                "opponent": self.opponent
            }
        })

    async def group_disconnect(self, event):
        log.info(f"user disconnected from group: {event}")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.disconnect(close_code=0)
        # await self.channel_layer.group_add("lobby", self.channel_name)
        # self.group_name = "lobby"
