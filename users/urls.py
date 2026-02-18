# users/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect # Importante

app_name = 'users'

urlpatterns = [
    path('', lambda request: redirect('users:dashboard'), name='index'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
   

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

    path('webinar/paso-1-subir/', views.webinar_paso1_subir_view, name='webinar_paso1'),
    path('webinar/paso-2-previsualizar/', views.webinar_paso2_previsualizar_view, name='webinar_paso2'),

    path('historial/borrar-seleccion/', views.borrar_constancias_view, name='borrar_constancias'),

    path('historial/descargar-seleccion/', views.descargar_constancias_zip_view, name='descargar_constancias_zip'),

    path('participante/<int:pk>/historial/', views.historial_participante_view, name='historial_participante'),

    path('participantes/', views.lista_participantes_view, name='lista_participantes'),
    
    path('participante/<int:pk>/editar/', views.editar_participante_view, name='editar_participante'),

    path('constancia/<int:pk>/enviar/', views.enviar_constancia_view, name='enviar_constancia'),

    path('encuesta/<uuid:token>/', views.encuesta_view, name='encuesta'),

    path('enviar-masivo/', views.enviar_constancias_masivo_view, name='enviar_masivo'),

    path('descargar/', views.buscador_constancias_publico, name='buscador_publico'),

    path('descargar-pdf/<int:pk>/', views.descargar_pdf_publico, name='descargar_pdf_publico'),
    

]


     
    
