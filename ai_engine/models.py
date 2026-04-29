from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q


class ChatSession(models.Model):
    """
    Persistent chat session for a user.
    Optionally tied to a specific land parcel for context-aware AI responses.
    This is the foundation of the MEMORY SYSTEM.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    land_parcel = models.ForeignKey(
        'lms_farming.LandParcel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_sessions',
        help_text="Optional: link session to a specific land for context",
    )
    title = models.CharField(max_length=255, default="New Chat")
    is_active = models.BooleanField(default=True)
    summary = models.TextField(
        blank=True,
        help_text="Auto-generated summary of older messages for long conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_sessions'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} — {self.user.username}"

    @property
    def message_count(self):
        return self.messages.count()


class ChatMessage(models.Model):
    """
    Individual message in a chat session.
    This is the MEMORY — every user/assistant exchange is persisted here
    and replayed to Gemini on each new request to maintain context.
    """

    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant (Gemini)'
        SYSTEM = 'system', 'System'

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extra context: disease scan results, weather data, etc.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']

    def __str__(self):
        preview = self.content[:60] + '...' if len(self.content) > 60 else self.content
        return f"[{self.role}] {preview}"


class DiseaseDetectionLog(models.Model):
    """Log of disease detection predictions for analytics."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='disease_detections',
    )
    crop_type = models.CharField(max_length=50)
    image = models.ImageField(upload_to='disease_scans/')
    predicted_class = models.CharField(max_length=100)
    confidence = models.FloatField()
    all_predictions = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'disease_detection_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.crop_type}: {self.predicted_class} ({self.confidence:.1f}%)"


class SoilClassificationLog(models.Model):
    """Log of soil classification predictions."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='soil_classifications',
    )
    image = models.ImageField(upload_to='soil_scans/')
    predicted_type = models.CharField(max_length=100)
    confidence = models.FloatField()
    all_predictions = models.JSONField(default=dict)
    land_parcel = models.ForeignKey(
        'lms_farming.LandParcel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'soil_classification_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.predicted_type} ({self.confidence:.1f}%)"


class Crop(models.Model):
    """Canonical crop list used by the Model Hub for dropdowns.

    `english_name` is unique and used as the identifier shown in the UI.
    `bengali_name` stores the corresponding Bangla display name.
    """

    english_name = models.CharField(max_length=120, unique=True)
    bengali_name = models.CharField(max_length=120, blank=True)

    class Meta:
        db_table = 'crops'
        ordering = ['english_name']

    def save(self, *args, **kwargs):
        previous_english_name = None
        if self.pk:
            previous_english_name = Crop.objects.filter(pk=self.pk).values_list('english_name', flat=True).first()

        super().save(*args, **kwargs)

        if previous_english_name and previous_english_name != self.english_name:
            AIModelArtifact.objects.filter(crop_type=previous_english_name).update(crop_type=self.english_name)

    def delete(self, *args, **kwargs):
        AIModelArtifact.objects.filter(crop_type=self.english_name).update(is_active=False)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.english_name} ({self.bengali_name})" if self.bengali_name else self.english_name


class AIModelArtifact(models.Model):
    class Operation(models.TextChoices):
        DISEASE_DETECTION = 'disease_detection', 'Disease Detection'
        SOIL_CLASSIFICATION = 'soil_classification', 'Soil Classification'

    operation = models.CharField(max_length=32, choices=Operation.choices)
    crop_type = models.CharField(max_length=50, blank=True, null=True)
    # Canonical metadata fields requested by UI: model name and version
    model_name = models.CharField(max_length=255, blank=True, null=True)
    version = models.CharField(max_length=64, blank=True, null=True)
    display_name = models.CharField(max_length=255)
    # Legacy upload fields kept for backward compatibility.
    model_file = models.FileField(upload_to='ai_models/', blank=True, null=True)
    indices_file = models.FileField(upload_to='ai_models/', blank=True, null=True)
    # Relative filesystem paths used by the new model hub flow.
    model_path = models.CharField(max_length=500, blank=True, null=True)
    indices_path = models.CharField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ai_models',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_model_artifacts'
        ordering = ['operation', 'crop_type', '-is_active', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['operation', 'crop_type'],
                condition=Q(is_active=True),
                name='unique_active_ai_model_per_scope',
            ),
        ]

    def clean(self):
        super().clean()
        has_model = bool(self.model_path) or bool(self.model_file)
        if not has_model:
            raise ValidationError({'model_path': 'Model path is required.'})

        if self.operation == self.Operation.DISEASE_DETECTION:
            self.crop_type = (self.crop_type or '').strip() or None
            if not self.crop_type:
                raise ValidationError({'crop_type': 'Crop type is required for disease detection models.'})
            has_indices = bool(self.indices_path) or bool(self.indices_file)
            if not has_indices:
                raise ValidationError({'indices_path': 'Indices path is required for disease detection models.'})
        elif self.operation == self.Operation.SOIL_CLASSIFICATION:
            self.crop_type = None

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            if self.is_active:
                queryset = AIModelArtifact.objects.filter(operation=self.operation)
                queryset = queryset.filter(crop_type=self.crop_type)
                queryset.exclude(pk=self.pk).update(is_active=False)
            super().save(*args, **kwargs)

    def __str__(self):
        suffix = f" ({self.crop_type})" if self.crop_type else ''
        state = 'active' if self.is_active else 'inactive'
        return f"{self.display_name} - {self.get_operation_display()}{suffix} [{state}]"


class AIModelUsageHistory(models.Model):
    class Service(models.TextChoices):
        DISEASE_DETECTION = 'disease_detection', 'Disease Detection'
        SOIL_CLASSIFICATION = 'soil_classification', 'Soil Classification'
        GEMINI_CHAT = 'gemini_chat', 'Gemini Chat'
        VOICE_COMMAND = 'voice_command', 'Voice Command'
        WEATHER_FORECAST = 'weather_forecast', 'Weather Forecast'
        OTHER = 'other', 'Other'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='model_usage_history',
    )
    subscription = models.ForeignKey(
        'finance.Subscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='model_usage_history',
    )
    model_artifact = models.ForeignKey(
        AIModelArtifact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usage_history',
    )
    service_name = models.CharField(max_length=50, choices=Service.choices)
    operation = models.CharField(max_length=32, blank=True)
    model_identifier = models.CharField(max_length=255, blank=True)
    model_version = models.CharField(max_length=64, blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    user_role = models.CharField(max_length=30, blank=True)
    subscription_plan_name = models.CharField(max_length=100, blank=True)
    subscription_plan_type = models.CharField(max_length=20, blank=True)
    subscription_status = models.CharField(max_length=20, blank=True)
    request_metadata = models.JSONField(default=dict, blank=True)
    response_metadata = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_model_usage_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service_name', '-created_at']),
            models.Index(fields=['operation', '-created_at']),
            models.Index(fields=['user_role', '-created_at']),
        ]

    def __str__(self):
        model_name = self.model_identifier or (self.model_artifact.display_name if self.model_artifact else 'unknown')
        return f"{self.get_service_name_display()} — {model_name} @ {self.created_at:%Y-%m-%d %H:%M}"


class AIServiceConfiguration(models.Model):
    """Singleton store for AI service settings such as the Gemini API key."""

    singleton_key = models.CharField(max_length=20, unique=True, default='default', editable=False)
    gemini_api_key = models.TextField(blank=True, help_text='Stored Gemini API key used by the AI assistant.')
    gemini_model = models.CharField(max_length=120, blank=True)
    gemini_secondary_model = models.CharField(max_length=120, blank=True)
    gemini_tertiary_model = models.CharField(max_length=120, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_service_configuration'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(singleton_key='default')
        return obj

    def __str__(self):
        return 'AI service configuration'
