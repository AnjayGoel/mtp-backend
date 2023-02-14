import json
import os
import random
import string

from google.auth.transport import requests
from google.oauth2 import id_token


def get_user_info(request):
    if isinstance(request, str):
        token = request
    else:
        token = request.META.get('HTTP_AUTHORIZATION').split(" ")[1]
    if not token:
        return None

    try:
        return id_token.verify_oauth2_token(token, requests.Request(), os.environ['CLIENT_ID'])
    except Exception as e:
        return None


def random_str():
    return ''.join(random.choices(string.ascii_lowercase, k=10))


def dumps(data):
    return json.dumps(data, indent=4, default=lambda __o: str(__o.__dict__)) + f"\n{'-' * 10}\n"
