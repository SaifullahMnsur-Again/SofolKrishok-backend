from pathlib import Path

from django.conf import settings
from django.utils.text import slugify
from rest_framework import serializers
from .models import (
    AIModelArtifact,
    AIModelUsageHistory,
    Crop,
    AIServiceConfiguration,
    ChatSession,
    ChatMessage,
    DiseaseDetectionLog,
    SoilClassificationLog,
)


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
    # Accept any crop_type string — validation is handled by the disease_service
    # which looks up the active AIModelArtifact from the database.
    crop_type = serializers.CharField(max_length=120)


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


class AIModelUsageHistorySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    model_display_name = serializers.CharField(source='model_artifact.display_name', read_only=True)
    crop_type = serializers.CharField(source='model_artifact.crop_type', read_only=True)
    model_operation = serializers.CharField(source='model_artifact.operation', read_only=True)

    class Meta:
        model = AIModelUsageHistory
        fields = [
            'id',
            'service_name',
            'operation',
            'model_identifier',
            'model_version',
            'model_display_name',
            'crop_type',
            'model_operation',
            'username',
            'user_email',
            'user_role',
            'subscription_plan_name',
            'subscription_plan_type',
            'subscription_status',
            'request_path',
            'request_metadata',
            'response_metadata',
            'confidence',
            'success',
            'error_message',
            'response_time_ms',
            'ip_address',
            'user_agent',
            'created_at',
        ]
        read_only_fields = fields


class AIModelArtifactSerializer(serializers.ModelSerializer):
    model_file = serializers.FileField(write_only=True, required=False, allow_null=True)
    indices_file = serializers.FileField(write_only=True, required=False, allow_null=True)
    model_name = serializers.CharField(required=False, allow_blank=True)
    version = serializers.CharField(required=False, allow_blank=True)
    crop_name_english = serializers.SerializerMethodField()
    crop_name_bengali = serializers.SerializerMethodField()
    model_file_name = serializers.SerializerMethodField()
    indices_file_name = serializers.SerializerMethodField()
    model_file_size = serializers.SerializerMethodField()
    indices_file_size = serializers.SerializerMethodField()
    total_size_bytes = serializers.SerializerMethodField()
    model_file_url = serializers.SerializerMethodField()
    indices_file_url = serializers.SerializerMethodField()

    class Meta:
        model = AIModelArtifact
        fields = [
            'id', 'operation', 'crop_type', 'crop_name_english', 'crop_name_bengali', 'display_name', 'model_file', 'model_file_name', 'model_file_size', 'model_path',
            'model_name', 'version',
            'model_file_url', 'indices_file', 'indices_file_name', 'indices_file_size', 'indices_file_url',
            'indices_path', 'total_size_bytes',
            'is_active', 'notes', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'created_by', 'created_at', 'updated_at',
            'crop_name_english', 'crop_name_bengali',
            'model_file_name', 'indices_file_name', 'model_file_size', 'indices_file_size', 'total_size_bytes',
            'model_file_url', 'indices_file_url',
            'model_path', 'indices_path',
        ]

    def get_crop_name_english(self, obj):
        return obj.crop_type

    def get_crop_name_bengali(self, obj):
        if not obj.crop_type:
            return None
        crop = Crop.objects.filter(english_name=obj.crop_type).only('bengali_name').first()
        return crop.bengali_name if crop else None

    def get_model_file_name(self, obj):
        return self._name_from_path(obj.model_path, obj.model_file)

    def get_indices_file_name(self, obj):
        return self._name_from_path(obj.indices_path, obj.indices_file)

    def get_model_file_size(self, obj):
        return self._size_from_path(obj.model_path, obj.model_file)

    def get_indices_file_size(self, obj):
        return self._size_from_path(obj.indices_path, obj.indices_file)

    def get_total_size_bytes(self, obj):
        return (self.get_model_file_size(obj) or 0) + (self.get_indices_file_size(obj) or 0)

    @staticmethod
    def _name_from_path(relative_path, legacy_file):
        if relative_path:
            return Path(str(relative_path)).name
        if legacy_file:
            return Path(str(getattr(legacy_file, 'name', ''))).name or None
        return None

    @staticmethod
    def _size_from_path(relative_path, legacy_file):
        if relative_path:
            abs_path = Path(settings.BASE_DIR) / str(relative_path)
            try:
                return abs_path.stat().st_size
            except OSError:
                return None
        if legacy_file:
            return getattr(legacy_file, 'size', None)
        return None

    def get_model_file_url(self, obj):
        if obj.model_path:
            return obj.model_path
        request = self.context.get('request')
        try:
            if obj.model_file and hasattr(obj.model_file, 'url'):
                return request.build_absolute_uri(obj.model_file.url) if request else obj.model_file.url
        except Exception:
            return None
        return None

    def get_indices_file_url(self, obj):
        if obj.indices_path:
            return obj.indices_path
        request = self.context.get('request')
        try:
            if obj.indices_file and hasattr(obj.indices_file, 'url'):
                return request.build_absolute_uri(obj.indices_file.url) if request else obj.indices_file.url
        except Exception:
            return None
        return None

    @staticmethod
    def _write_uploaded_file(uploaded_file, target_path: Path):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open('wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

    def _store_model_files(self, instance, model_upload, indices_upload, crop_type, display_name):
        """Store model files to relative paths."""
        # Prefer explicit model_name/version when provided, fall back to display_name
        model_name_val = instance.model_name or display_name
        version_val = instance.version or 'v1'

        name_slug = slugify(model_name_val or '')
        version_slug = slugify(version_val or '')
        if not name_slug:
            raise serializers.ValidationError({'model_name': 'Model name is required.'})

        base_dir = Path(settings.BASE_DIR)

        if instance.operation == AIModelArtifact.Operation.DISEASE_DETECTION:
            crop_slug = slugify(crop_type or '')
            if not crop_slug:
                raise serializers.ValidationError({'crop_type': 'Crop name is required.'})
            crop = Crop.objects.filter(english_name__iexact=crop_type).only('english_name').first()
            if not crop:
                raise serializers.ValidationError({'crop_type': 'Please add this crop first in the Crop section, then choose it for the model.'})
            instance.crop_type = crop.english_name
            model_dir = base_dir / 'ml_models' / 'disease_detection' / crop_slug
            file_stem = f"{crop_slug}_{name_slug}_{version_slug}"
        elif instance.operation == AIModelArtifact.Operation.SOIL_CLASSIFICATION:
            instance.crop_type = None
            model_dir = base_dir / 'ml_models' / 'soil_classification'
            file_stem = f"{name_slug}_{version_slug}"
        else:
            crop_slug = slugify(crop_type or '')
            if not crop_slug:
                raise serializers.ValidationError({'crop_type': 'Crop name is required.'})
            instance.crop_type = crop_type
            model_dir = base_dir / 'ml_models' / 'models' / crop_slug
            file_stem = f"{crop_slug}_{name_slug}_{version_slug}"

        if model_upload is not None:
            model_ext = Path(model_upload.name).suffix or '.h5'
            model_abs_path = model_dir / f"{file_stem}_model{model_ext}"
            self._write_uploaded_file(model_upload, model_abs_path)
            instance.model_path = model_abs_path.relative_to(base_dir).as_posix()

        if indices_upload is not None:
            indices_ext = Path(indices_upload.name).suffix or '.txt'
            indices_abs_path = model_dir / f"{file_stem}_indices{indices_ext}"
            self._write_uploaded_file(indices_upload, indices_abs_path)
            instance.indices_path = indices_abs_path.relative_to(base_dir).as_posix()

        if not instance.model_path:
            raise serializers.ValidationError({'model_file': 'Please upload a model file.'})
        # Disease detection and soil classification both require indices file in this hub
        if instance.operation in {
            AIModelArtifact.Operation.DISEASE_DETECTION,
            AIModelArtifact.Operation.SOIL_CLASSIFICATION,
        } and not instance.indices_path:
            raise serializers.ValidationError({'indices_file': 'Please upload an indices file.'})

    def create(self, validated_data):
        model_upload = validated_data.pop('model_file', None)
        indices_upload = validated_data.pop('indices_file', None)
        # Accept model_name/version passed in top-level data
        model_name = validated_data.get('model_name')
        version = validated_data.get('version')

        instance = AIModelArtifact(**validated_data)
        if model_name:
            instance.model_name = model_name
        if version:
            instance.version = version
        self._store_model_files(
            instance,
            model_upload=model_upload,
            indices_upload=indices_upload,
            crop_type=validated_data.get('crop_type'),
            display_name=validated_data.get('display_name'),
        )
        instance.save()
        return instance

    def update(self, instance, validated_data):
        model_upload = validated_data.pop('model_file', None)
        indices_upload = validated_data.pop('indices_file', None)

        # Apply simple scalar updates first
        for key, value in validated_data.items():
            setattr(instance, key, value)

        # update model_name/version if present
        if 'model_name' in validated_data:
            instance.model_name = validated_data.get('model_name')
        if 'version' in validated_data:
            instance.version = validated_data.get('version')

        self._store_model_files(
            instance,
            model_upload=model_upload,
            indices_upload=indices_upload,
            crop_type=instance.crop_type,
            display_name=instance.display_name,
        )
        instance.save()
        return instance


class AIServiceConfigurationSerializer(serializers.ModelSerializer):
    gemini_api_key = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    gemini_api_key_present = serializers.SerializerMethodField(read_only=True)
    gemini_api_key_preview = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AIServiceConfiguration
        fields = [
            'gemini_api_key',
            'gemini_api_key_present',
            'gemini_api_key_preview',
            'gemini_model',
            'gemini_secondary_model',
            'gemini_tertiary_model',
            'updated_at',
        ]
        read_only_fields = ['gemini_api_key_present', 'gemini_api_key_preview', 'updated_at']

    def get_gemini_api_key_present(self, obj):
        return bool(obj.gemini_api_key)

    def get_gemini_api_key_preview(self, obj):
        if not obj.gemini_api_key:
            return ''
        if len(obj.gemini_api_key) <= 8:
            return '********'
        return f"{obj.gemini_api_key[:4]}...{obj.gemini_api_key[-4:]}"

    def update(self, instance, validated_data):
        gemini_api_key = validated_data.pop('gemini_api_key', None)
        if gemini_api_key is not None:
            instance.gemini_api_key = gemini_api_key.strip()
        return super().update(instance, validated_data)


class CropSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = ['id', 'english_name', 'bengali_name']
        read_only_fields = ['id']
