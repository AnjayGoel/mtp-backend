from datetime import datetime
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
from django.db import models


class Player(models.Model):
    email = models.EmailField(name="email", primary_key=True)
    name = models.CharField(name="name", max_length=100)
    avatar = models.URLField(name="avatar")
    hall = models.CharField(name="hall", max_length=100)
    year = models.CharField(name="year", max_length=100)
    department = models.CharField(name="department", max_length=100)

    @staticmethod
    def get_if_exists(email):
        objs = Player.objects.filter(email=email)
        if objs.count() == 1:
            return objs.get()
        else:
            return None


class Game(models.Model):
    class GameType(models.TextChoices):
        INFO = 'INFO'
        CHAT = 'CHAT'
        VIDEO = 'VIDEO'

    game_id = models.CharField(name="game_id", primary_key=True, max_length=10)
    player_one = models.ForeignKey(name="player_one", related_name="player_one", to=Player, on_delete=models.CASCADE)
    player_two = models.ForeignKey(name="player_two", related_name="player_two", to=Player, on_delete=models.CASCADE)
    created_at = models.DateTimeField(name="created_at", default=datetime.now)
    last_played = models.DateTimeField(name="last_played", default=datetime.now)
    state = models.JSONField(name="state", default=dict)
    finished = models.BooleanField(name="finished", default=False)
    game_type = ArrayField(models.CharField(
        max_length=10,
        choices=GameType.choices,
        default=GameType.VIDEO,
    ), default=[GameType.INFO, GameType.CHAT, GameType.VIDEO])
