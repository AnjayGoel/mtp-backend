from google.auth.transport import requests
from google.oauth2 import id_token
import environ

env = environ.Env()
environ.Env.read_env(".env")


def get_user_info(request):
    token = request.META.get('HTTP_AUTHORIZATION').split(" ")[1]
    if not token:
        return None

    try:
        return id_token.verify_oauth2_token(token, requests.Request(), env('CLIENT_ID'))
    except Exception:
        return None
