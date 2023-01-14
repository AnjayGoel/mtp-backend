from django.contrib.auth.models import User
from django.db import models


class Player(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.URLField(name="avatar")
    hall = models.CharField(name="hall", max_length=100)
    year = models.CharField(name="year", max_length=100)
    department = models.CharField(name="department", max_length=100)
