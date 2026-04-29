from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from .models import (
    LandParcel, LandParcelHistory, CropTrack, CropTrackHistory, CropStage, CropActivityLog,
    FarmingCycle, FarmingCycleHistory
)
from ai_engine.weather_service import get_weather_forecast
from .serializers import (
    LandParcelSerializer,
    LandParcelMinimalSerializer,
    LandParcelHistorySerializer,
    CropTrackSerializer,
    CropTrackHistorySerializer,
    CropStageSerializer,
    CropActivityLogSerializer,
    FarmingCycleSerializer,
    FarmingCycleHistorySerializer,
)


LAND_HISTORY_FIELDS = ('name', 'location', 'latitude', 'longitude', 'area_acres', 'soil_type', 'notes')


def _serialize_land_snapshot(land):
    return {
        'name': land.name,
        'location': land.location,
        'latitude': str(land.latitude) if land.latitude is not None else None,
        'longitude': str(land.longitude) if land.longitude is not None else None,
        'area_acres': str(land.area_acres) if land.area_acres is not None else None,
        'soil_type': land.soil_type,
        'notes': land.notes,
    }


def _build_land_change_summary(changed_fields):
    readable = {
        'name': 'name',
        'location': 'location',
        'latitude': 'latitude',
        'longitude': 'longitude',
        'area_acres': 'area acres',
        'soil_type': 'soil type',
        'notes': 'notes',
    }
    labels = [readable[field] for field in changed_fields if field in readable]
    if not labels:
        return 'Land details updated'
    if len(labels) == 1:
        return f"Updated {labels[0]}"
    return f"Updated {', '.join(labels[:-1])} and {labels[-1]}"


class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        if hasattr(obj, 'land'):
            return obj.land.owner == request.user
        if hasattr(obj, 'track'):
            return obj.track.land.owner == request.user
        return False


class FarmingWeatherSerializer(serializers.Serializer):
    lat = serializers.FloatField(required=False)
    lon = serializers.FloatField(required=False)
    days = serializers.IntegerField(required=False, min_value=1, max_value=7)


@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='history', decorator=swagger_auto_schema(tags=['Farming']))
class LandParcelViewSet(viewsets.ModelViewSet):
    serializer_class = LandParcelSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return LandParcel.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        land = serializer.save(owner=self.request.user)
        LandParcelHistory.objects.create(
            land=land,
            action_type=LandParcelHistory.Action.CREATED,
            summary='Land parcel registered',
            current_values=_serialize_land_snapshot(land),
        )

    def perform_update(self, serializer):
        land = self.get_object()
        previous_values = _serialize_land_snapshot(land)
        updated_land = serializer.save()
        current_values = _serialize_land_snapshot(updated_land)

        changed_fields = [field for field in LAND_HISTORY_FIELDS if previous_values.get(field) != current_values.get(field)]
        if changed_fields:
            LandParcelHistory.objects.create(
                land=updated_land,
                action_type=LandParcelHistory.Action.UPDATED,
                summary=_build_land_change_summary(changed_fields),
                previous_values=previous_values,
                current_values=current_values,
            )

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """GET /api/lands/{id}/history/ — Full crop and land history of a parcel."""
        land = self.get_object()
        tracks = CropTrack.objects.filter(land=land).prefetch_related('stages', 'history_entries')
        cycle_history = CropTrackHistory.objects.filter(track__land=land).select_related('track', 'track__land')
        activity_history = CropActivityLog.objects.filter(track__land=land).select_related('track', 'track__land', 'recorded_by')
        return Response({
            'land': LandParcelSerializer(land).data,
            'crop_history': CropTrackSerializer(tracks, many=True).data,
            'cycle_history': CropTrackHistorySerializer(cycle_history, many=True).data,
            'activity_history': CropActivityLogSerializer(activity_history, many=True).data,
            'land_history': LandParcelHistorySerializer(land.history_entries.all(), many=True).data,
        })


@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Farming']))
class CropTrackViewSet(viewsets.ModelViewSet):
    serializer_class = CropTrackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CropTrack.objects.filter(land__owner=self.request.user).select_related('land').prefetch_related('stages', 'activity_logs')

    def _track_snapshot(self, track):
        return {
            'land_id': track.land_id,
            'land_name': track.land.name,
            'crop_name': track.crop_name,
            'season': track.season,
            'status': track.status,
            'planted_date': str(track.planted_date) if track.planted_date else None,
            'expected_harvest_date': str(track.expected_harvest_date) if track.expected_harvest_date else None,
            'actual_harvest_date': str(track.actual_harvest_date) if track.actual_harvest_date else None,
            'notes': track.notes,
        }

    def perform_create(self, serializer):
        track = serializer.save()
        CropTrackHistory.objects.create(
            track=track,
            action_type=CropTrackHistory.Action.CREATED,
            summary='Farming cycle enrolled',
            current_values=self._track_snapshot(track),
        )

    def perform_update(self, serializer):
        track = self.get_object()
        previous_values = self._track_snapshot(track)
        updated_track = serializer.save()
        current_values = self._track_snapshot(updated_track)
        changed_fields = [key for key, value in current_values.items() if previous_values.get(key) != value]
        if changed_fields:
            CropTrackHistory.objects.create(
                track=updated_track,
                action_type=CropTrackHistory.Action.UPDATED,
                summary='Farming cycle updated',
                previous_values=previous_values,
                current_values=current_values,
            )

    @action(detail=True, methods=['get', 'post'])
    def activities(self, request, pk=None):
        track = self.get_object()

        if request.method == 'GET':
            serializer = CropActivityLogSerializer(track.activity_logs.all(), many=True)
            return Response({'results': serializer.data})

        serializer = CropActivityLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        previous_values = self._track_snapshot(track)
        activity = serializer.save(track=track, recorded_by=request.user)

        if activity.activity_type == CropActivityLog.ActivityType.HARVEST:
            track.actual_harvest_date = activity.occurred_at.date()
            if track.status not in {CropTrack.Status.HARVESTED, CropTrack.Status.COMPLETED}:
                track.status = CropTrack.Status.HARVESTED
            track.save(update_fields=['actual_harvest_date', 'status', 'updated_at'])

        CropTrackHistory.objects.create(
            track=track,
            action_type=CropTrackHistory.Action.UPDATED,
            summary=f"Logged {activity.get_activity_type_display().lower()} activity",
            previous_values=previous_values,
            current_values={
                **self._track_snapshot(track),
                'last_activity': {
                    'type': activity.activity_type,
                    'occurred_at': activity.occurred_at.isoformat(),
                    'notes': activity.notes,
                },
            },
        )

        return Response(CropActivityLogSerializer(activity).data, status=status.HTTP_201_CREATED)


@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Farming']))
class CropStageViewSet(viewsets.ModelViewSet):
    serializer_class = CropStageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CropStage.objects.filter(track__land__owner=self.request.user)


@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Farming']))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Farming']))
class FarmingCycleViewSet(viewsets.ModelViewSet):
    serializer_class = FarmingCycleSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return FarmingCycle.objects.filter(land__owner=self.request.user).prefetch_related('history_entries')

    def _cycle_snapshot(self, cycle):
        return {
            'name': cycle.name,
            'description': cycle.description,
            'started_at': str(cycle.started_at),
            'expected_end_at': str(cycle.expected_end_at) if cycle.expected_end_at else None,
            'actual_end_at': str(cycle.actual_end_at) if cycle.actual_end_at else None,
            'status': cycle.status,
            'soil_preparation_notes': cycle.soil_preparation_notes,
            'expected_yield': str(cycle.expected_yield) if cycle.expected_yield else None,
            'actual_yield': str(cycle.actual_yield) if cycle.actual_yield else None,
            'total_investment': str(cycle.total_investment) if cycle.total_investment else None,
            'total_revenue': str(cycle.total_revenue) if cycle.total_revenue else None,
            'notes': cycle.notes,
        }

    def _build_cycle_change_summary(self, changed_fields):
        readable = {
            'name': 'name',
            'status': 'status',
            'actual_end_at': 'actual end date',
            'actual_yield': 'actual yield',
            'total_revenue': 'total revenue',
            'notes': 'notes',
        }
        labels = [readable.get(field, field) for field in changed_fields if field in readable or field not in readable]
        if not labels:
            return 'Farming cycle updated'
        if len(labels) == 1:
            return f"Updated {labels[0]}"
        return f"Updated {', '.join(labels[:-1])} and {labels[-1]}"

    def perform_create(self, serializer):
        cycle = serializer.save()
        FarmingCycleHistory.objects.create(
            cycle=cycle,
            action_type=FarmingCycleHistory.Action.CREATED,
            summary='Farming cycle created',
            current_values=self._cycle_snapshot(cycle),
            modified_by=self.request.user,
        )

    def perform_update(self, serializer):
        cycle = self.get_object()
        previous_values = self._cycle_snapshot(cycle)
        updated_cycle = serializer.save()
        current_values = self._cycle_snapshot(updated_cycle)

        changed_fields = [field for field in previous_values.keys() if previous_values.get(field) != current_values.get(field)]
        if changed_fields:
            action_type = FarmingCycleHistory.Action.STATUS_CHANGED if 'status' in changed_fields else FarmingCycleHistory.Action.UPDATED
            if updated_cycle.status == FarmingCycleHistory.Action.COMPLETED:
                action_type = FarmingCycleHistory.Action.COMPLETED
            
            FarmingCycleHistory.objects.create(
                cycle=updated_cycle,
                action_type=action_type,
                summary=self._build_cycle_change_summary(changed_fields),
                previous_values=previous_values,
                current_values=current_values,
                modified_by=self.request.user,
            )


class FarmingWeatherView(APIView):
    """GET /api/farming/weather/ — OpenWeather forecast for farmer lands."""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(tags=['Farming'])
    def get(self, request):
        serializer = FarmingWeatherSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        lat = serializer.validated_data.get('lat')
        lon = serializer.validated_data.get('lon')
        days = serializer.validated_data.get('days')

        if lat is None or lon is None:
            land = request.user.land_parcels.exclude(latitude__isnull=True, longitude__isnull=True).first()
            if land:
                lat, lon = float(land.latitude), float(land.longitude)

        if lat is None or lon is None:
            lat, lon = 24.3745, 88.6042

        payload = get_weather_forecast(lat=lat, lon=lon, days=days)
        return Response(payload, status=status.HTTP_200_OK)
