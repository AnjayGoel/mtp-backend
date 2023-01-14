from django.contrib.auth.models import User
from rest_framework import permissions
from rest_framework import viewsets
from rest_framework.decorators import api_view, authentication_classes, action
from rest_framework.response import Response
from rest_framework.views import APIView

from api.authentication import GoogleJWTAuthentication
from api.models import Player
from api.serializers import PlayerSerializer
from api.utils import get_user_info


class PlayerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    authentication_classes = [GoogleJWTAuthentication, ]

    def create(self, request):
        user_info = get_user_info(request)
        user = User(
            email=user_info["email"],
            username=user_info["name"]
        ).save()
        player = Player(user=user, hall=request.data["hall"], year=request.data["year"])
        player.save()

    @action(detail=False, methods=['get'], url_path="check")
    def check(self, request, pk=None):
        print("HERE")
        user_info = get_user_info(request)
        return Response(data={"exists": self.queryset.filter(user__email=user_info['email']).count() == 1})


@api_view(['GET'])
@authentication_classes([GoogleJWTAuthentication])
def get(request):
    return Response(data={"status": 200})
