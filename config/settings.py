from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'dev-only-branch-query-engine'
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']


INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'rest_framework',
    'query_engine',
    'assistant',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'query_engine' / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': []},
}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'UNAUTHENTICATED_USER': None,
}

BRANCH_ANALYTICS_FILE = BASE_DIR / 'data' / 'branch_analytics.xlsx'
BRANCH_ANALYTICS_SHEET = 'Sheet1'

# Local Speech-to-Text (faster-whisper) Configuration
import os
WHISPER_MODEL = os.environ.get('WHISPER_MODEL', 'small')
WHISPER_DEVICE = os.environ.get('WHISPER_DEVICE', 'auto')
WHISPER_COMPUTE_TYPE = os.environ.get('WHISPER_COMPUTE_TYPE', 'auto')
WHISPER_DOWNLOAD_ROOT = os.environ.get('WHISPER_DOWNLOAD_ROOT', None)
WHISPER_CPU_THREADS = int(os.environ.get('WHISPER_CPU_THREADS', 4))
WHISPER_BEAM_SIZE = int(os.environ.get('WHISPER_BEAM_SIZE', 1))
VOICE_DEBUG_MODE = os.environ.get('VOICE_DEBUG_MODE', 'True').lower() in ('true', '1', 'yes')

