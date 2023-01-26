from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from api.authentication import GoogleJWTAuthentication
from api.models import Player
from api.serializers import PlayerSerializer
from api.utils import get_user_info


@api_view(['GET'])
@authentication_classes([])
def status(request):
    return Response(data={"status": 200})


@api_view(['GET'])
@authentication_classes([])
def get_user(request):
    user_info = get_user_info(request)
    if user_info is None:
        return Response(data={"exists": False, "data": None})
    else:
        player_query = Player.objects.filter(email=user_info['email'])
        exists = player_query.count() == 1
        data = None
        if exists:
            data = PlayerSerializer(player_query.get()).data

        return Response(data={
            "exists": exists,
            "profile": data
        })


@api_view(["POST"])
@authentication_classes([GoogleJWTAuthentication, ])
def signup_or_update(request):
    user_info = get_user_info(request)

    """
    # player = Player.objects.filter(email=user_info["email"])
    # if player.count() != 0:
    #    return Response(status=400, data={"message": "User already exists"})

    player = Player(
        email=user_info["email"],
        name=user_info["name"],
        avatar=user_info["picture"],
        hall=request.data["hall"],
        year=request.data["year"],
        department=request.data["department"],
        upi_id=request.data["upi_id"]
    )
    player.save()
    """
    Player.objects.update_or_create(
        email=user_info["email"],
        defaults={
            'name': user_info["name"],
            'avatar': user_info["picture"],
            'hall': request.data["hall"],
            'year': request.data["year"],
            'department': request.data["department"],
            'upi_id': request.data["upi_id"]
        }
    )

    return Response(status=200)
