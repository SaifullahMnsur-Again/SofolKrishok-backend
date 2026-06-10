from django.contrib import admin
from .models import (
    LandParcel, LandParcelHistory, CropTrack, CropTrackHistory, CropStage, CropActivityLog,
    FarmingCycle, FarmingCycleHistory, CropType
)

@admin.action(description="Merge selected into the first selected crop")
def merge_crops(modeladmin, request, queryset):
    crops = list(queryset)
    if len(crops) < 2: 
        modeladmin.message_user(request, "Please select at least two crops to merge.", level="ERROR")
        return
    
    target = crops[0]
    merged_count = 0
    for crop in crops[1:]:
        # Update foreign keys safely
        LandParcel.objects.filter(default_crop=crop).update(default_crop=target)
        CropTrack.objects.filter(crop=crop).update(crop=target)
        from ai_engine.models import AIModelArtifact
        AIModelArtifact.objects.filter(crop=crop).update(crop=target)
        
        # Mark as merged
        crop.merged_into = target
        crop.is_approved = False
        crop.is_public = False
        crop.save()
        merged_count += 1
        
    modeladmin.message_user(request, f"Successfully merged {merged_count} crops into '{target.name_en}'.")

@admin.register(CropType)
class CropTypeAdmin(admin.ModelAdmin):
    list_display = ('name_en', 'name_bn', 'is_public', 'is_approved', 'suggested_by', 'merged_into', 'created_at')
    list_filter = ('is_public', 'is_approved', 'created_at')
    search_fields = ('name_en', 'name_bn')
    actions = [merge_crops]

@admin.register(LandParcel)
class LandParcelAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'area_acres', 'soil_type')
    list_filter = ('soil_type',)
    search_fields = ('name', 'owner__username', 'location')

@admin.register(CropTrack)
class CropTrackAdmin(admin.ModelAdmin):
    list_display = ('id', 'land', 'crop', 'season', 'status')
    list_filter = ('status', 'season')
    search_fields = ('crop__name_en', 'land__name')


@admin.register(CropActivityLog)
class CropActivityLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'activity_type', 'track', 'occurred_at', 'quantity', 'unit', 'recorded_by')
    list_filter = ('activity_type', 'occurred_at')
    search_fields = ('track__crop_name', 'track__land__name', 'notes', 'recorded_by__username')


@admin.register(CropTrackHistory)
class CropTrackHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'track', 'action_type', 'summary', 'created_at')
    list_filter = ('action_type', 'created_at')
    search_fields = ('track__crop_name', 'track__land__name', 'summary')

@admin.register(CropStage)
class CropStageAdmin(admin.ModelAdmin):
    list_display = ('title', 'track', 'started_at', 'completed_at', 'is_current')
    list_filter = ('is_current',)
    search_fields = ('title', 'track__crop_name')


@admin.register(LandParcelHistory)
class LandParcelHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'land', 'action_type', 'summary', 'created_at')
    list_filter = ('action_type', 'created_at')
    search_fields = ('land__name', 'summary')


@admin.register(FarmingCycle)
class FarmingCycleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'land', 'started_at', 'status', 'expected_yield', 'actual_yield')
    list_filter = ('status', 'started_at')
    search_fields = ('name', 'land__name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FarmingCycleHistory)
class FarmingCycleHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'cycle', 'action_type', 'summary', 'modified_by', 'created_at')
    list_filter = ('action_type', 'created_at')
    search_fields = ('cycle__name', 'cycle__land__name', 'summary', 'modified_by__username')
    readonly_fields = ('cycle', 'action_type', 'summary', 'previous_values', 'current_values', 'modified_by', 'created_at')
