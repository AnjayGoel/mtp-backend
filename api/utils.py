import random
import string

import environ
from google.auth.transport import requests
from google.oauth2 import id_token

env = environ.Env()
environ.Env.read_env(".env")


def get_user_info(request):
    if isinstance(request, str):
        token = request
    else:
        token = request.META.get('HTTP_AUTHORIZATION').split(" ")[1]
    if not token:
        return None

    try:
        return id_token.verify_oauth2_token(token, requests.Request(), env('CLIENT_ID'))
    except Exception as e:
        return None


def random_str():
    return ''.join(random.choices(string.ascii_lowercase, k=6))
