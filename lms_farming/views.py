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


@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Farming - Land'],
    operation_description='List user land parcels with full details and status.'
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    tags=['Farming - Land'],
    operation_description='Get specific land parcel details.'
))
@method_decorator(name='create', decorator=swagger_auto_schema(
    tags=['Farming - Land'],
    operation_description='Register a new land parcel.'
))
@method_decorator(name='update', decorator=swagger_auto_schema(
    tags=['Farming - Land'],
    operation_description='Replace land parcel details.'
))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(
    tags=['Farming - Land'],
    operation_description='Partially update land parcel.'
))
@method_decorator(name='destroy', decorator=swagger_auto_schema(
    tags=['Farming - Land'],
    operation_description='Delete a land parcel.'
))
@method_decorator(name='history', decorator=swagger_auto_schema(
    tags=['Farming - Land'],
    operation_description='Get complete history of land parcel and crops grown.'
))
class LandParcelViewSet(viewsets.ModelViewSet):
    """Land parcel management.

    Audience: Farmer
    
    CRUD operations for managing user's agricultural land parcels. Each parcel tracks location, area, and soil characteristics.
    
    **Available Actions:**
    - GET /farming/lands/ - List user's land parcels
    - GET /farming/lands/{id}/ - Get land details
    - POST /farming/lands/ - Register new land
    - PUT /farming/lands/{id}/ - Replace land details
    - PATCH /farming/lands/{id}/ - Update land fields
    - DELETE /farming/lands/{id}/ - Remove land parcel
    - GET /farming/lands/{id}/history/ - View complete land & crop history
    
    **Authentication:** Required (Bearer token)
    
    **Permissions:** Owners can only access their own land parcels
    
    **Fields:**
    - id (read-only): Unique parcel identifier
    - owner (read-only): User who registered the land
    - name: Display name for the parcel (e.g., "North Field")
    - location: Village/area description
    - latitude: GPS latitude
    - longitude: GPS longitude
    - area_acres: Total area in decimal acres
    - soil_type: Classification (loamy, sandy, clayey, rocky, etc.)
    - notes: Additional information
    - created_at (read-only): Registration timestamp
    - updated_at (read-only): Last modification timestamp
    
    **Validation Rules:**
    - name: Required, max 255 characters
    - area_acres: Must be positive decimal (> 0)
    - latitude: Between -90 and 90
    - longitude: Between -180 and 180
    - soil_type: Select from predefined types
    """
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


@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='List crop tracks (growing seasons) for user lands.'
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Get crop track details with activities log.'
))
@method_decorator(name='create', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Create new crop track (season).'
))
@method_decorator(name='update', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Replace crop track details.'
))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Partially update crop track.'
))
@method_decorator(name='destroy', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Delete a crop track.'
))
class CropTrackViewSet(viewsets.ModelViewSet):
    """Crop tracking and activity logging.

    Audience: Farmer
    
    Track individual crop growing seasons on each land parcel. Log farming activities (irrigation, fertilization, pesticide application, harvesting).
    
    **Available Actions:**
    - GET /farming/tracks/ - List crop tracks
    - GET /farming/tracks/{id}/ - Get crop track details
    - POST /farming/tracks/ - Create new crop track
    - PUT /farming/tracks/{id}/ - Replace track details
    - PATCH /farming/tracks/{id}/ - Update track fields
    - DELETE /farming/tracks/{id}/ - Delete crop track
    - GET /farming/tracks/{id}/activities/ - List activities for this track
    - POST /farming/tracks/{id}/activities/ - Log new farming activity
    
    **Authentication:** Required (Bearer token)
    
    **Permissions:** Access only own land parcels
    
    **Fields:**
    - id (read-only): Track identifier
    - land: Land parcel ID
    - crop_name: Display name (e.g., "Rice")
    - crop_type: Classification (rice, wheat, corn, potato, vegetables)
    - planted_date: Sowing/planting date
    - expected_harvest_date: Projected harvest date
    - actual_harvest_date: Actual harvest date (populated after harvest)
    - status: Current stage (active, harvested, completed)
    - notes: Cultivation notes
    
    **Activity Types:**
    - irrigation: Water application
    - fertilization: Nutrient application
    - pesticide: Pest/disease control
    - weeding: Manual weed removal
    - harvest: Crop harvesting
    - other: Miscellaneous activity
    
    **Automatic Updates:**
    - When harvest activity is logged, actual_harvest_date and status update automatically
    - CropTrackHistory records all significant changes for audit trail
    """
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


@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='List crop growth stages.'
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Get specific growth stage details.'
))
@method_decorator(name='create', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Create new growth stage for a crop.'
))
@method_decorator(name='update', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Replace growth stage details.'
))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Update growth stage fields.'
))
@method_decorator(name='destroy', decorator=swagger_auto_schema(
    tags=['Farming - Crops'],
    operation_description='Delete a growth stage.'
))
class CropStageViewSet(viewsets.ModelViewSet):
    """Crop growth stages.

    Audience: Farmer
    
    Define and track specific growth stages (phenophases) during a crop's lifecycle. Each stage represents a distinct developmental phase with associated characteristics.
    
    **Available Actions:**
    - GET /farming/stages/ - List all stages
    - GET /farming/stages/{id}/ - Get stage details
    - POST /farming/stages/ - Create stage
    - PUT /farming/stages/{id}/ - Replace stage
    - PATCH /farming/stages/{id}/ - Update stage
    - DELETE /farming/stages/{id}/ - Delete stage
    
    **Authentication:** Required (Bearer token)
    
    **Permissions:** Access only own land crop stages
    
    **Fields:**
    - id (read-only): Stage identifier
    - track: Parent crop track ID
    - stage_name: Phase name (Vegetative, Flowering, Grain Fill, Maturity)
    - started_at: When stage began
    - expected_end_at: Projected stage end
    - actual_end_at: Actual stage end date
    - description: Stage characteristics and management notes
    - image_url: Reference image (optional)
    
    **Typical Rice Stages:**
    1. Vegetative: Leaf production, tiller development (0-40 days)
    2. Reproductive: Panicle initiation and development (40-70 days)
    3. Grain Development: Grain filling (70-95 days)
    4. Mature: Ready for harvest (95+ days)
    """
    serializer_class = CropStageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CropStage.objects.filter(track__land__owner=self.request.user)


@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Farming - Cycles'],
    operation_description='List farming cycles for user lands.'
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    tags=['Farming - Cycles'],
    operation_description='Get farming cycle details with history.'
))
@method_decorator(name='create', decorator=swagger_auto_schema(
    tags=['Farming - Cycles'],
    operation_description='Create new farming cycle.'
))
@method_decorator(name='update', decorator=swagger_auto_schema(
    tags=['Farming - Cycles'],
    operation_description='Replace farming cycle details.'
))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(
    tags=['Farming - Cycles'],
    operation_description='Update farming cycle fields.'
))
@method_decorator(name='destroy', decorator=swagger_auto_schema(
    tags=['Farming - Cycles'],
    operation_description='Delete a farming cycle.'
))
class FarmingCycleViewSet(viewsets.ModelViewSet):
    """Farming cycles and seasonal management.

    Audience: Farmer
    
    Manage complete farming cycles (seasons) with financial tracking, yield predictions, and modification history. Each cycle represents one complete agricultural season on a specific land parcel.
    
    **Available Actions:**
    - GET /farming/cycles/ - List farming cycles
    - GET /farming/cycles/{id}/ - Get cycle details
    - POST /farming/cycles/ - Create cycle
    - PUT /farming/cycles/{id}/ - Replace cycle
    - PATCH /farming/cycles/{id}/ - Update cycle
    - DELETE /farming/cycles/{id}/ - Delete cycle
    - GET /farming/cycles/{id}/history/ - View modification history
    
    **Authentication:** Required (Bearer token)
    
    **Permissions:** Owner access only
    
    **Fields:**
    - id (read-only): Cycle identifier
    - land: Land parcel ID
    - name: Cycle name (e.g., "Summer Rice 2026")
    - description: Season description and goals
    - started_at: Season start date
    - expected_end_at: Projected season end
    - actual_end_at: Actual season end date
    - status: Current status (planning, active, completed, archived)
    - soil_preparation_notes: Pre-planting soil management
    - expected_yield: Projected yield (kg)
    - actual_yield: Harvested yield (kg)
    - total_investment: Total cost in BDT (seeds, fertilizer, labor)
    - total_revenue: Total income in BDT
    - notes: General notes
    
    **Statuses:**
    - planning: Initial setup phase
    - active: Crop in progress
    - completed: Season finished, yield recorded
    - archived: Historical data
    
    **Financial Tracking:**
    - Investment includes seeds, fertilizer, pesticides, labor
    - Revenue calculated from harvest quantity and market price
    - ROI = (revenue - investment) / investment * 100
    
    **History Tracking:**
    - All modifications automatically recorded
    - Immutable audit trail for compliance
    - Tracks yield updates, revenue changes, status transitions
    """
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
    """Weather forecast endpoint for farming operations.

    Audience: Both

    Returns weather forecast with optional coordinates. If coordinates are omitted,
    resolves location from user's first land parcel; otherwise uses default fallback coordinates.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        tags=['Farming - Weather'],
        operation_description='Get weather forecast for provided coordinates or default farm location.'
    )
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
