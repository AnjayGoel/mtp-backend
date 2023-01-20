import logging

from django.contrib.auth.models import User
from google.auth.transport import requests
from google.oauth2 import id_token
from rest_framework import authentication
from rest_framework import exceptions
import environ

from api.models import Player

env = environ.Env()
environ.Env.read_env(".env")
log = logging.getLogger(__name__)


class GoogleJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        token = request.META.get('HTTP_AUTHORIZATION').split(" ")[1]
        if not token:
            exceptions.AuthenticationFailed('Invalid Token')
        try:
            info = id_token.verify_oauth2_token(token, requests.Request(), env('CLIENT_ID'))
            email = info['email']
            player = Player.objects.filter(email=email).get()
            return player, None
        except Exception as e:
            log.error(e)
            raise exceptions.AuthenticationFailed('User does not exist')
