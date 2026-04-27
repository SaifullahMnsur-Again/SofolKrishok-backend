from rest_framework import serializers
from .models import ChatSession, ChatMessage, DiseaseDetectionLog, SoilClassificationLog


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'metadata', 'created_at']
        read_only_fields = ['id', 'created_at']


class ChatSessionSerializer(serializers.ModelSerializer):
    message_count = serializers.ReadOnlyField()

    class Meta:
        model = ChatSession
        fields = [
            'id', 'title', 'land_parcel', 'is_active',
            'message_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.ReadOnlyField()

    class Meta:
        model = ChatSession
        fields = [
            'id', 'title', 'land_parcel', 'is_active',
            'message_count', 'messages', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatRequestSerializer(serializers.Serializer):
    """Incoming chat message from user."""
    session_id = serializers.IntegerField(required=False, help_text="Existing session ID. Omit to create new.")
    message = serializers.CharField(max_length=5000)
    land_id = serializers.IntegerField(required=False, help_text="Optional land parcel for context.")


class ChatResponseSerializer(serializers.Serializer):
    """Response from the AI assistant."""
    session_id = serializers.IntegerField()
    session_title = serializers.CharField()
    response = serializers.CharField()
    message_count = serializers.IntegerField()


class VoiceCommandSerializer(serializers.Serializer):
    """Text or audio-powered command input."""
    text = serializers.CharField(required=False, allow_blank=True)
    audio = serializers.FileField(required=False)


class WeatherForecastSerializer(serializers.Serializer):
    """Optional coordinates for weather lookup."""
    lat = serializers.FloatField(required=False)
    lon = serializers.FloatField(required=False)
    days = serializers.IntegerField(required=False, min_value=1, max_value=7)


class DiseaseDetectionSerializer(serializers.Serializer):
    """Request for disease detection."""
    image = serializers.ImageField()
    crop_type = serializers.ChoiceField(choices=['corn', 'potato', 'rice', 'wheat'])


class DiseaseDetectionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiseaseDetectionLog
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']


class SoilClassificationSerializer(serializers.Serializer):
    """Request for soil classification."""
    image = serializers.ImageField()
    land_id = serializers.IntegerField(required=False, help_text="Optional: update this land parcel's soil type")


class SoilClassificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoilClassificationLog
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']
