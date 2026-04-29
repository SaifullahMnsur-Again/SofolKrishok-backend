from rest_framework import serializers
from .models import (
    LandParcel, LandParcelHistory, CropTrack, CropTrackHistory, CropStage,
    CropActivityLog, FarmingCycle, FarmingCycleHistory
)


class CropStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropStage
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class CropActivityLogSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.username', read_only=True)

    class Meta:
        model = CropActivityLog
        fields = [
            'id', 'track', 'activity_type', 'occurred_at', 'quantity', 'unit',
            'notes', 'metadata', 'recorded_by', 'recorded_by_name', 'created_at',
        ]
        read_only_fields = ['id', 'recorded_by', 'recorded_by_name', 'created_at']


class CropTrackSerializer(serializers.ModelSerializer):
    stages = CropStageSerializer(many=True, read_only=True)
    activity_logs = CropActivityLogSerializer(many=True, read_only=True)

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


class FarmingCycleHistorySerializer(serializers.ModelSerializer):
    modified_by_name = serializers.CharField(source='modified_by.username', read_only=True)

    class Meta:
        model = FarmingCycleHistory
        fields = [
            'id', 'cycle', 'action_type', 'summary', 'previous_values', 'current_values',
            'modified_by', 'modified_by_name', 'created_at',
        ]
        read_only_fields = ['id', 'cycle', 'modified_by', 'modified_by_name', 'created_at']


class FarmingCycleSerializer(serializers.ModelSerializer):
    history_entries = FarmingCycleHistorySerializer(many=True, read_only=True)

    class Meta:
        model = FarmingCycle
        fields = [
            'id', 'land', 'name', 'description', 'started_at', 'expected_end_at',
            'actual_end_at', 'status', 'soil_preparation_notes', 'expected_yield',
            'actual_yield', 'total_investment', 'total_revenue', 'notes', 'metadata',
            'history_entries', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'history_entries', 'created_at', 'updated_at']
