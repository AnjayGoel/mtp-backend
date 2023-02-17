from typing import List

from api.models import Player, Game


class BaseGame:
    state = {}
    actions = []
    server: Player = None
    client: Player = None
    info_type: List[Game.InfoType] = None
    group_id = None
    is_sim = False
    game_name = None
    config = None
    game_id = 0

    def __init__(self, group_id, server, client, info_type):
        self.server = server
        self.client = client
        self.info_type = info_type
        self.group_id = group_id
        self.game_name = "base"
        self.state = {}
        self.actions = []
        self.config = {}

    def update_state(self, event):
        event = event.copy()
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
    def __init__(self, group_id, server, client, info_type):
        super(Intro, self).__init__(group_id, server, client, info_type)
        self.is_sim = True
        self.game_name = "intro"
        self.game_id = 1
        self.config = {"timeout": 150, "default": ""}


class Machine(BaseGame):
    def __init__(self, group_id, server, client, info_type):
        super(Machine, self).__init__(group_id, server, client, info_type)
        self.is_sim = True
        self.game_name = "machine"
        self.game_id = 2
        self.config = {"timeout": 120, "default": "dont"}

    def get_current_scores(self):
        ss, cs = 0, 0

        s_action = self.state[self.server.email]
        c_action = self.state[self.client.email]

        if s_action == 'put':
            ss -= 5
            cs += 15
        elif s_action == 'dont':
            pass

        if c_action == 'put':
            cs -= 5
            ss += 15
        elif c_action == 'dont':
            pass

        return [ss, cs]


class PrisonersDilemma(BaseGame):
    def __init__(self, group_id, server, client, info_type):
        super(PrisonersDilemma, self).__init__(group_id, server, client, info_type)
        self.is_sim = True
        self.game_name = "prisoners_dilemma"
        self.game_id = 3
        self.config = {"timeout": 120, "default": "confess"}

    def get_current_scores(self):
        ss, cs = 0, 0

        s_action = self.state[self.server.email]
        c_action = self.state[self.client.email]

        if s_action == 'deny' and c_action == 'deny':
            ss -= 5
            cs -= 5

        elif s_action == 'deny' and c_action == 'confess':
            ss -= 20
            cs += 0

        if s_action == 'confess' and c_action == 'deny':
            ss += 0
            cs -= 20

        elif s_action == 'confess' and c_action == 'confess':
            ss -= 10
            cs -= 10

        return [ss, cs]


class TrustGame(BaseGame):
    def __init__(self, group_id, server, client, info_type):
        super(TrustGame, self).__init__(group_id, server, client, info_type)
        self.is_sim = True
        self.game_name = "trust_game"
        self.game_id = 4
        self.config = {"timeout": 180, "default": 5}

    def get_current_scores(self):
        s_action = self.state[self.server.email]
        c_action = self.state[self.client.email]

        ss = 10 - s_action + c_action
        cs = 3 * s_action - c_action

        return [ss, cs]


class Outro(BaseGame):
    def __init__(self, group_id, server, client, info_type):
        super(Outro, self).__init__(group_id, server, client, info_type)
        self.is_sim = True
        self.game_name = "outro"
        self.game_id = 5
        self.info_type = []
        self.config = {"timeout": 120, "default": {"trust": 5, "know": False}}


GAME_MAP = {
    0: BaseGame,
    1: Intro,
    2: Machine,
    3: PrisonersDilemma,
    4: TrustGame,
    5: Outro
}


def get_game(group_id, server, client, info_type, game_id) -> BaseGame:
    if game_id in GAME_MAP:
        return GAME_MAP[game_id](group_id, server, client, info_type)
    else:
        return BaseGame(group_id, server, client, info_type)
