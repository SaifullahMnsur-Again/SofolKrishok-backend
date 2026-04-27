from django.contrib import admin
from .models import ChatSession, ChatMessage, DiseaseDetectionLog, SoilClassificationLog

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
