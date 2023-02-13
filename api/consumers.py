import logging
import pickle
from typing import Dict, List
from django.core.cache import cache
from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
import random

from channels_redis.core import RedisChannelLayer

from .games import get_game, BaseGame
from .models import Player, Game
from .serializers import PlayerSerializer
from .utils import random_str, dumps
from django.conf import settings

log = logging.getLogger(__name__)


class Commands:
    GAME_START = "game_start"
    GAME_UPDATE = "game_update"
    SERVER_GAME_UPDATE = "server_game_update"
    RETRY_MATCHING = "retry_matching"
    HANDLE_GAME_EVENT = "handle_game_event"
    CHAT = "chat"
    PLAYER_DISCONNECT = "player_disconnect"

    WEB_RTC_MEDIA_OFFER = "web_rtc_media_offer"
    WEB_RTC_MEDIA_ANSWER = "web_rtc_media_answer"
    WEB_RTC_ICE_CANDIDATE = "web_rtc_ice_candidate"
    WEB_RTC_REMOTE_PEER_ICE_CANDIDATE = "remote_peer_ice_candidate"


COMMANDS_LIST = [v for k, v in dict(vars(Commands)).items() if "__" not in k]


class WebRTCSignalingConsumer(JsonWebsocketConsumer):
    def web_rtc_media_offer(self, event):
        if event["sender"] != self.channel_name:
            self.send_json(event)

    def web_rtc_media_answer(self, event):
        if event["sender"] != self.channel_name:
            self.send_json(event)

    def web_rtc_ice_candidate(self, event):
        if event["sender"] != self.channel_name:
            event["type"] = Commands.WEB_RTC_REMOTE_PEER_ICE_CANDIDATE
            self.send_json(event)

    def remote_peer_ice_candidate(self, event):
        log.info(event)
        log.info('-' * 20)


class Active:
    @staticmethod
    def all():
        obj = cache.get('active_channels')
        if obj is None:
            cache.set('active_channels', {}, 60 * 30)
            return {}
        else:
            return obj

    @staticmethod
    def get(name) -> Player:
        obj = Active.all()
        if name in obj:
            return obj[name]
        else:
            return None

    @staticmethod
    def set(name, player: Player):
        obj: Dict[str, Player] = Active.all()
        obj = {k: v for k, v in obj.items() if v.email != player.email}
        obj[name] = player
        cache.set('active_channels', obj, 60 * 30)

    @staticmethod
    def delete(name):
        obj = Active.all()
        if name in obj:
            del obj[name]
        cache.set('active_channels', obj, 60 * 30)


class GameConsumer(WebRTCSignalingConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.is_server = False
        self.player: Player = None
        self.opponent: Player = None
        self.game: BaseGame = None
        self.group_id = None

    def get_group_members(self, group):
        async def inner(group):
            cl: RedisChannelLayer = self.channel_layer
            key = cl._group_key(group)
            con = cl.connection(cl.consistent_hash(group))
            rng = await con.zrange(key, 0, -1)
            return [x.decode("utf8") for x in rng]

        return async_to_sync(inner)(group)

    def get_players(self) -> List:
        Active.set(self.channel_name, self.player)
        log.info(f"Channels: {self.get_group_members('lobby')}")
        log.info(f"Self: {self.channel_name}")
        log.info(f"Saved: {Active.all()}")
        log.info('-' * 30)

        for channel in self.get_group_members("lobby"):
            if channel != self.channel_name and channel in Active.all():
                other_player = Active.get(channel)
                if other_player.email == self.player.email:
                    continue

                if settings.DEBUG:
                    have_played = False
                else:
                    have_played = Game.players_hava_played(self_player.email, other_player.email)

                # TODO: Fix this
                have_played = False

                if not have_played:
                    return [self.channel_name, channel]
        return None

    def create_group(self):
        if self.group_id != "lobby":
            return

        lobby_channels = self.get_players()

        log.info(f'matched: {lobby_channels}')

        if lobby_channels is not None:
            log.info(' '.join(lobby_channels))
            group_name = random_str()
            async_to_sync(self.channel_layer.group_add)(group_name, lobby_channels[0])
            async_to_sync(self.channel_layer.group_add)(group_name, lobby_channels[1])
            async_to_sync(self.channel_layer.group_discard)("lobby", lobby_channels[0])
            async_to_sync(self.channel_layer.group_discard)("lobby", lobby_channels[1])

            self.create_game(
                channels=lobby_channels,
                group_name=group_name,
                game_id=1
            )

    def connect(self):
        self.player = self.scope["user"]
        self.player.channel_name = self.channel_name

        Active.set(self.channel_name, self.player)

        log.info(dumps({
            "event": "player_connected",
            "channels": Active.all()
        }))

        self.group_id = "lobby"
        async_to_sync(self.channel_layer.group_add)("lobby", self.channel_name)
        self.accept()
        self.create_group()

    def disconnect(self, close_code):
        Active.delete(self.channel_name)
        async_to_sync(self.channel_layer.group_send)(
            self.group_id, {
                "type": "player_disconnect",
                "sender": self.channel_name
            }
        )
        async_to_sync(self.channel_layer.group_discard)(self.group_id, self.channel_name)
        super(GameConsumer, self).disconnect(close_code)

    def receive_json(self, data, **kwargs):
        data["sender"] = self.channel_name
        log.info(dumps({
            "chanel": self.channel_name,
            "group": self.group_id,
            "channels": self.get_group_members(self.group_id),
            "data": data
        }))

        if data["type"] == Commands.RETRY_MATCHING:
            self.create_group()
        elif data["type"] == Commands.GAME_UPDATE:
            async_to_sync(self.channel_layer.group_send)(
                self.group_id,
                {"type": Commands.HANDLE_GAME_EVENT, "data": data}
            )
            # self.handle_game_event(data)

        elif data["type"] in COMMANDS_LIST:
            async_to_sync(self.channel_layer.group_send)(
                self.group_id, data
            )

    def player_disconnect(self, event):
        async_to_sync(self.channel_layer.group_discard)(self.group_id, self.channel_name)
        self.send_json({"type": Commands.PLAYER_DISCONNECT})
        self.disconnect(close_code=0)

    def chat(self, event):
        self.send_json(event)

    def create_game(self, channels, group_name, info_type=None, game_id=1):
        server = Active.get(channels[0])
        client = Active.get(channels[1])

        if info_type is None:
            info_type = random.sample([
                Game.InfoType.INFO,
                Game.InfoType.VIDEO,
                Game.InfoType.CHAT
            ], random.randint(0, 3))
            # TODO Fix this
            info_type = [Game.InfoType.INFO, Game.InfoType.CHAT, Game.InfoType.VIDEO]

        game = get_game(
            group_id=group_name,
            server=server,
            client=client,
            info_type=info_type,
            game_id=game_id
        )

        async_to_sync(self.channel_layer.group_send)(
            group_name,
            {
                "type": Commands.GAME_START,
                "data": pickle.dumps(game)
            }
        )

    def game_start(self, event):
        game = pickle.loads(event['data'])
        self.game = game
        self.group_id = self.game.group_id
        self.is_server = self.channel_name == self.game.server.channel_name

        if self.is_server:
            self.opponent = self.game.client
        else:
            self.opponent = self.game.server

        self.send_json({
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

    def game_update(self, message):
        log.info(f'----------GAME UPDATE ({self.is_server})--------------')
        log.info(dumps(message))

        data = message["data"]
        log.info(data)

        self.game.state = data["state"]
        self.game.actions = data["actions"]
        self.send_json(message)

    def handle_game_event(self, message: dict):
        if not self.is_server:
            return

        log.info('----------SERVER GAME UPDATE--------------')
        log.info(dumps(message))

        data = message['data']

        self.game.update_state(data.copy())
        data["finished"] = self.game.is_complete()
        data['sender'] = Active.get(data['sender']).email
        message = {
            "type": Commands.GAME_UPDATE,
            "data": {
                "last_event": data,
                "state": self.game.state,
                "actions": self.game.actions
            }
        }
        log.info('######')
        log.info(message)
        if self.game.is_complete():
            log.info("COMPLETE")
            self.game.save()
            async_to_sync(self.channel_layer.group_send)(self.group_id, message)
            self.create_game(
                channels=[self.game.server.channel_name, self.game.client.channel_name],
                group_name=self.group_id,
                game_id=(self.game.game_id + 1) % 6,
                info_type=self.game.info_type
            )
            if self.game.game_name == "outro":
                self.disconnect(123)
        else:
            async_to_sync(self.channel_layer.group_send)(self.group_id, message)
