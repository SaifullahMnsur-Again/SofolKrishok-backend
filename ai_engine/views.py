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
    """Return the manually managed model registry for the Model Hub UI."""
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
    """Manage crop names used by the Model Hub dropdown."""
    permission_classes = [permissions.IsAuthenticated, IsAIModelManager]
    serializer_class = CropSerializer

    def get_queryset(self):
        return Crop.objects.all().order_by('english_name')

    def perform_create(self, serializer):
        serializer.save()


class ActiveDiseaseCropsView(APIView):
    """
    GET /api/ai/active-disease-crops/

    Public (IsAuthenticated) endpoint that returns active disease-detection
    models grouped by crop.  Used by the farmer-facing DiseaseDetectPage so
    that regular users don't need the IsAIModelManager permission.
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

@method_decorator(name='get', decorator=swagger_auto_schema(tags=['AI']))
@method_decorator(name='post', decorator=swagger_auto_schema(tags=['AI']))
class ChatSessionListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/ai/chat-sessions/ — List all chat sessions for the current user
    POST /api/ai/chat-sessions/ — Create a new chat session
    """
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@method_decorator(name='get', decorator=swagger_auto_schema(tags=['AI']))
@method_decorator(name='put', decorator=swagger_auto_schema(tags=['AI']))
@method_decorator(name='patch', decorator=swagger_auto_schema(tags=['AI']))
@method_decorator(name='delete', decorator=swagger_auto_schema(tags=['AI']))
class ChatSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/ai/chat-sessions/{id}/ — Get session with full message history
    PUT    /api/ai/chat-sessions/{id}/ — Update session (rename, etc.)
    DELETE /api/ai/chat-sessions/{id}/ — Delete session and all messages
    """
    serializer_class = ChatSessionDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)


# ============================================
# Chat with Gemini (Memory-Aware)
# ============================================

class GeminiChatView(APIView):
    """
    POST /api/ai/gemini-chat/
    
    Send a message to the Gemini AI with full conversation memory.
    The entire chat history is replayed as context on each request.
    
    Request body:
        {
            "message": "My rice leaves are turning brown, what should I do?",
            "session_id": 5,          // optional: reuse existing session
            "land_id": 3              // optional: link to a land parcel for context
        }
    
    Response:
        {
            "session_id": 5,
            "session_title": "Rice Brown Leaf Issue",
            "response": "Based on your land in Rajshahi...",
            "message_count": 12
        }
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
    """
    POST /api/ai/disease-detect/
    
    Upload a crop image for disease detection.
    
    Form data:
        image: <file>
        crop_type: corn|potato|rice|wheat
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
    """
    POST /api/ai/soil-classify/
    
    Upload a soil image for classification.
    Optionally link result to a land parcel.
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
    """
    POST /api/ai/voice-command/
    
    Accepts text or audio blobs (simulated) and extracts a navigation intent.
    Mapping:
    - "market" | "buy" | "shop" -> MARKETPLACE
    - "weather" | "rain"         -> DASHBOARD (Weather card focus)
    - "help" | "chat" | "talk"   -> AI_CHAT
    - "bill" | "pay" | "credit"  -> BILLING
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
    """GET /api/ai/weather-forecast/ — Current + upcoming forecast with alerts."""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(tags=['AI'])
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
