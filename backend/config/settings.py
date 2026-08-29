import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "users",
    "accounts",
    "storage",
    "files",
    "notifications",
    "sharing",
    "ai",
    "adminpanel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "driveon"),
        "USER": os.environ.get("POSTGRES_USER", "driveon"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "driveon"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "users.authentication.FirebaseAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
}

CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")

# Firebase Admin SDK service account JSON path, used to verify ID tokens
# issued to the frontend by Firebase Authentication.
FIREBASE_CREDENTIALS_PATH = os.environ.get("FIREBASE_CREDENTIALS_PATH", "")

# Google OAuth 2.0 client (Web application) used to connect user-owned
# Google Drive accounts. Never a service account -- see SOP section 46.
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get(
    "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/accounts/callback/google"
)
GOOGLE_OAUTH_SCOPES = ["https://www.googleapis.com/auth/drive"]

# Microsoft identity platform app registration (Azure AD, "Personal
# Microsoft accounts" supported) used to connect user-owned OneDrive
# accounts. Same trust posture as the Google client above -- never a
# service/app-only credential.
MICROSOFT_OAUTH_CLIENT_ID = os.environ.get("MICROSOFT_OAUTH_CLIENT_ID", "")
MICROSOFT_OAUTH_CLIENT_SECRET = os.environ.get("MICROSOFT_OAUTH_CLIENT_SECRET", "")
MICROSOFT_OAUTH_REDIRECT_URI = os.environ.get(
    "MICROSOFT_OAUTH_REDIRECT_URI", "http://localhost:8000/api/accounts/callback/microsoft"
)
MICROSOFT_OAUTH_SCOPES = ["Files.ReadWrite", "offline_access", "User.Read", "openid", "email"]

# Fernet key (generate with cryptography.fernet.Fernet.generate_key()) used
# to encrypt OAuth tokens at rest. Must never be committed.
TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY", "")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Server-side enforced plan limits (SOP section 68) -- never trust the
# frontend for these checks. One combined cap across every connected
# provider (Google + Microsoft), matching "one unified storage pool."
DEFAULT_MAX_CONNECTED_ACCOUNTS = int(os.environ.get("DEFAULT_MAX_CONNECTED_ACCOUNTS", "5"))
DEFAULT_MAX_FILE_SIZE_MB = int(os.environ.get("DEFAULT_MAX_FILE_SIZE_MB", "4096"))

# Notification emails. Falls back to printing to the Celery worker's
# stdout when EMAIL_HOST isn't set, so local/dev works with zero email
# configuration.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "driveON <noreply@driveon.local>")

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

# Upload streaming: files larger than this are spooled to a temp file on
# disk instead of held in memory (see SOP section 21).
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = None

# Distributed chunking engine: a file is split into fixed-size blocks
# striped across the user's connected accounts. 8MB matches the transfer
# chunk size accounts.clients.google_drive already uses for a single
# Drive resumable upload/download, so one logical block maps cleanly onto
# one Drive resumable session.
CHUNK_SIZE_BYTES = 8 * 1024 * 1024
CHUNK_UPLOAD_CONCURRENCY = 8
CHUNK_DOWNLOAD_CONCURRENCY = 4
# Written by the view, read by the Celery worker -- must be a path both
# containers can see. docker-compose.yml bind-mounts the same host
# directory into both the `backend` and `celery` services, so a path
# under BASE_DIR satisfies that without extra volume config.
CHUNK_UPLOAD_TMP_DIR = BASE_DIR / "tmp_uploads"

REBALANCE_IMBALANCE_THRESHOLD = 0.25
REBALANCE_MAX_CHUNKS_PER_RUN = 50

# console.anthropic.com/settings/keys -- powers AI summaries, multi-PDF
# chat, natural-language search, and auto-categorization (see the `ai`
# app). Views degrade to a clear 503 rather than crashing when unset.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "claude-opus-5")
# Raw-bytes cap, checked *before* reconstruction.stream_reconstructed runs
# (a live parallel fetch against Google Drive/OneDrive) -- base64 encoding
# inflates a file by ~4/3x, and Claude's document content block caps at
# 32MB on the request itself, so this keeps the encoded payload safely
# under that. Applies uniformly to both the summarize (inline base64) and
# chat (Files API) paths.
AI_MAX_DOCUMENT_SIZE_MB = int(os.environ.get("AI_MAX_DOCUMENT_SIZE_MB", "20"))
AI_CATEGORIZE_BATCH_SIZE = 75
