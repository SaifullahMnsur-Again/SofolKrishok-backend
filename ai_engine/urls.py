from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('models', views.AIModelArtifactViewSet, basename='ai-models')
router.register('model-usage', views.AIModelUsageHistoryViewSet, basename='ai-model-usage')
router.register('crops', views.CropViewSet, basename='ai-crops')

urlpatterns = [
    # Gemini Chat (Memory-Aware)
    path('gemini-chat/', views.GeminiChatView.as_view(), name='gemini-chat'),

    # Chat Session Management
    path('chat-sessions/', views.ChatSessionListCreateView.as_view(), name='chat-sessions'),
    path('chat-sessions/<int:pk>/', views.ChatSessionDetailView.as_view(), name='chat-session-detail'),

    # Disease Detection
    path('disease-detect/', views.DiseaseDetectView.as_view(), name='disease-detect'),

    # Active disease crops — accessible by all authenticated users (used by DiseaseDetectPage)
    path('active-disease-crops/', views.ActiveDiseaseCropsView.as_view(), name='active-disease-crops'),

    # Soil Classification
    path('soil-classify/', views.SoilClassifyView.as_view(), name='soil-classify'),

    # Voice Command Intent Mapping
    path('voice-command/', views.VoiceCommandView.as_view(), name='voice-command'),

    # Weather forecast + alert generation
    path('weather-forecast/', views.WeatherForecastView.as_view(), name='weather-forecast'),

    # Model management (staff-only)
    path('models/inventory/', views.AIModelInventoryView.as_view(), name='ai-model-inventory'),
    path('settings/gemini/', views.GeminiConfigurationView.as_view(), name='gemini-config'),
] + router.urls
