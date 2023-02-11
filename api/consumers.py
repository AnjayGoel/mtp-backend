import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import random
from .games import get_game, BaseGame
from .models import Player, Game
from .serializers import PlayerSerializer
from .utils import random_str, dumps

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


COMMANDS_LIST = [v for k, v in dict(vars(Commands)).items() if "__" not in k]


class WebRTCSignalingConsumer(AsyncJsonWebsocketConsumer):
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


class GameConsumer(WebRTCSignalingConsumer):
    channels_info = dict()

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.is_server = False
        self.player: Player = None
        self.opponent: Player = None
        self.game: BaseGame = None
        self.group_id = None

    async def connect(self):
        self.player = self.scope["user"]
        self.player.channel_name = self.channel_name

        GameConsumer.channels_info[self.channel_name] = self.player

        log.info(dumps({
            "event": "player_connected",
            "channels": GameConsumer.channels_info
        }))

        self.group_id = "lobby"
        await self.channel_layer.group_add("lobby", self.channel_name)
        await self.accept()

        lobby_channels = list(self.channel_layer.groups["lobby"].keys())
        if len(lobby_channels) > 1:
            group_name = random_str()
            await self.channel_layer.group_add(group_name, lobby_channels[0])
            await self.channel_layer.group_add(group_name, lobby_channels[1])
            await self.channel_layer.group_discard("lobby", lobby_channels[0])
            await self.channel_layer.group_discard("lobby", lobby_channels[1])

            await self.create_game(
                channels=lobby_channels,
                group_name=group_name,
                game_id=1
            )

    async def disconnect(self, close_code):
        if self.channel_name in GameConsumer.channels_info:
            del GameConsumer.channels_info[self.channel_name]
        await self.channel_layer.group_send(
            self.group_id, {
                "type": "group_disconnect",
                "sender": self.channel_name
            }
        )
        await self.channel_layer.group_discard(self.group_id, self.channel_name)

    async def receive_json(self, data, **kwargs):
        data["sender"] = self.channel_name
        log.info(dumps({
            "chanel": self.channel_name,
            "group": self.group_id,
            "channels": list(self.channel_layer.groups[self.group_id].keys()),
            "data": data
        }))

        if data["type"] == Commands.GAME_UPDATE:
            data["type"] = Commands.SERVER_GAME_UPDATE

        if data["type"] in COMMANDS_LIST:
            await self.channel_layer.group_send(
                self.group_id, data
            )

    async def group_disconnect(self, event):
        await self.channel_layer.group_discard(self.group_id, self.channel_name)
        await self.send_json({"type": Commands.PLAYER_DISCONNECT})
        await self.disconnect(close_code=0)

    async def chat(self, event):
        await self.send_json(event)

    async def create_game(self, channels, group_name, info_type=None, game_id=1):
        server = GameConsumer.channels_info[channels[0]]
        client = GameConsumer.channels_info[channels[1]]

        if info_type is None:
            info_type = random.sample([
                Game.InfoType.INFO,
                Game.InfoType.VIDEO,
                Game.InfoType.CHAT
            ], random.randint(0, 3))

        game = get_game(
            group_id=group_name,
            server=server,
            client=client,
            info_type=info_type,
            game_id=game_id
        )

        await self.channel_layer.group_send(
            group_name,
            {
                "type": Commands.GAME_START,
                "data": game
            }
        )

    async def game_start(self, event):
        self.game = event["data"]
        log.info(dumps(event))
        self.group_id = self.game.group_id
        self.is_server = self.channel_name == self.game.server.channel_name

        if self.is_server:
            self.opponent = self.game.client
        else:
            self.opponent = self.game.server

        await self.send_json({
            "type": Commands.GAME_START,
            "data": {
                "is_server": self.is_server,
                "info_type": self.game.info_type,
                "game_id": self.game.game_id,
                "opponent": PlayerSerializer(self.opponent).data,
                "config": self.game.config
            }
        })
        log.info(dumps({
            "is_server": self.is_server,
            "info_type": self.game.info_type,
            "game_id": self.game.game_id,
            "opponent": PlayerSerializer(self.opponent).data,
            "config": self.game.config
        }))

    async def game_update(self, message):
        log.info(dumps(message))

        data = message["data"]
        if not self.is_server:
            self.game.state = data["state"]
            self.game.actions = data["actions"]
        await self.send_json(message)

    async def server_game_update(self, event: dict):
        if not self.is_server:
            return

        log.info(dumps(event))

        event["type"] = Commands.GAME_UPDATE
        self.game.update_state(event.copy())
        event["finished"] = self.game.is_complete()
        event['sender'] = GameConsumer.channels_info[event['sender']].email
        message = {
            "type": Commands.GAME_UPDATE,
            "data": {
                "last_event": event,
                "state": self.game.state,
                "actions": self.game.actions
            }
        }

        if self.game.is_complete():
            await self.game.save()
            await self.channel_layer.group_send(self.group_id, message)
            await self.create_game(
                channels=[self.game.server.channel_name, self.game.client.channel_name],
                group_name=self.group_id,
                game_id=(self.game.game_id + 1) % 5,
                info_type=self.game.info_type
            )
        else:
            await self.channel_layer.group_send(self.group_id, message)
