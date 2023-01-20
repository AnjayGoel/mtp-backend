from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from api.authentication import GoogleJWTAuthentication
from api.models import Player
from api.utils import get_user_info


@api_view(['GET'])
@authentication_classes([GoogleJWTAuthentication])
def get(request):
    return Response(data={"status": 200})


@api_view(['GET'])
@authentication_classes([])
def check(request):
    user_info = get_user_info(request)
    return Response(data={"exists": Player.objects.filter(email=user_info['email']).count() == 1})


@api_view(["POST"])
@authentication_classes([])
def create(request):
    user_info = get_user_info(request)

    player = Player.objects.filter(email=user_info["email"])
    if player.count() != 0:
        return Response(status=400, data={"message": "User already exists"})

    player = Player(
        email=user_info["email"],
        name=user_info["name"],
        avatar=user_info["picture"],
        hall=request.data["hall"],
        year=request.data["year"],
        department=request.data["department"]
    )
    player.save()

    return Response(status=200)
