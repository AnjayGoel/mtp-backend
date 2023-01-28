import json
import logging
import time
# TODO: WebRTC going through right channel not lobby
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .games import games, get_game, BaseGame, GameType
from .models import Player, Game
from .serializers import PlayerSerializer
from .utils import random_str

log = logging.getLogger(__name__)


class Commands:
    GAME_START = "game_start"
    GAME_UPDATE = "game_update"
    SERVER_GAME_UPDATE = "server_game_update"
    GAME_END = "game_end"

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
        self.is_server = False
        self.player: Player = None
        self.opponent: Player = None
        self.game: BaseGame = None
        self.group_name = None

    async def connect(self):
        self.player = self.scope["user"]
        GameConsumer.channels_info[self.channel_name] = self.player
        self.group_name = "lobby"

        log.info(f"Channel {self.channel_name}: connected.\nChannels info: {GameConsumer.channels_info}")

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

            await self.create_game(
                channels=[player_one, player_two],
                group_name=group_name
            )

    async def disconnect(self, close_code):
        if self.channel_name in GameConsumer.channels_info:
            del GameConsumer.channels_info[self.channel_name]
        await self.channel_layer.group_send(
            self.group_name, {
                "type": "group_disconnect",
                "sender": self.channel_name
            }
        )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        log.info(f"Channel: {self.channel_name} Disconnecting. Channels {GameConsumer.channels_info}")

    async def receive_json(self, data, **kwargs):
        data["sender"] = self.channel_name
        log.info(
            f"----------------\n"
            f"Chanel: {self.channel_name}\n"
            f"Group: {self.group_name}\n"
            f"Channels: {list(self.channel_layer.groups[self.group_name].keys())}\n"
            f"Received: {json.dumps(data, indent=4)}\n"
            f"{data['type'] == Commands.WEB_RTC_MEDIA_OFFER}")

        if data["type"] == Commands.GAME_UPDATE:
            data["type"] = Commands.SERVER_GAME_UPDATE

        if data["type"] in GameConsumer.commands_list:
            await self.channel_layer.group_send(
                self.group_name, data
            )

    async def group_disconnect(self, event):
        log.info(f"User disconnected from group: {event}")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.send_json({"type": Commands.PLAYER_DISCONNECT})
        await self.disconnect(close_code=0)
        # await self.channel_layer.group_add("lobby", self.channel_name)
        # self.group_name = "lobby"

    async def chat(self, event):
        await self.send_json(event)

    async def create_game(self, channels, group_name, server=None):
        player_one = channels[0]
        player_two = channels[1]

        if server is None:
            server = player_one

        # TODO: Fix this
        game = get_game(
            group_id=group_name,
            player_one=player_one,
            player_two=player_two,
            game_type=games[0],
            info_type=[
                Game.InfoType.INFO,
                Game.InfoType.VIDEO,
                Game.InfoType.CHAT
            ],
            server=server
        )

        await self.channel_layer.group_send(
            group_name,
            {
                "type": Commands.GAME_START,
                "data": {
                    "channels": channels,
                    "group": group_name,
                    "game": game
                }
            }
        )

    async def game_start(self, event):
        log.info(f"Game Init: {event}")
        data = event["data"]
        self.game = data["game"]
        self.group_name = data["group"]
        self.is_server = self.channel_name == data["game"].server

        if self.channel_name == data["channels"][0]:
            self.opponent = GameConsumer.channels_info[data["channels"][1]]
        else:
            self.opponent = GameConsumer.channels_info[data["channels"][0]]

        await self.send_json({
            "type": Commands.GAME_START,
            "data": {
                "player_one": self.is_server,
                "game_type": self.game.game_type,
                "opponent": PlayerSerializer(self.opponent).data
            }
        })
        log.info(f"Current: {self.channel_name} Opponent: {self.opponent}")

    async def game_update(self, event):
        if not self.is_server:
            self.game.update_state(event)

        if self.game.game_type == GameType.SIM and not event["is_complete"]:
            return

        await self.send_json(event)

    async def server_game_update(self, event):
        if not self.is_server:
            return

        event["type"] = Commands.GAME_UPDATE
        self.game.update_state(event)

        if self.game.is_complete():
            game = Game(
                player_one=GameConsumer.channels_info[self.game.player_one],
                player_two=GameConsumer.channels_info[self.game.player_two],
                state=self.game.state,
                info_type=self.game.info_type,
                group_id=self.game.group_id
            )
            await database_sync_to_async(game.save)()

            event["is_finished"] = True
            await self.send_json(event)
            await self.create_game(
                channels=[self.game.player_one, self.game.player_two],
                group_name=self.group_name,
                server=self.game.server
            )
        else:
            event["is_finished"] = False
            await self.send_json(event)

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
