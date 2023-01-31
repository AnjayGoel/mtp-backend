import uuid
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
    upi_id = models.CharField(name="upi_id", max_length=100)
    channel_name = None

    @staticmethod
    def get_if_exists(email):
        objs = Player.objects.filter(email=email)
        if objs.count() == 1:
            return objs.get()
        else:
            return None


class Game(models.Model):
    class InfoType(models.TextChoices):
        INFO = 'INFO'
        CHAT = 'CHAT'
        VIDEO = 'VIDEO'

    game_id = models.UUIDField(name="game_id", primary_key=True, default=uuid.uuid4)
    game_name = models.CharField(name="game_name", max_length=100)
    info_type = ArrayField(models.CharField(
        max_length=10,
        choices=InfoType.choices,
        default=InfoType.VIDEO,
    ), default=[InfoType.INFO, InfoType.CHAT, InfoType.VIDEO])

    group_id = models.CharField(name="group_id", max_length=100)
    server = models.ForeignKey(name="server", related_name="server", to=Player, on_delete=models.CASCADE)
    client = models.ForeignKey(name="client", related_name="client", to=Player, on_delete=models.CASCADE)

    created_at = models.DateTimeField(name="created_at", default=datetime.now)

    state = models.JSONField(name="state", default=dict)
    actions = models.JSONField(name="actions", default=dict)
