import logging

from channels.db import database_sync_to_async

from api.models import Player, Game

games = ["prisoners_dilemma"]


class BaseGame:
    state = {}
    actions = []
    server: Player = None
    client: Player = None
    info_type: Game.InfoType = None
    group_id = None
    is_sim = False
    game_name = None
    config = None

    def __init__(self, group_id, server, client, info_type):
        self.server = server
        self.client = client
        self.info_type = info_type
        self.group_id = group_id
        self.state = {}
        self.actions = []
        self.config = {}

    def update_state(self, event):
        if event['sender'] == self.server.channel_name:
            event['sender'] = self.server.email
        else:
            event['sender'] = self.client.email

        if self.is_sim:
            actions = list(filter(lambda x: x['sender'] == event['sender'], self.actions))

            if len(actions) > 0:
                return

            self.actions.append(event)
            self.state[event['sender']] = event['data']
        else:
            self.actions.append(event)

    def is_complete(self):
        if len(self.actions) == 2:
            return True

    def get_state(self):
        return self.state

    async def save(self):
        game = Game(
            server=self.server,
            client=self.client,
            state=self.state,
            actions=self.actions,
            info_type=self.info_type,
            group_id=self.group_id
        )
        await database_sync_to_async(game.save)()


class PrisonersDilemma(BaseGame):
    def __init__(self, group_id, server, client, info_type):
        super(PrisonersDilemma, self).__init__(group_id, server, client, info_type)
        self.is_sim = True
        self.game_name = "prisoners_dilemma"
        self.config = {"timeout": 60, "default": {"action": "d", "response": 5}}


def get_game(group_id, server, client, info_type, game_name) -> BaseGame:
    if game_name == "prisoners_dilemma":
        return PrisonersDilemma(group_id, server, client, info_type)
    else:
        return BaseGame(group_id, server, client, info_type)
