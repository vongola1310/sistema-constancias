import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv


# 1. Cargar variables de entorno (Lee el archivo .env si existe en tu PC)
load_dotenv()

# 2. Definición de directorios
BASE_DIR = Path(__file__).resolve().parent.parent

# 3. Detectar si estamos en Vercel o en Local
IS_VERCEL = 'VERCEL' in os.environ

# 4. Seguridad
# SECRET_KEY: Intenta leerla del .env, si no, usa una por defecto (solo para desarrollo)
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fallback-key-dev-only')

# DEBUG: 
# En Vercel (Producción) será False automáticamente.
# En tu PC será True.
DEBUG = not IS_VERCEL

ALLOWED_HOSTS = ['*']

# 5. Aplicaciones Instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # --- CLOUDINARY (El orden es CRÍTICO) ---
    'cloudinary_storage',  # Debe ir ANTES de staticfiles
    'cloudinary',
    
    # Debe ir DESPUÉS de staticfiles
    # ----------------------------------------

    'users',
    'widget_tweaks',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # <-- Motor de estáticos para Vercel
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
        'DIRS': [BASE_DIR / 'templates'],
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

# 6. Base de Datos Híbrida
# Vercel inyecta automáticamente la variable POSTGRES_URL
if IS_VERCEL:
   DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}
else:
    # En tu PC usamos la de siempre
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Validadores de contraseña
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Configuración Regional
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True


# 7. Archivos Estáticos (CSS, JS) - WhiteNoise
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') # Vercel guardará los estáticos aquí
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
# Le decimos a Django y Cloudinary que WhiteNoise manejará el diseño
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# 8. Archivos Media (Imágenes) - Cloudinary
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Configuración que lee tu .env o las variables de Vercel
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}

# Esto hace la magia: guarda las fotos en la nube
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configuración de Usuarios
AUTH_USER_MODEL = 'users.Evaluador'
LOGIN_URL = 'users:login'
LOGOUT_REDIRECT_URL = 'users:login'