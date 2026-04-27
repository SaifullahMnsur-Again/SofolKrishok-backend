from django.db import models
from django.conf import settings


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
