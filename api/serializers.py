from rest_framework import serializers

from api.models import Player


class PlayerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Player
        fields = ['username', 'email', 'hall', 'year', 'department']
