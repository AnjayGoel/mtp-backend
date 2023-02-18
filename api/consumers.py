import logging
import pickle
import random
from datetime import datetime
from typing import List

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.conf import settings
from django.core.cache import cache
from redis.exceptions import ConnectionError

from .games import get_game, BaseGame, GAME_LIST
from .models import Player, Game
from .serializers import PlayerSerializer
from .utils import random_str, dumps

log = logging.getLogger(__name__)


class C:
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
    REMOTE_IMAGE_URI = "remote_image_uri"

    WRTC_COMMANDS = [
        WEB_RTC_REMOTE_PEER_ICE_CANDIDATE,
        WEB_RTC_ICE_CANDIDATE,
        WEB_RTC_MEDIA_OFFER,
        WEB_RTC_MEDIA_ANSWER
    ]
    IGNORE_LOG = WRTC_COMMANDS + [REMOTE_IMAGE_URI]


COMMANDS_LIST = [v for k, v in dict(vars(C)).items() if "__" not in k]


class WebRTCSignalingConsumer(JsonWebsocketConsumer):
    def web_rtc_media_offer(self, event):
        self.send_json(event)

    def web_rtc_media_answer(self, event):
        self.send_json(event)

    def web_rtc_ice_candidate(self, event):
        event["type"] = C.WEB_RTC_REMOTE_PEER_ICE_CANDIDATE
        self.send_json(event)


class Active:
    @staticmethod
    def all():
        obj = cache.get('active_channels', {})
        return {k: v['data'] for k, v in obj.items() if v['ttl'] > int(datetime.now().timestamp())}

    @staticmethod
    def get(name) -> Player:
        obj = cache.get('active_channels', {})
        if name in obj and obj[name]['ttl'] > int(datetime.now().timestamp()):
            return obj[name]['data']
        else:
            return None

    @staticmethod
    def set(name, player: Player):
        obj = cache.get('active_channels', {})
        obj = {k: v for k, v in obj.items() if v['data'].email != player.email}
        obj[name] = {'data': player, "ttl": int(datetime.now().timestamp()) + 60 * 15}
        cache.set('active_channels', obj, 60 * 30)

    @staticmethod
    def delete(name):
        obj = cache.get('active_channels', {})
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
        self.scores = [0, 0]

    def connect(self):
        self.player = self.scope["user"]
        self.player.channel_name = self.channel_name

        self.add_to_lobby(self.channel_name, self.player, None)
        self.group_id = "lobby"

        log.info(dumps({
            "event": "player_connected",
            "player": self.player.email,
            "channel": self.player.channel_name,
            "channels": Active.all()
        }))

        self.accept()
        self.create_group()

    def disconnect(self, close_code):
        log.info(dumps({
            "event": C.PLAYER_DISCONNECT,
            "player": self.player.email,
            "channel": self.player.channel_name,
            "channels": Active.all()
        }))

        if self.group_id != "lobby":
            async_to_sync(self.channel_layer.group_send)(
                self.group_id, {
                    "type": "player_disconnect",
                    "sender": self.channel_name
                }
            )

        if self.group_id == "lobby":
            self.add_to_group(self.channel_name, None)
        else:
            async_to_sync(self.channel_layer.group_discard)(self.group_id, self.channel_name)
        super(GameConsumer, self).disconnect(close_code)

    def receive_json(self, data, **kwargs):
        data["sender"] = self.channel_name

        if data['type'] not in C.IGNORE_LOG:
            log.info(dumps({
                "chanel": self.channel_name,
                "group": self.group_id,
                "data": data
            }))

        if data["type"] == C.RETRY_MATCHING:
            self.create_group()

        elif data["type"] == C.GAME_UPDATE:
            log.info("HERE" * 10)
            async_to_sync(self.channel_layer.send)(
                self.game.server.channel_name,
                {"type": C.HANDLE_GAME_EVENT, "data": data}
            )

        elif data["type"] == C.REMOTE_IMAGE_URI:
            async_to_sync(self.channel_layer.send)(
                self.opponent.channel_name,
                data
            )

        elif data["type"] in C.WRTC_COMMANDS:
            async_to_sync(self.channel_layer.send)(self.opponent.channel_name, data)

        elif data["type"] in COMMANDS_LIST:
            async_to_sync(self.channel_layer.group_send)(
                self.group_id, data
            )

    def remote_image_uri(self, event):
        self.send_json(event)

    def add_to_lobby(self, channel_name, player, prev_group_id):
        if prev_group_id is not None:
            async_to_sync(self.channel_layer.group_discard)(prev_group_id, channel_name)
        try:
            async_to_sync(self.channel_layer.group_add)("lobby", channel_name)
        except ConnectionError as e:
            """Connection getting dropped when idle"""
            async_to_sync(self.channel_layer.group_add)("lobby", channel_name)

        Active.set(channel_name, player)

    def add_to_group(self, channel_name, group_id):
        async_to_sync(self.channel_layer.group_discard)("lobby", channel_name)
        if group_id is not None:
            async_to_sync(self.channel_layer.group_add)(group_id, channel_name)
        Active.delete(channel_name)

    def find_opponent(self) -> List:
        log.info(dumps(
            {
                "group": self.group_id,
                "self": self.channel_name,
                "active": Active.all()
            }
        ))

        players = Active.all()

        for channel in players:
            if channel != self.channel_name:
                other_player = players[channel]
                if other_player.email == self.player.email:
                    continue

                if settings.DEBUG:
                    have_played = False
                else:
                    have_played = Game.players_hava_played(self.player.email, other_player.email)

                # TODO: Fix this
                # have_played = False

                if not have_played:
                    return [self.channel_name, channel]
        return None

    def create_group(self):
        if self.channel_name not in Active.all():
            return

        lobby_channels = self.find_opponent()

        log.info(dumps(
            {
                "event": "matched",
                "player": self.player.email,
                "channels": lobby_channels
            }
        ))

        if lobby_channels is not None:
            group_name = random_str()

            server = Active.get(lobby_channels[0])
            client = Active.get(lobby_channels[1])

            self.add_to_group(lobby_channels[0], group_name)
            self.add_to_group(lobby_channels[1], group_name)

            self.init_game(
                server=server,
                client=client,
                group_name=group_name,
                game_id=1
            )

    def player_disconnect(self, event):
        async_to_sync(self.channel_layer.group_discard)(self.group_id, self.channel_name)
        self.send_json({"type": C.PLAYER_DISCONNECT})
        self.disconnect(close_code=0)

    def chat(self, event):
        self.send_json(event)

    def init_game(self, server: Player, client: Player, group_name, info_type=None, game_id=1):
        if info_type is None:
            if settings.DEBUG:
                info_type = [Game.InfoType.INFO, Game.InfoType.CHAT, Game.InfoType.VIDEO]
            else:
                info_type = random.sample([
                    Game.InfoType.INFO,
                    Game.InfoType.VIDEO,
                    Game.InfoType.CHAT
                ], random.randint(0, 3))
            # TODO Fix this
            # info_type = [Game.InfoType.INFO, Game.InfoType.CHAT, Game.InfoType.VIDEO]

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
                "type": C.GAME_START,
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

        message = {
            "type": C.GAME_START,
            "data": {
                "is_server": self.is_server,
                "info_type": self.game.info_type,
                "game_id": self.game.game_id,
                "opponent": PlayerSerializer(self.opponent).data,
                "config": self.game.config,
                "scores": self.scores
            }
        }

        self.send_json(message)
        log.info(dumps(message))

    def handle_game_event(self, message: dict):
        data = message['data']

        self.game.update_state(data)
        data["finished"] = self.game.is_complete()
        if data['finished']:
            data['scores'] = self.game.get_current_scores()

        data['sender'] = self.player.email if data['sender'] == self.channel_name else self.opponent.email

        message = {
            "type": C.GAME_UPDATE,
            "data": {
                "last_event": data,
                "state": self.game.state,
                "actions": self.game.actions
            }
        }

        log.info(dumps(message))
        log.info('************')

        async_to_sync(self.channel_layer.group_send)(self.group_id, message)

        if self.game.is_complete():
            self.game.save()
            self.init_game(
                server=self.game.server,
                client=self.game.client,
                group_name=self.group_id,
                game_id=(self.game.game_id + 1) % len(GAME_LIST),
                info_type=self.game.info_type
            )
            if self.game.game_name == "outro":
                self.disconnect(123)

    def game_update(self, message):
        data = message["data"]
        self.game.state = data["state"]
        self.game.actions = data["actions"]

        if data['last_event']['finished']:
            scores = data['last_event']['scores']

            if self.is_server:
                self.scores[0] += scores[0]
                self.scores[1] += scores[1]
            else:
                self.scores[0] += scores[1]
                self.scores[1] += scores[0]

        self.send_json(message)
