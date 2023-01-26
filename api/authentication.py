import logging
import os

from google.auth.transport import requests
from google.oauth2 import id_token
from rest_framework import authentication
from rest_framework import exceptions

from api.models import Player

log = logging.getLogger(__name__)


class GoogleJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        header = request.META.get('HTTP_AUTHORIZATION')

        if header is None:
            raise exceptions.AuthenticationFailed("No Token Provided")

        token = header.split(" ")[1]
        try:
            info = id_token.verify_oauth2_token(token, requests.Request(), os.environ['CLIENT_ID'])
            return info, None
        except Exception as e:
            log.error(e)
            raise exceptions.AuthenticationFailed('User does not exist')
