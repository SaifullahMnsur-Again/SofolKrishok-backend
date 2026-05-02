"""
Django settings for SofolKrishok project.
"""

import os
import environ
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent  # /home/saifullah/final-project/april-15


def comma_separated_list(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(',') if item.strip()]

# Load environment variables
env = environ.Env(
    DEBUG=(bool, True),
)
# environ.Env.read_env(os.path.join(PROJECT_ROOT, '.env'))
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env.str('SECRET_KEY', default='django-insecure-change-me-in-production')


load_dotenv()

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', default='localhost,127.0.0.1,testserver').split(',')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year in seconds
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True 
    # ALLOWED_HOSTS.append('testserver')

# FORCE_SCRIPT_NAME: Reverse proxy handles /api/ path-based routing (not SCRIPT_NAME rewriting)
# Always keep as None so Django treats paths naturally
FORCE_SCRIPT_NAME = None

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_yasg',

    # Custom apps
    'users',
    'lms_farming',
    'ai_engine',
    'marketplace',
    'consultation',
    'finance',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sofolkrishok.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sofolkrishok.wsgi.application'

# Database
DB_ENGINE = env.str('DB_ENGINE', default='django.db.backends.sqlite3')
if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / env.str('DB_NAME', default='db.sqlite3'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': env.str('DB_NAME', default=''),
            'USER': env.str('DB_USER', default='postgres'),
            'PASSWORD': env.str('DB_PASSWORD', default=''),
            'HOST': env.str('DB_HOST', default='localhost'),
            'PORT': env.str('DB_PORT', default='5432'),
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'users.CustomUser'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# Static files
# DEBUG: Serve at /static/ (dev server, no reverse proxy)
# PRODUCTION: Serve at /api/static/ (reverse proxy routes /api/* to backend)
STATIC_URL = '/static/' if DEBUG else '/api/static/'

STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": str(BASE_DIR / 'media'),
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# STORAGES = {
#     'staticfiles': {
#         'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
#     },
# }

# Media files
# MEDIA_URL = 'media/'
MEDIA_URL = '/api/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# REST Framework
# ============================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ============================================
# JWT Configuration
# ============================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=2),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ============================================
# CORS Configuration
# ============================================
# FRONTEND_URL = env.str('FRONTEND_URL', default='http://localhost:5173')
# CORS_ALLOWED_ORIGINS = [
#     FRONTEND_URL,
#     'http://localhost:5173',
#     'http://localhost:5174',
#     'http://127.0.0.1:5173',
#     'http://127.0.0.1:5174',
# ]

CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')

# CORS_ALLOW_CREDENTIALS = True
# CSRF_TRUSTED_ORIGINS = comma_separated_list(
#     env.str(
#         'CSRF_TRUSTED_ORIGINS',
#         default=f'{FRONTEND_URL},http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174',
#     )
# )

# Security / proxy settings for hosted deployment
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# ============================================
# AI Model Configuration
# ============================================
# Models are uploaded and managed via admin dashboard
# No local model paths required

# Gemini AI
GEMINI_API_KEY = env.str('GEMINI_API_KEY', default='')
GEMINI_MODEL = env.str('GEMINI_MODEL', default='gemini-3.1-flash-lite-preview')
GEMINI_SECONDARY_MODEL = env.str('GEMINI_SECONDARY_MODEL', default='gemini-2.5-flash-lite-preview')
GEMINI_TERTIARY_MODEL = env.str('GEMINI_TERTIARY_MODEL', default='gemini-2.5-flash')

# ============================================
# Administrative UI Configuration
# ============================================
JAZZMIN_SETTINGS = {
    "site_title": "SofolKrishok Admin",
    "site_header": "SofolKrishok Admin",
    "site_brand": "SofolKrishok",
    "welcome_sign": "Welcome to the SofolKrishok Administrative Portal",
    "copyright": "SofolKrishok Bangladesh",
    "search_model": ["users.CustomUser"],
    "show_ui_builder": False,
    "topmenu_links": [
        {"name": "Home",  "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Site", "url": "/", "new_window": True},
    ],
    "icons": {
        "users.CustomUser": "fas fa-users",
        "lms_farming.LandParcel": "fas fa-map-marked-alt",
        "lms_farming.CropTrack": "fas fa-seedling",
        "ai_engine.ChatSession": "fas fa-comments",
        "ai_engine.AIModelUsageHistory": "fas fa-chart-line",
        "marketplace.Product": "fas fa-shopping-cart",
        "consultation.ConsultationSlot": "fas fa-stethoscope",
        "finance.Transaction": "fas fa-wallet",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
}

JAZZMIN_UI_TWEAKS = {
    "navbar": "navbar-dark",
    "theme": "pulse",
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_child_indent": True,
}

# Chat memory settings
CHAT_MAX_HISTORY_MESSAGES = 50  # Sliding window size
CHAT_SUMMARY_THRESHOLD = 40    # Summarize when history exceeds this

# ============================================
# External API Keys
# ============================================
OPENWEATHER_API_KEY = env.str('OPENWEATHER_API_KEY', default='')
WEATHER_FORECAST_DAYS = env.int('WEATHER_FORECAST_DAYS', default=5)
WHISPER_BN_MODEL_PATH = env.str(
    'WHISPER_BN_MODEL_PATH',
    default=str(PROJECT_ROOT / 'banglaspeech2text' / 'whisper-base-bn'),
)

# SSLCommerz
SSLCOMMERZ_STORE_ID = env.str('SSLCOMMERZ_STORE_ID', default='')
SSLCOMMERZ_STORE_PASSWORD = env.str('SSLCOMMERZ_STORE_PASSWORD', default='')
SSLCOMMERZ_SANDBOX = env.bool('SSLCOMMERZ_SANDBOX', default=True)

# ============================================
# Celery & Background Tasks
# ============================================
CELERY_BROKER_URL = env.str('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env.str('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# ============================================
# Swagger / OpenAPI UI Settings
# ============================================
SWAGGER_SETTINGS = {
    'TAGS_SORTER': 'alpha',
    'OPERATIONS_SORTER': 'alpha',
    'USE_SESSION_AUTH': False,
    'PERSIST_AUTH': True,
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'JWT access token. Format: Bearer <access_token>',
        },
        'RefreshToken': {
            'type': 'apiKey',
            'name': 'X-Refresh-Token',
            'in': 'header',
            'description': 'Optional helper for testing token refresh flows in Swagger UI. The refresh endpoint primarily accepts refresh token in request body.',
        },
    },
    'SECURITY_REQUIREMENTS': [
        {
            'Bearer': [],
        }
    ],
}

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


LOGIN_URL = '/api/admin/login/'
LOGIN_REDIRECT_URL = '/api/admin/'