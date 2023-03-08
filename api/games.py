from typing import List, Type, Dict

from api.models import Player, Game


class BaseGame:
    game_name = "base"
    game_id = 0
    config = {}

    def __init__(self, group_id, server, client, info_type):
        self.state = {}
        self.actions = []
        self.group_id = group_id
        self.server = server
        self.client = client
        self.info_type = info_type

    def update_state(self, event):
        event = event.copy()
        if event['sender'] == self.server.channel_name:
            event['sender'] = self.server.email
        else:
            event['sender'] = self.client.email

        actions = list(filter(lambda x: x['sender'] == event['sender'], self.actions))

        if len(actions) > 0:
            return

        self.actions.append(event)
        self.state[event['sender']] = event['data']

    def is_complete(self):
        return len(self.actions) == 2

    def get_state(self):
        return self.state

    def save(self):
        game = Game(
            server=self.server,
            client=self.client,
            state=self.state,
            actions=self.actions,
            info_type=self.info_type,
            group_id=self.group_id,
            game_name=self.game_name
        )
        game.save()

    def get_current_scores(self):
        return [0, 0]


class Intro(BaseGame):
    game_id = 1
    game_name = "intro"
    config = {"timeout": 150, "default": ""}

    def __init__(self, group_id, server, client, info_type):
        super(Intro, self).__init__(group_id, server, client, info_type)


class Restaurant(BaseGame):
    game_id = 2
    game_name = "restaurant"
    config = {"timeout": 120, "default": "low"}

    def __init__(self, group_id, server, client, info_type):
        super(Restaurant, self).__init__(group_id, server, client, info_type)

    def get_current_scores(self):
        ss, cs = 0, 0

        s_action = self.state[self.server.email]
        c_action = self.state[self.client.email]

        if s_action == 'high' and c_action == 'high':
            ss = 5
            cs = 5

        elif s_action == 'high' and c_action == 'low':
            ss = -2.5
            cs = 7.5

        if s_action == 'low' and c_action == 'high':
            ss = 7.5
            cs = -2.5

        elif s_action == 'low' and c_action == 'low':
            ss = 0
            cs = 0

        return [ss, cs]


class ATM(BaseGame):
    game_id = 3
    game_name = "atm"
    config = {"timeout": 120, "default": "dont"}

    def __init__(self, group_id, server, client, info_type):
        super(ATM, self).__init__(group_id, server, client, info_type)

    def get_current_scores(self):
        ss, cs = 0, 0

        s_action = self.state[self.server.email]
        c_action = self.state[self.client.email]

        if s_action == 'put':
            ss -= 3
            cs += 10
        elif s_action == 'dont':
            pass

        if c_action == 'put':
            cs -= 3
            ss += 10
        elif c_action == 'dont':
            pass

        return [ss, cs]


class Police(BaseGame):
    game_id = 4
    game_name = "police"
    config = {"timeout": 120, "default": "confess"}

    def __init__(self, group_id, server, client, info_type):
        super(Police, self).__init__(group_id, server, client, info_type)

    def get_current_scores(self):
        ss, cs = 0, 0

        s_action = self.state[self.server.email]
        c_action = self.state[self.client.email]

        if s_action == 'deny' and c_action == 'deny':
            ss -= 2.5
            cs -= 2.5

        elif s_action == 'deny' and c_action == 'confess':
            ss -= 7.5
            cs += 0

        if s_action == 'confess' and c_action == 'deny':
            ss += 0
            cs -= 7.5

        elif s_action == 'confess' and c_action == 'confess':
            ss -= 5
            cs -= 5

        return [ss, cs]


class Investment(BaseGame):
    game_name = "investment"
    game_id = 5
    config = {"timeout": 180, "default": 2.5}

    def __init__(self, group_id, server, client, info_type):
        super(Investment, self).__init__(group_id, server, client, info_type)

    def get_current_scores(self):
        s_action = self.state[self.server.email]
        c_action = self.state[self.client.email]

        ss = 5 - s_action + c_action
        cs = 3 * s_action - c_action

        return [ss, cs]


class Outro(BaseGame):
    game_id = 6
    game_name = "outro"
    config = {"timeout": 120, "default": {"trust": 5, "know": False}}

    def __init__(self, group_id, server, client, info_type):
        super(Outro, self).__init__(group_id, server, client, info_type)
        self.info_type = []


GAME_LIST: List[Type[BaseGame]] = [BaseGame, Intro, Restaurant, ATM, Police, Investment, Outro]

GAME_MAP: Dict[int, Type[BaseGame]] = {k.game_id: k for k in GAME_LIST}


def get_game(group_id, server, client, info_type, game_id) -> BaseGame:
    return GAME_MAP.get(game_id, BaseGame)(group_id, server, client, info_type)
