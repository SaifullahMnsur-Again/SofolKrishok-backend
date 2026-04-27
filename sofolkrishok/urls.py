"""
SofolKrishok URL Configuration
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="SofolKrishok API",
        default_version='v1',
        description="Unified API docs for auth, farming, AI, marketplace, consultation, and finance modules.",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
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
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
