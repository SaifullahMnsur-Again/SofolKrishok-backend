import logging
from datetime import timedelta
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema

from .models import ChatSession, ChatMessage, DiseaseDetectionLog, SoilClassificationLog
from .models import AIModelArtifact, AIServiceConfiguration, Crop, AIModelUsageHistory
from .serializers import (
    ChatSessionSerializer,
    ChatSessionDetailSerializer,
    ChatRequestSerializer,
    ChatResponseSerializer,
    DiseaseDetectionSerializer,
    DiseaseDetectionLogSerializer,
    SoilClassificationSerializer,
    SoilClassificationLogSerializer,
    AIModelUsageHistorySerializer,
    VoiceCommandSerializer,
    WeatherForecastSerializer,
    AIModelArtifactSerializer,
    AIServiceConfigurationSerializer,
    CropSerializer,
)
from .permissions import IsAIModelManager
from .gemini_service import chat_with_gemini
from .whisper_service import transcribe_bangla_audio
from .weather_service import get_weather_forecast
from .usage_history import record_model_usage
from users.models import Notification

logger = logging.getLogger(__name__)


def _invalidate_gemini_client_cache():
    from . import gemini_service

    gemini_service._client = None
    gemini_service._client_api_key = None


class AIModelArtifactViewSet(viewsets.ModelViewSet):
    """AI model artifact registry management.

    Audience: Staff

    Manage model artifacts used by disease detection and soil classification services.
    Includes activation workflow to switch currently active model per scope.
    """
    serializer_class = AIModelArtifactSerializer
    permission_classes = [permissions.IsAuthenticated, IsAIModelManager]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        queryset = AIModelArtifact.objects.all().select_related('created_by')
        query_params = getattr(self.request, 'query_params', {})
        operation = query_params.get('operation')
        crop_type = query_params.get('crop_type')
        is_active = query_params.get('is_active')

        if operation:
            queryset = queryset.filter(operation=operation)
        if crop_type:
            queryset = queryset.filter(crop_type=crop_type)
        if is_active in {'true', 'True', '1'}:
            queryset = queryset.filter(is_active=True)
        elif is_active in {'false', 'False', '0'}:
            queryset = queryset.filter(is_active=False)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @swagger_auto_schema(tags=['AI Management'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['AI Management'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['AI Management'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['AI Management'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(tags=['AI Management'])
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        artifact = self.get_object()
        artifact.is_active = True
        # Do NOT use update_fields here — the custom save() must run
        # to deactivate other models with the same operation+crop_type scope.
        artifact.save()
        return Response(self.get_serializer(artifact).data)


class AIModelUsageHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """AI model usage analytics and audit logs.

    Audience: Staff

    Read-only endpoint for filtering and analyzing model usage, failures, confidence trends,
    and service-level behavior.
    """
    serializer_class = AIModelUsageHistorySerializer
    permission_classes = [permissions.IsAuthenticated, IsAIModelManager]

    def get_queryset(self):
        queryset = (
            AIModelUsageHistory.objects.all()
            .select_related('user', 'subscription__plan', 'model_artifact')
        )
        params = getattr(self.request, 'query_params', {})

        operation = params.get('operation')
        service_name = params.get('service_name')
        model_identifier = params.get('model_identifier')
        user_role = params.get('user_role')
        subscription_plan_name = params.get('subscription_plan_name')
        subscription_plan_type = params.get('subscription_plan_type')
        subscription_status = params.get('subscription_status')
        success = params.get('success')
        user_id = params.get('user_id')
        model_id = params.get('model_id')
        crop_type = params.get('crop_type')
        start = params.get('start')
        end = params.get('end')
        condition = params.get('condition')

        if operation:
            queryset = queryset.filter(operation=operation)
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        if model_identifier:
            queryset = queryset.filter(model_identifier__icontains=model_identifier)
        if user_role:
            queryset = queryset.filter(user_role=user_role)
        if subscription_plan_name:
            queryset = queryset.filter(subscription_plan_name__icontains=subscription_plan_name)
        if subscription_plan_type:
            queryset = queryset.filter(subscription_plan_type=subscription_plan_type)
        if subscription_status:
            queryset = queryset.filter(subscription_status=subscription_status)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if model_id:
            queryset = queryset.filter(model_artifact_id=model_id)
        if crop_type:
            queryset = queryset.filter(model_artifact__crop_type=crop_type)
        if success in {'true', 'True', '1'}:
            queryset = queryset.filter(success=True)
        elif success in {'false', 'False', '0'}:
            queryset = queryset.filter(success=False)
        if start:
            queryset = queryset.filter(created_at__gte=start)
        if end:
            queryset = queryset.filter(created_at__lte=end)

        if condition == 'today':
            today = timezone.localdate()
            queryset = queryset.filter(created_at__date=today)
        elif condition == 'this_week':
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=7))
        elif condition == 'this_month':
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=30))
        elif condition == 'high_confidence':
            queryset = queryset.filter(confidence__gte=90)
        elif condition == 'training_ready':
            queryset = queryset.filter(success=True).exclude(response_metadata={})
        elif condition == 'errors':
            queryset = queryset.filter(success=False)

        return queryset.order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)

        summary_qs = queryset
        summary = {
            'total': summary_qs.count(),
            'successful': summary_qs.filter(success=True).count(),
            'failed': summary_qs.filter(success=False).count(),
        }

        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data['summary'] = summary
            return response

        return Response({'count': summary['total'], 'summary': summary, 'results': serializer.data})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        from django.db.models import Count, Avg
        from django.db.models.functions import TruncDate

        def serialize_top(items, key):
            return [
                {key: item[key], 'count': item['count']}
                for item in items
            ]

        daily_usage = []
        for item in (
            queryset.annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        ):
            daily_usage.append({
                'date': item['day'].isoformat() if item.get('day') else None,
                'count': item['count'],
            })

        return Response({
            'total': queryset.count(),
            'successful': queryset.filter(success=True).count(),
            'failed': queryset.filter(success=False).count(),
            'by_service': serialize_top(
                list(queryset.values('service_name').annotate(count=Count('id')).order_by('-count')[:10]),
                'service_name',
            ),
            'by_model': serialize_top(
                list(queryset.values('model_identifier').annotate(count=Count('id')).order_by('-count')[:10]),
                'model_identifier',
            ),
            'by_role': serialize_top(
                list(queryset.values('user_role').annotate(count=Count('id')).order_by('-count')[:10]),
                'user_role',
            ),
            'by_subscription_plan': serialize_top(
                list(queryset.values('subscription_plan_name').annotate(count=Count('id')).order_by('-count')[:10]),
                'subscription_plan_name',
            ),
            'daily_usage': daily_usage[-14:],
            'avg_confidence': queryset.exclude(confidence__isnull=True).aggregate(avg=Avg('confidence')).get('avg'),
        })


class GeminiConfigurationView(APIView):
    """Gemini service configuration management.

    Audience: Staff

    Allows AI managers to view and update Gemini API/model settings.
    Any update invalidates cached Gemini client configuration.
    """
    permission_classes = [permissions.IsAuthenticated, IsAIModelManager]

    def get(self, request):
        config = AIServiceConfiguration.get_solo()
        serializer = AIServiceConfigurationSerializer(config)
        return Response(serializer.data)

    def put(self, request):
        config = AIServiceConfiguration.get_solo()
        serializer = AIServiceConfigurationSerializer(config, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _invalidate_gemini_client_cache()
        return Response(serializer.data)

    def patch(self, request):
        """Partial update — update only the fields supplied (e.g. just the models, or just the key)."""
        config = AIServiceConfiguration.get_solo()
        serializer = AIServiceConfigurationSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _invalidate_gemini_client_cache()
        return Response(serializer.data)



class AIModelInventoryView(APIView):
    """Model inventory snapshot for Model Hub UI.

    Audience: Staff

    Returns disease and soil model registries plus Gemini config envelope for management dashboards.
    """
    permission_classes = [permissions.IsAuthenticated, IsAIModelManager]

    def get(self, request):
        disease_queryset = (
            AIModelArtifact.objects.filter(operation=AIModelArtifact.Operation.DISEASE_DETECTION)
            .order_by('crop_type', '-is_active', '-updated_at')
        )
        disease_registry = AIModelArtifactSerializer(disease_queryset, many=True, context={'request': request}).data

        soil_queryset = (
            AIModelArtifact.objects.filter(operation=AIModelArtifact.Operation.SOIL_CLASSIFICATION)
            .order_by('crop_type', '-is_active', '-updated_at')
        )
        soil_registry = AIModelArtifactSerializer(soil_queryset, many=True, context={'request': request}).data

        return Response({
            'registry': disease_registry,  # backward compatibility
            'disease': {
                'registry': disease_registry,
            },
            'soil': {
                'registry': soil_registry,
            },
            'gemini': {},
        })

    def patch(self, request):
        config = AIServiceConfiguration.get_solo()
        serializer = AIServiceConfigurationSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _invalidate_gemini_client_cache()
        return Response(serializer.data)


class CropViewSet(viewsets.ModelViewSet):
    """Crop dictionary management for AI model tools.

    Audience: Staff

    Maintains crop catalog entries shown in AI management and inference workflows.
    """
    permission_classes = [permissions.IsAuthenticated, IsAIModelManager]
    serializer_class = CropSerializer

    def get_queryset(self):
        return Crop.objects.all().order_by('english_name')

    def perform_create(self, serializer):
        serializer.save()


class ActiveDiseaseCropsView(APIView):
    """Active disease model registry for farmer-facing clients.

    Audience: Both

    Exposes active disease models grouped by crop without requiring AI manager role.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(tags=['AI'])
    def get(self, request):
        queryset = (
            AIModelArtifact.objects.filter(
                operation=AIModelArtifact.Operation.DISEASE_DETECTION,
                is_active=True,
            ).order_by('crop_type', '-updated_at')
        )
        data = AIModelArtifactSerializer(queryset, many=True, context={'request': request}).data
        return Response({'disease': {'registry': data}})


# ============================================
# Chat Session Management (Memory)
# ============================================

@method_decorator(name='get', decorator=swagger_auto_schema(
    tags=['AI - Chat Sessions'],
    operation_description='List chat sessions for current user.'
))
@method_decorator(name='post', decorator=swagger_auto_schema(
    tags=['AI - Chat Sessions'],
    operation_description='Create a new chat session.'
))
class ChatSessionListCreateView(generics.ListCreateAPIView):
    """Chat session list/create endpoint.

    Audience: Both

    Provides per-user chat session listing and session creation for Gemini conversations.
    """
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@method_decorator(name='get', decorator=swagger_auto_schema(
    tags=['AI - Chat Sessions'],
    operation_description='Retrieve a chat session with message history.'
))
@method_decorator(name='put', decorator=swagger_auto_schema(
    tags=['AI - Chat Sessions'],
    operation_description='Replace chat session details.'
))
@method_decorator(name='patch', decorator=swagger_auto_schema(
    tags=['AI - Chat Sessions'],
    operation_description='Partially update chat session details.'
))
@method_decorator(name='delete', decorator=swagger_auto_schema(
    tags=['AI - Chat Sessions'],
    operation_description='Delete chat session and related messages.'
))
class ChatSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Chat session detail/update/delete endpoint.

    Audience: Both

    Supports retrieval, update, and deletion of a specific user chat session.
    """
    serializer_class = ChatSessionDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)


# ============================================
# Chat with Gemini (Memory-Aware)
# ============================================

class GeminiChatView(APIView):
    """AI chat with full conversation memory.

    Audience: Both
    
    Send messages to Gemini AI with persistent conversation history. The entire chat history is automatically maintained and replayed as context for better contextual responses.
    
    **Endpoint:** POST /ai/gemini-chat/
    
    **Authentication:** Required (Bearer token)
    
    **Request Body:**
    ```json
    {
      "message": "How do I prevent rice blast disease?",
      "session_id": 5,
      "land_id": 3
    }
    ```
    
    **Request Fields:**
    - message: User query (required, max 2000 chars)
    - session_id: Existing chat session ID to continue (optional)
    - land_id: Link chat to a specific land parcel for context (optional)
    
    **Response:**
    ```json
    {
      "session_id": 5,
      "session_title": "Rice Disease Prevention",
      "response": "To prevent rice blast disease...",
      "message_count": 12
    }
    ```
    
    **Response Fields:**
    - session_id: Chat session ID for future messages
    - session_title: Auto-generated session title based on conversation
    - response: AI-generated answer
    - message_count: Total messages in this session
    
    **Features:**
    - Full chat history context: Each message includes all previous conversation
    - Land parcel context: Responses tailored to specific land characteristics
    - Auto-session creation: New session created if session_id not provided
    - Usage tracking: All requests logged for quota enforcement
    - Error handling: Clear error messages for API failures
    
    **Error Responses:**
    - 404: Session not found (if invalid session_id provided)
    - 503: Gemini API unavailable or rate limited
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(tags=['AI'])
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        message = serializer.validated_data['message']
        session_id = serializer.validated_data.get('session_id')
        land_id = serializer.validated_data.get('land_id')

        # Get or create session
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=user)
            except ChatSession.DoesNotExist:
                return Response(
                    {'error': 'Chat session not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            # Create new session
            land_parcel = None
            if land_id:
                from lms_farming.models import LandParcel
                try:
                    land_parcel = LandParcel.objects.get(id=land_id, owner=user)
                except LandParcel.DoesNotExist:
                    pass

            session = ChatSession.objects.create(
                user=user,
                land_parcel=land_parcel,
                title="New Chat",
            )

        # If land_id provided and session has no land parcel, link it
        if land_id and not session.land_parcel:
            from lms_farming.models import LandParcel
            try:
                session.land_parcel = LandParcel.objects.get(id=land_id, owner=user)
                session.save(update_fields=['land_parcel'])
            except LandParcel.DoesNotExist:
                pass

        # Call Gemini with full memory context
        try:
            chat_result = chat_with_gemini(session, message, return_metadata=True)
        except ValueError as e:
            record_model_usage(
                user=user,
                service_name=AIModelUsageHistory.Service.GEMINI_CHAT,
                operation='gemini_chat',
                model_identifier=getattr(settings, 'GEMINI_MODEL', '') or AIServiceConfiguration.get_solo().gemini_model or 'gemini-chat',
                request_path=request.path,
                request_metadata={
                    'session_id': session_id,
                    'land_id': land_id,
                    'message_length': len(message),
                },
                success=False,
                error_message=str(e),
                request=request,
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response_text = chat_result['response']
        model_used = chat_result.get('model_used', '')
        record_model_usage(
            user=user,
            service_name=AIModelUsageHistory.Service.GEMINI_CHAT,
            operation='gemini_chat',
            model_identifier=model_used,
            model_version=model_used,
            request_path=request.path,
            request_metadata={
                'session_id': session.id,
                'land_id': land_id,
                'message_length': len(message),
            },
            response_metadata={
                'message_count': session.message_count,
            },
            request=request,
        )

        # Refresh session from DB (title may have been auto-updated)
        session.refresh_from_db()

        return Response({
            'session_id': session.id,
            'session_title': session.title,
            'response': response_text,
            'message_count': session.message_count,
        })


# ============================================
# Disease Detection
# ============================================

class DiseaseDetectView(APIView):
    """Crop disease detection via image upload.

    Audience: Farmer
    
    Upload a crop leaf or plant image for AI-powered disease detection. Supports corn, potato, rice, and wheat crops with high accuracy disease classification.
    
    **Endpoint:** POST /ai/disease-detect/
    
    **Authentication:** Required (Bearer token)
    
    **Request Format:** multipart/form-data
    
    **Request Fields:**
    - image: Image file (JPG/PNG, max 10MB) - required
    - crop_type: corn, potato, rice, or wheat - required
    - land_id: Link detection to a specific land parcel (optional)
    
    **Response:**
    ```json
    {
      "predicted_class": "Rice Blast",
      "confidence": "95.2",
      "disease_description": "Fungal infection caused by Pyricularia oryzae",
      "treatment_recommendations": [
        "Apply fungicide XYZ at recommended concentration",
        "Improve field drainage to reduce humidity",
        "Harvest affected areas to prevent spread"
      ],
      "all_predictions": {
        "Rice Blast": "95.2",
        "Brown Spot": "3.1",
        "Leaf Scald": "1.7"
      },
      "image_url": "/media/disease_scans/rice_2026_04_30_abc123.jpg",
      "detection_timestamp": "2026-04-30T10:30:00Z"
    }
    ```
    
    **Response Fields:**
    - predicted_class: Most likely disease detected
    - confidence: Detection confidence percentage (0-100)
    - disease_description: Detailed disease information
    - treatment_recommendations: List of treatment actions
    - all_predictions: All disease probabilities (top N)
    - image_url: Saved scan image URL
    - detection_timestamp: When detection was performed
    
    **Supported Crops & Diseases:**
    - Rice: Blast, Brown Spot, Leaf Scald, Septoria
    - Wheat: Rusts, Septoria, Powdery Mildew, Scab
    - Corn: Leaf Blight, Rust, Gray Leaf Spot
    - Potato: Late Blight, Early Blight, Scab
    
    **Best Practices:**
    - Use high-quality, clear photos in good lighting
    - Capture affected leaves/stems (not entire plant)
    - Ensure image is focused and not blurry
    - Multiple angles improve accuracy
    
    **Error Responses:**
    - 400: Invalid crop_type or missing image
    - 413: Image file too large
    - 500: Model inference failed
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(tags=['AI'])
    def post(self, request):
        serializer = DiseaseDetectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image = serializer.validated_data['image']
        crop_type = serializer.validated_data['crop_type']

        try:
            from .disease_service import detect_disease
            from .disease_service import resolve_active_disease_artifact
            artifact = resolve_active_disease_artifact(crop_type)
            result = detect_disease(image, crop_type)
        except FileNotFoundError as e:
            record_model_usage(
                user=request.user,
                service_name=AIModelUsageHistory.Service.DISEASE_DETECTION,
                operation='disease_detection',
                model_artifact=artifact if 'artifact' in locals() else None,
                model_identifier=(artifact.display_name if 'artifact' in locals() and artifact else f'disease:{crop_type}'),
                model_version=getattr(artifact, 'version', '') if 'artifact' in locals() and artifact else '',
                request_path=request.path,
                request_metadata={'crop_type': crop_type, 'image_name': getattr(image, 'name', '')},
                success=False,
                error_message=str(e),
                request=request,
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.error(f"Disease detection error: {e}")
            record_model_usage(
                user=request.user,
                service_name=AIModelUsageHistory.Service.DISEASE_DETECTION,
                operation='disease_detection',
                model_artifact=artifact if 'artifact' in locals() else None,
                model_identifier=(artifact.display_name if 'artifact' in locals() and artifact else f'disease:{crop_type}'),
                model_version=getattr(artifact, 'version', '') if 'artifact' in locals() and artifact else '',
                request_path=request.path,
                request_metadata={'crop_type': crop_type, 'image_name': getattr(image, 'name', '')},
                success=False,
                error_message=str(e),
                request=request,
            )
            return Response(
                {'error': 'Disease detection failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Log the prediction
        log = DiseaseDetectionLog.objects.create(
            user=request.user,
            crop_type=crop_type,
            image=image,
            predicted_class=result['predicted_class'],
            confidence=result['confidence'],
            all_predictions=result['all_predictions'],
        )

        record_model_usage(
            user=request.user,
            service_name=AIModelUsageHistory.Service.DISEASE_DETECTION,
            operation='disease_detection',
            model_artifact=artifact if 'artifact' in locals() else None,
            model_identifier=(artifact.display_name if 'artifact' in locals() and artifact else f'disease:{crop_type}'),
            model_version=getattr(artifact, 'version', '') if 'artifact' in locals() and artifact else '',
            request_path=request.path,
            request_metadata={'crop_type': crop_type, 'image_name': getattr(image, 'name', '')},
            response_metadata={
                'log_id': log.id,
                'predicted_class': result['predicted_class'],
                'is_healthy': result.get('is_healthy'),
                'top_prediction': result['all_predictions'],
            },
            confidence=result.get('confidence'),
            request=request,
        )

        return Response({
            'log_id': log.id,
            **result,
        })

    @swagger_auto_schema(tags=['AI'])
    def get(self, request):
        """GET /api/ai/disease-detect/ — List supported crops."""
        from .disease_service import get_supported_crops
        return Response({'supported_crops': get_supported_crops()})


# ============================================
# Soil Classification
# ============================================

class SoilClassifyView(APIView):
    """Soil classification via image analysis.

    Audience: Farmer
    
    Upload a soil sample image for AI-powered soil type classification, texture analysis, and fertilizer recommendations. Provides comprehensive soil management guidance.
    
    **Endpoint:** POST /ai/soil-classify/
    
    **Authentication:** Required (Bearer token)
    
    **Request Format:** multipart/form-data
    
    **Request Fields:**
    - image: Soil sample photo (JPG/PNG, max 10MB) - required
    - land_id: Link analysis to a specific land parcel (optional)
    
    **Response:**
    ```json
    {
      "soil_type": "loamy",
      "texture_class": "sandy-clay-loam",
      "ph_level": "7.2",
      "fertility_rating": "high",
      "organic_matter": "medium",
      "drainage_rating": "well-drained",
      "recommended_crops": [
        "rice",
        "wheat",
        "vegetables",
        "legumes"
      ],
      "not_recommended_crops": [
        "sugarcane"
      ],
      "fertilizer_recommendations": {
        "nitrogen_kg_per_acre": "100",
        "phosphorus_kg_per_acre": "50",
        "potassium_kg_per_acre": "40",
        "organic_matter_kg_per_acre": "5000"
      },
      "soil_improvement_tips": [
        "Add organic compost to improve water retention",
        "Rotate crops annually to maintain fertility"
      ],
      "image_url": "/media/soil_scans/loam_2026_04_30_xyz789.jpg",
      "analysis_timestamp": "2026-04-30T11:15:00Z"
    }
    ```
    
    **Response Fields:**
    - soil_type: Primary classification (clay, loam, sandy, rocky)
    - texture_class: Detailed USDA texture classification
    - ph_level: Soil pH (0-14)
    - fertility_rating: high, medium, low
    - organic_matter: Organic content percentage
    - drainage_rating: Drainage characteristics
    - recommended_crops: Suitable crop list
    - not_recommended_crops: Crops to avoid
    - fertilizer_recommendations: Nutrient application rates
    - soil_improvement_tips: Management suggestions
    - image_url: Stored analysis image
    - analysis_timestamp: Analysis date/time
    
    **Soil Types & Characteristics:**
    - Sandy: Drains quickly, low fertility, needs frequent watering
    - Clay: High fertility, poor drainage, compacts easily
    - Loam: Balanced texture, good drainage, best all-around soil
    - Rocky: Poor water retention, difficult cultivation
    
    **Best Practices:**
    - Collect soil sample from multiple areas of field
    - Take photo in natural daylight
    - Show soil texture clearly (crumbled/compressed)
    - Ensure image is in focus
    
    **Linked to Land Parcel:**
    If land_id provided, analysis is associated with that parcel for history tracking and recommendations.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(tags=['AI'])
    def post(self, request):
        serializer = SoilClassificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image = serializer.validated_data['image']
        land_id = serializer.validated_data.get('land_id')

        try:
            from .soil_service import classify_soil
            from .soil_service import resolve_active_soil_artifact
            artifact = resolve_active_soil_artifact()
            result = classify_soil(image)
        except FileNotFoundError as e:
            record_model_usage(
                user=request.user,
                service_name=AIModelUsageHistory.Service.SOIL_CLASSIFICATION,
                operation='soil_classification',
                model_artifact=artifact if 'artifact' in locals() else None,
                model_identifier=(artifact.display_name if 'artifact' in locals() and artifact else 'soil-classifier'),
                model_version=getattr(artifact, 'version', '') if 'artifact' in locals() and artifact else '',
                request_path=request.path,
                request_metadata={'land_id': land_id, 'image_name': getattr(image, 'name', '')},
                success=False,
                error_message=str(e),
                request=request,
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.error(f"Soil classification error: {e}")
            record_model_usage(
                user=request.user,
                service_name=AIModelUsageHistory.Service.SOIL_CLASSIFICATION,
                operation='soil_classification',
                model_artifact=artifact if 'artifact' in locals() else None,
                model_identifier=(artifact.display_name if 'artifact' in locals() and artifact else 'soil-classifier'),
                model_version=getattr(artifact, 'version', '') if 'artifact' in locals() and artifact else '',
                request_path=request.path,
                request_metadata={'land_id': land_id, 'image_name': getattr(image, 'name', '')},
                success=False,
                error_message=str(e),
                request=request,
            )
            return Response(
                {'error': 'Soil classification failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # If land_id provided, update the land parcel's soil type
        land_parcel = None
        if land_id:
            from lms_farming.models import LandParcel
            try:
                land_parcel = LandParcel.objects.get(id=land_id, owner=request.user)
                land_parcel.soil_type = result['predicted_type']
                land_parcel.save(update_fields=['soil_type'])
            except LandParcel.DoesNotExist:
                pass

        # Log the prediction
        log = SoilClassificationLog.objects.create(
            user=request.user,
            image=image,
            predicted_type=result['predicted_type'],
            confidence=result['confidence'],
            all_predictions=result['all_predictions'],
            land_parcel=land_parcel,
        )

        record_model_usage(
            user=request.user,
            service_name=AIModelUsageHistory.Service.SOIL_CLASSIFICATION,
            operation='soil_classification',
            model_artifact=artifact if 'artifact' in locals() else None,
            model_identifier=(artifact.display_name if 'artifact' in locals() and artifact else 'soil-classifier'),
            model_version=getattr(artifact, 'version', '') if 'artifact' in locals() and artifact else '',
            request_path=request.path,
            request_metadata={'land_id': land_id, 'image_name': getattr(image, 'name', '')},
            response_metadata={
                'log_id': log.id,
                'predicted_type': result['predicted_type'],
                'land_updated': land_parcel is not None,
            },
            confidence=result.get('confidence'),
            request=request,
        )

        return Response({
            'log_id': log.id,
            **result,
            'land_updated': land_parcel is not None,
        })


# ============================================
# Voice Command Execution (NLP Intent Mapping)
# ============================================

class VoiceCommandView(APIView):
    """Voice command processing and navigation intent recognition.

    Audience: Both
    
    Process voice or text commands to extract user intent and navigate to relevant app sections. Supports Bangla speech transcription via Whisper.
    
    **Endpoint:** POST /ai/voice-command/
    
    **Authentication:** Required (Bearer token)
    
    **Request Format:** multipart/form-data OR JSON
    
    **Request Fields (JSON):**
    ```json
    {
      "text": "Show me the market"
    }
    ```
    
    **Request Fields (Multipart with Audio):**
    - audio: Audio file (WAV/MP3, max 10MB)
    - text: Optional text fallback if audio fails
    
    **Response:**
    ```json
    {
      "original_text": "Show me the market",
      "transcribed": false,
      "intent": "NAVIGATE",
      "target": "/marketplace",
      "voice_response": "Okay, taking you to Marketplace."
    }
    ```
    
    **Intent Recognition Keywords:**
    
    | Intent | Keywords | Target |
    |--------|----------|--------|
    | Marketplace | market, buy, seed, shop, order | /marketplace |
    | Weather | weather, rain, forecast, temperature | /dashboard |
    | Chat | chat, help, assistant, talk | /chat |
    | Billing | bill, pay, credit, subscription | /billing |
    | Land Mgmt | land, field, parcel | /lands |
    | Disease | disease, sick, detect, leaf | /disease-detect |
    
    **Response Fields:**
    - original_text: Recognized/provided text
    - transcribed: Whether audio was transcribed to text
    - intent: Recognized action intent
    - target: Navigation target URL
    - voice_response: Audio-ready response text
    
    **Supported Languages:**
    - Bengali (Bangla) - via Whisper model
    - English - direct text processing
    
    **Error Responses:**
    - 400: No text or valid audio provided
    - 503: Whisper transcription failed
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _resolve_intent(self, text: str):
        text = (text or '').lower()
        intent = "UNKNOWN"
        target = "/dashboard"

        if any(word in text for word in ['market', 'buy', 'seed', 'fertilizer', 'shop', 'order']):
            intent = "NAVIGATE"
            target = "/marketplace"
        elif any(word in text for word in ['weather', 'rain', 'temperature', 'forecast']):
            intent = "NAVIGATE"
            target = "/dashboard"
        elif any(word in text for word in ['chat', 'help', 'assistant', 'talk']):
            intent = "NAVIGATE"
            target = "/chat"
        elif any(word in text for word in ['bill', 'pay', 'credit', 'subscription', 'finance']):
            intent = "NAVIGATE"
            target = "/billing"
        elif any(word in text for word in ['land', 'field', 'parcel']):
            intent = "NAVIGATE"
            target = "/lands"
        elif any(word in text for word in ['disease', 'sick', 'detect', 'leaf']):
            intent = "NAVIGATE"
            target = "/disease-detect"

        return intent, target

    @swagger_auto_schema(tags=['AI'])
    def post(self, request):
        serializer = VoiceCommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        text = (serializer.validated_data.get('text') or '').strip()
        audio = serializer.validated_data.get('audio')

        if audio and not text:
            try:
                text = transcribe_bangla_audio(audio)
            except Exception as e:
                logger.error("Whisper transcription failed: %s", e)
                return Response(
                    {'error': f"Speech transcription failed: {e}"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        intent, target = self._resolve_intent(text)

        return Response({
            'original_text': text,
            'transcribed': bool(audio),
            'intent': intent,
            'target': target,
            'voice_response': f"Okay, taking you to {target.replace('/', '').capitalize()}." if intent == "NAVIGATE" else "I'm sorry, I didn't catch that command.",
        })


class WeatherForecastView(APIView):
    """Weather forecast with risk alerts and farming recommendations.

    Audience: Both

    Retrieve current and upcoming weather forecasts for a location, including risk alerts relevant to farming operations.

    **Endpoint:** GET /ai/weather-forecast/

    **Authentication:** Required (Bearer token)

    **Query Parameters:**
    - lat: Latitude (optional)
    - lon: Longitude (optional)
    - days: Forecast range in days (optional, 1-7)

    **Location Resolution Priority:**
    1. Query params lat/lon (if provided)
    2. User's first land parcel with coordinates
    3. Fallback to Rajshahi default coordinates

    **Response Includes:**
    - Current weather conditions
    - Daily forecasts
    - Farming-specific alerts
    - Irrigation and field operation recommendations

    **Automatic Notifications:**
    Significant weather risk alerts are automatically saved as user notifications (deduplicated for 12 hours).
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        tags=['AI'],
        operation_description='Get weather forecast with agricultural alerts for a location.'
    )
    def get(self, request):
        serializer = WeatherForecastSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        lat = serializer.validated_data.get('lat')
        lon = serializer.validated_data.get('lon')
        days = serializer.validated_data.get('days')

        if lat is None or lon is None:
            land = request.user.land_parcels.exclude(latitude__isnull=True, longitude__isnull=True).first()
            if land:
                lat, lon = float(land.latitude), float(land.longitude)

        if lat is None or lon is None:
            lat, lon = 24.3745, 88.6042  # Rajshahi fallback

        try:
            payload = get_weather_forecast(lat=lat, lon=lon, days=days)
        except Exception as e:
            logger.error("Weather API error: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Raise user alerts for meaningful weather risks, deduping over 12 hours.
        now = timezone.now()
        for alert in payload.get('alerts', []):
            title = 'Weather Alert'
            message = f"{alert['date']}: {alert['message']}"
            exists = Notification.objects.filter(
                user=request.user,
                title=title,
                message=message,
                timestamp__gte=now - timedelta(hours=12),
            ).exists()
            if not exists:
                Notification.objects.create(
                    user=request.user,
                    title=title,
                    message=message,
                    notification_type='weather',
                )

        return Response(payload)
