import json

from channels.generic.websocket import AsyncWebsocketConsumer, AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer

from api.utils import random_str


class ChatConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.group_name = None

    async def connect(self):
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
        self.group_name = "lobby"
        await self.channel_layer.group_add("lobby", self.channel_name)
        await self.accept()

        lobby_channels = list(self.channel_layer.groups["lobby"].keys())
        if len(lobby_channels) > 1:
            await self.channel_layer.group_send(
                "lobby",
                {
                    "type": "pair",
                    "channels": [lobby_channels[0], lobby_channels[1]],
                    "group": random_str()
                }
            )

    async def disconnect(self, close_code):
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
            await self.channel_layer.group_add(event["group"], self.channel_name)
            await self.channel_layer.group_discard("lobby", self.channel_name)
            await self.channel_layer.group_send(
                self.group_name, {
                    "type": "chat_message",
                    "sender": self.channel_name,
                    "message": f"{self.channel_name} joined {event['group']}"
                })
