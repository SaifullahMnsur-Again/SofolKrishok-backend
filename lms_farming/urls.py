from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'lands', views.LandParcelViewSet, basename='land')
router.register(r'tracks', views.CropTrackViewSet, basename='track')
router.register(r'stages', views.CropStageViewSet, basename='stage')
router.register(r'cycles', views.FarmingCycleViewSet, basename='cycle')

urlpatterns = [
    path('weather/', views.FarmingWeatherView.as_view(), name='farming-weather'),
    path('', include(router.urls)),
]
