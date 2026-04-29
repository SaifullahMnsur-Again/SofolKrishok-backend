from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('manage', views.UserManagementViewSet, basename='user-manage')
router.register('audit', views.AuditLogViewSet, basename='audit-logs')
router.register('notifications', views.NotificationViewSet, basename='notifications')

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.AuthTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', views.AuthTokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('avatar/', views.AvatarView.as_view(), name='avatar'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('users/', views.UserListView.as_view(), name='user-list'),
] + router.urls
