from rest_framework import serializers
from .models import LandParcel, LandParcelHistory, CropTrack, CropTrackHistory, CropStage


class CropStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropStage
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class CropTrackSerializer(serializers.ModelSerializer):
    stages = CropStageSerializer(many=True, read_only=True)

    class Meta:
        model = CropTrack
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class CropTrackHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CropTrackHistory
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class LandParcelSerializer(serializers.ModelSerializer):
    crop_tracks = CropTrackSerializer(many=True, read_only=True)

    class Meta:
        model = LandParcel
        fields = '__all__'
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']


class LandParcelMinimalSerializer(serializers.ModelSerializer):
    """Minimal version for dropdowns and lists."""
    class Meta:
        model = LandParcel
        fields = ['id', 'name', 'location', 'soil_type', 'area_acres']


class LandParcelHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LandParcelHistory
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
