from django.contrib.auth.models import User
from google.auth.transport import requests
from google.oauth2 import id_token
from rest_framework import authentication
from rest_framework import exceptions
import environ

env = environ.Env()
environ.Env.read_env(".env")


class GoogleJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        token = request.META.get('HTTP_AUTHORIZATION').split(" ")[1]
        if not token:
            exceptions.AuthenticationFailed('Invalid Token')

        try:
            info = id_token.verify_oauth2_token(token, requests.Request(), env('CLIENT_ID'))

            email = info['email']
            user = User.objects.filter(email=email).get()
            return user, None
        except ValueError:
            raise exceptions.AuthenticationFailed('Invalid Token')
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User does not exist')
