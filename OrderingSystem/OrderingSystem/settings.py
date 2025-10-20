"""
Django settings for OrderingSystem project.
Modified for Render deployment with Daphne, Channels, and Redis.
"""

import os
import dj_database_url  
from pathlib import Path

# --------------------------------------------------
# Paths
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------
# Security
# --------------------------------------------------

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-fallback-key")

DEBUG = os.environ.get("DEBUG", "False").lower() in ["true", "1"]

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "orderingsystemsept16.onrender.com").split(",")

# CSRF Protection for HTTPS
CSRF_TRUSTED_ORIGINS = [
    'https://orderingsystemsept16.onrender.com',
]

# Add your local development origins if needed
if DEBUG:
    CSRF_TRUSTED_ORIGINS.extend([
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ])

# --------------------------------------------------
# Applications
# --------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'channels',

    # Local
    'MSMEOrderingWebApp.apps.MSMEOrderingWebAppConfig',
]

# --------------------------------------------------
# ASGI / Channels
# --------------------------------------------------
ASGI_APPLICATION = 'OrderingSystem.asgi.application'

REDIS_URL = os.environ.get("REDIS_URL", None)

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    # Fallback (for local dev)
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# --------------------------------------------------
# Middleware
# --------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',

    # Custom middleware (must be early)
    'MSMEOrderingWebApp.middleware.BusinessOwnerSetupMiddleware',
    'MSMEOrderingWebApp.middleware.EnsureMediaDirectoryMiddleware',

    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# --------------------------------------------------
# URLs / Templates
# --------------------------------------------------
ROOT_URLCONF = 'OrderingSystem.urls'

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

WSGI_APPLICATION = 'OrderingSystem.wsgi.application'

# --------------------------------------------------
# Database
# --------------------------------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True
    )
}

# --------------------------------------------------
# Password validation
# --------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --------------------------------------------------
# Internationalization
# --------------------------------------------------
LANGUAGE_CODE = 'en-us'

TIME_ZONE = os.environ.get("TIME_ZONE", "Asia/Manila")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------
# Static & Media Files
# --------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'MSMEOrderingWebApp/static')
]

MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media'

# --------------------------------------------------
# Default Primary Key
# --------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --------------------------------------------------
# Email Configuration
# --------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'tupclaboratory@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'hyub dnjs etuf syjd')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'tupclaboratory@gmail.com')

# Detect Render environment
IS_RENDER = os.environ.get('RENDER', False)

if IS_RENDER:
    # CRITICAL FOR RENDER
    SECURE_SSL_REDIRECT = False  # Render handles SSL
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    ALLOWED_HOSTS = ['orderingsystemsept16.onrender.com']
    DEBUG = False
else:
    # Local development
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '10.210.182.134']
    DEBUG = True

# These should be False for now
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# --------------------------------------------------
# Remove all upload and data size restrictions
# --------------------------------------------------
DATA_UPLOAD_MAX_MEMORY_SIZE = 209715200  # 200 * 1024 * 1024 bytes
FILE_UPLOAD_MAX_MEMORY_SIZE = 209715200

