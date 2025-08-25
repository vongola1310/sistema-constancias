# users/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


app_name = 'users'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    path('evaluadores/crear/', views.crear_evaluador_view, name='crear_evaluador'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('perfil/cambiar-foto/', views.change_photo_view, name='change_photo'),
    path('perfil/cambiar-firma/', views.change_signature_view, name='change_signature'),

    path('cursos/crear/', views.crear_curso_view, name='crear_curso'),

    path('participantes/crear/', views.crear_participante_view, name='crear_participante'),

    path('instituciones/crear/', views.crear_institucion_view, name='crear_institucion'),

    path('constancias/crear-lote/', views.crear_lote_constancias_view, name='crear_lote'),
    path('constancia/<int:pk>/pdf/', views.generar_pdf_constancia_view, name='generar_pdf'),

    path('historial/', views.historial_constancias_view, name='historial_constancias'),
]


     
    
