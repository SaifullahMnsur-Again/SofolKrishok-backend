from django.contrib import admin
from .models import (
    AIModelArtifact,
    AIServiceConfiguration,
    ChatSession,
    ChatMessage,
    DiseaseDetectionLog,
    SoilClassificationLog,
)

class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at', 'metadata')
    can_delete = False

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'land_parcel', 'message_count', 'created_at')
    search_fields = ('title', 'user__username')
    list_filter = ('created_at',)
    inlines = [ChatMessageInline]
    readonly_fields = ('summary', 'message_count')

@admin.register(DiseaseDetectionLog)
class DiseaseDetectionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'crop_type', 'predicted_class', 'confidence', 'created_at')
    list_filter = ('crop_type', 'created_at')
    search_fields = ('user__username', 'predicted_class')
    readonly_fields = ('predicted_class', 'confidence', 'all_predictions')

@admin.register(SoilClassificationLog)
class SoilClassificationLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'land_parcel', 'predicted_type', 'confidence', 'created_at')
    list_filter = ('predicted_type', 'created_at')
    search_fields = ('user__username', 'predicted_type')
    readonly_fields = ('predicted_type', 'confidence', 'all_predictions')


@admin.register(AIModelArtifact)
class AIModelArtifactAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'operation', 'crop_type', 'is_active', 'created_by', 'updated_at')
    list_filter = ('operation', 'crop_type', 'is_active')
    search_fields = ('display_name', 'notes', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AIServiceConfiguration)
class AIServiceConfigurationAdmin(admin.ModelAdmin):
    list_display = ('singleton_key', 'updated_at')
    readonly_fields = ('singleton_key', 'updated_at')
