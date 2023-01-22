import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Player, Game
from .serializers import PlayerSerializer
from .utils import random_str

log = logging.getLogger(__name__)


class Commands:
    GAME_START = "game_start"
    GAME_UPDATE = "game_update"
    CHAT = "chat"
    PLAYER_DISCONNECT = "player_disconnect"
    WEB_RTC_MEDIA_OFFER = "web_rtc_media_offer"
    WEB_RTC_MEDIA_ANSWER = "web_rtc_media_answer"
    WEB_RTC_ICE_CANDIDATE = "web_rtc_ice_candidate"
    WEB_RTC_REMOTE_PEER_ICE_CANDIDATE = "remote_peer_ice_candidate"


class GameConsumer(AsyncJsonWebsocketConsumer):
    channels_info = dict()

    commands_list = [v for k, v in dict(vars(Commands)).items() if "__" not in k]

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

        log.info(f"Channel {self.channel_name}: connected.\nChannels info: {self.channels_info}")

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
                    "data": {
                        "channels": [lobby_channels[0], lobby_channels[1]],
                        "group": group_name,
                        "game": game,
                        "player_one": player_one
                    }
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
        log.info(f"Channel: {self.channel_name} Disconnecting. Channels {self.channels_info}")

    async def receive_json(self, data, **kwargs):
        data["sender"] = self.channel_name
        log.info(
            f"----------------\n"
            f"Chanel: {self.channel_name}\n"
            f"Group: {self.group_name}\n"
            f"Channels: {list(self.channel_layer.groups[self.group_name].keys())}\n"
            f"Received: {json.dumps(data, indent=4)}\n"
            f"{data['type'] == Commands.WEB_RTC_MEDIA_OFFER}")

        if data["type"] in self.commands_list:
            await self.channel_layer.group_send(
                self.group_name, data
            )

    async def web_rtc_media_offer(self, event):
        if event["sender"] != self.channel_name:
            await self.send_json(event)

    async def web_rtc_media_answer(self, event):
        if event["sender"] != self.channel_name:
            await self.send_json(event)

    async def web_rtc_ice_candidate(self, event):
        if event["sender"] != self.channel_name:
            event["type"] = Commands.WEB_RTC_REMOTE_PEER_ICE_CANDIDATE
            await self.send_json(event)

    async def chat(self, event):
        await self.send_json(event)

    async def game_init(self, event):
        log.info(f"Game Init: {event}")
        data = event["data"]
        self.game = data["game"]
        self.group_name = data["group"]
        if self.channel_name == data["channels"][0]:
            self.opponent = self.channels_info[data["channels"][1]]
        else:
            self.opponent = self.channels_info[data["channels"][0]]
        await self.send_json({
            "type": Commands.GAME_START,
            "data": {
                "is_player_one": self.channel_name == data["player_one"],
                "game_type": self.game.game_type,
                "opponent": PlayerSerializer(self.opponent).data
            }
        })
        log.info(f"Current: {self.channel_name} Opponent: {self.opponent}")

    async def group_disconnect(self, event):
        log.info(f"User disconnected from group: {event}")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.send_json({"type": Commands.PLAYER_DISCONNECT})
        await self.disconnect(close_code=0)
        # await self.channel_layer.group_add("lobby", self.channel_name)
        # self.group_name = "lobby"
