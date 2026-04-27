from django.urls import path
from . import views

urlpatterns = [
    # Gemini Chat (Memory-Aware)
    path('gemini-chat/', views.GeminiChatView.as_view(), name='gemini-chat'),

    # Chat Session Management
    path('chat-sessions/', views.ChatSessionListCreateView.as_view(), name='chat-sessions'),
    path('chat-sessions/<int:pk>/', views.ChatSessionDetailView.as_view(), name='chat-session-detail'),

    # Disease Detection
    path('disease-detect/', views.DiseaseDetectView.as_view(), name='disease-detect'),

    # Soil Classification
    path('soil-classify/', views.SoilClassifyView.as_view(), name='soil-classify'),

    # Voice Command Intent Mapping
    path('voice-command/', views.VoiceCommandView.as_view(), name='voice-command'),

    # Weather forecast + alert generation
    path('weather-forecast/', views.WeatherForecastView.as_view(), name='weather-forecast'),
]
