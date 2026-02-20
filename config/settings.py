import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# 1. Cargar variables de entorno
load_dotenv()

# 2. Directorios
BASE_DIR = Path(__file__).resolve().parent.parent

# 3. Seguridad y Entorno (Sincronizado con tus capturas de Vercel)
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-fallback')
ALLOWED_HOSTS = ['*']

# 4. Aplicaciones (Orden corregido para Cloudinary)
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',          # Debe ir antes de staticfiles
    'cloudinary',
    'users',
    'widget_tweaks',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Para servir estáticos en Vercel
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# 5. Base de Datos (Neon / DATABASE_URL)
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# 6. Configuración Regional
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

# 7. Archivos Estáticos (CSS, JS, Logos)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
# WhiteNoise para que Vercel encuentre los archivos

# 8. Archivos Media (Fotos/Firmas en Cloudinary)
# Esto evita el error "Read-only file system"
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

MEDIA_URL = '/media/'

# 9. Configuración de Usuarios
AUTH_USER_MODEL = 'users.Evaluador'
LOGIN_URL = 'users:login'
LOGOUT_REDIRECT_URL = 'users:login'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'