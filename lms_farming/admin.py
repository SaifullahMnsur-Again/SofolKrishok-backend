from django.contrib import admin
from .models import LandParcel, LandParcelHistory, CropTrack, CropTrackHistory, CropStage

@admin.register(LandParcel)
class LandParcelAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'area_acres', 'soil_type')
    list_filter = ('soil_type',)
    search_fields = ('name', 'owner__username', 'location')

@admin.register(CropTrack)
class CropTrackAdmin(admin.ModelAdmin):
    list_display = ('id', 'land', 'crop_name', 'season', 'status')
    list_filter = ('status', 'season')
    search_fields = ('crop_name', 'land__name')


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
