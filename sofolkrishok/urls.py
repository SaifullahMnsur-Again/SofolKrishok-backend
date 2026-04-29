"""
SofolKrishok URL Configuration
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def api_root(request):
    """API root endpoint showing available services."""
    return Response({
        'message': 'SofolKrishok API',
        'version': 'v1',
        'description': 'Unified API for farming, AI, marketplace, consultation, and finance',
        'endpoints': {
            'auth': '/auth/',
            'farming': '/farming/',
            'ai': '/ai/',
            'marketplace': '/marketplace/',
            'consultation': '/consultation/',
            'finance': '/finance/',
            'docs': '/docs/',
            'admin': '/admin/',
        },
        'note': 'In production with reverse proxy, prepend /api to all routes (e.g., /api/auth/)'
    })

schema_view = get_schema_view(
    openapi.Info(
        title="SofolKrishok API",
        default_version='v1',
        description=(
            "Unified API docs for auth, farming, AI, marketplace, consultation, and finance modules.\n\n"
            "Authentication in Swagger:\n"
            "1. Call /auth/login/ to obtain access + refresh tokens.\n"
            "2. Click Authorize and set Bearer token as: Bearer <access_token>.\n"
            "3. For /auth/token/refresh/, send refresh token in request body as {\"refresh\": \"...\"}.\n\n"
            "Audience labels used in endpoint docs:\n"
            "- Audience: Farmer\n"
            "- Audience: Staff\n"
            "- Audience: Both"
        ),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('', api_root, name='api-root'),
    path('admin/', admin.site.urls),

    # API endpoints
    path('auth/', include('users.urls')),
    path('farming/', include('lms_farming.urls')),
    path('ai/', include('ai_engine.urls')),
    path('marketplace/', include('marketplace.urls')),
    path('consultation/', include('consultation.urls')),
    path('finance/', include('finance.urls')),

    # API documentation (reduced to only necessary endpoints)
    re_path(r'^schema\.json$', schema_view.without_ui(cache_timeout=0), name='api-schema-json'),
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api-schema-swagger-ui'),
]

if settings.DEBUG:
    # Serve both static and media files directly in debug mode
    # STATIC_URL = '/static/' in DEBUG, so register pattern for '/static/'
    urlpatterns += static('/static/', document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static('/media/', document_root=settings.MEDIA_ROOT)
