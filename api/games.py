games = ["prisoners_dilemma"]


class GameType:
    SEQ = "SEQ"
    SIM = "SIM"


class BaseGame:
    state = []
    game_type = None
    player_one = None
    player_two = None
    info_type = None
    server = None
    group_id = None

    def __init__(self, group_id, game_type, player_one, player_two, server, info_type):
        self.game_type = game_type
        self.player_one = player_one
        self.player_two = player_two
        self.info_type = info_type
        self.server = server
        self.group_id = group_id
        self.game_type= GameType.SIM

    def update_state(self, event):
        if self.game_type == GameType.SIM:
            events = list(filter(lambda x: x['player'] != event['player'], self.state))
            if len(events) > 0:
                return
        self.state.append(event)

    def is_complete(self):
        if self.game_type == GameType.SIM and len(self.state) == 2:
            return True

    def get_state(self):
        return self.state


def get_game(group_id,game_type, player_one, player_two, server, info_type) -> BaseGame:
    return BaseGame(group_id,game_type, player_one, player_two, server, info_type)
