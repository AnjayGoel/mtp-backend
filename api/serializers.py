from rest_framework import serializers

from api.models import Player, Game


class PlayerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Player
        fields = ['name', 'email', 'avatar', 'hall', 'year', 'department', 'upi_id']


class GameSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Game
        fields = ['game_id', 'player_one', 'player_two', 'created_at', 'last_played', 'state', 'finished', 'game_type']
