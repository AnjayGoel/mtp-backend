import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .utils import random_str


class GameConsumer(AsyncJsonWebsocketConsumer):

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.group_name = None
        self.email = None

    async def connect(self):
        """
        # print(self.scope['user'])
        # print(self.scope['session'])
        # print('-------------------')
        # print(self.channel_name)
        # print(self.groups)
        # print(self.scope)
        # print('-' * 10)
        # self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        # self.room_group_name = "chat_%s" % self.room_name
        # Join room group
        """
        """
        token = str(self.scope["query_string"]).split("=")[1] + "=="
        user_info = get_user_info(token)
        print(user_info)
        print(token)
        obj: Player = await database_sync_to_async(Player.get_if_exists)(user_info['email'])
        if obj is None:
            await self.close()
            return

        print(obj.avatar)
        # if user_info is not None and Player.objects.exists(user_info['email']):
        #    print(user_info)
        """
        self.group_name = "lobby"
        await self.channel_layer.group_add("lobby", self.channel_name)
        await self.accept()

        lobby_channels = list(self.channel_layer.groups["lobby"].keys())
        if len(lobby_channels) > 1:
            group_name = random_str()
            await self.channel_layer.group_add(group_name, lobby_channels[0])
            await self.channel_layer.group_add(group_name, lobby_channels[1])
            await self.channel_layer.group_discard("lobby", lobby_channels[0])
            await self.channel_layer.group_discard("lobby", lobby_channels[1])
            await self.channel_layer.group_send(
                group_name,
                {
                    "type": "pair",
                    "channels": [lobby_channels[0], lobby_channels[1]],
                    "group": group_name
                }
            )

    async def disconnect(self, close_code):
        await self.channel_layer.group_send(
            self.group_name, {
                "type": "group_disconnect",
                "sender": self.channel_name
            }
        )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, data, **kwargs):
        print(f"chanel: {self.channel_name}: received: {json.dumps(data)}")

        await self.channel_layer.group_send(
            self.group_name, {
                "type": "chat_message",
                **data
            }
        )

    async def chat_message(self, event):
        print(f"chat: {event}, receiver: {self.channel_name}")
        await self.send_json(event)

    async def pair(self, event):
        print(f"event: {event}")
        if self.channel_name in event["channels"]:
            self.group_name = event["group"]
            await self.channel_layer.group_send(
                self.group_name, {
                    "type": "chat_message",
                    "sender": self.channel_name,
                    "message": f"{self.channel_name} joined {event['group']}"
                })

    async def group_disconnect(self, event):
        print(f"user disconnected from group: {event}")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.channel_layer.group_add("lobby", self.channel_name)
        self.group_name = "lobby"
