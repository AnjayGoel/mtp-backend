from django.contrib.auth.models import User
from django.db import models


class Player(models.Model):
    name = models.CharField(name="name", max_length=100)
    email = models.EmailField(name="email")
    avatar = models.URLField(name="avatar")
    hall = models.CharField(name="hall", max_length=100)
    year = models.CharField(name="year", max_length=100)
    department = models.CharField(name="department", max_length=100)

    @staticmethod
    def get_if_exists(email):
        objs = Player.objects.filter(user__email=email)
        if objs.count() == 1:
            return objs.get()
        else:
            return None
