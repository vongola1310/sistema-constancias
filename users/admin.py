from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Evaluador, Curso, Participante, Constancia,Institucion,EncuestaRespuesta,LeadVenta

@admin.register(Evaluador)
class EvaluadorAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'es_gerente')
    fieldsets = UserAdmin.fieldsets + (
        ('Campos Personalizados', {'fields': ('cargo', 'foto', 'firma_digital', 'es_gerente')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Campos Personalizados', {'fields': ('cargo', 'foto', 'firma_digital', 'es_gerente')}),
    )

@admin.register(Institucion)
class InstitucionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion')
    search_fields = ('nombre', 'ubicacion')

@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    # La vista de Curso ahora es mucho más simple
    list_display = ('nombre',)
    search_fields = ('nombre',)
    # Ya no hay campos de fecha para filtrar aquí

@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'email', 'titulo','institucion')
    search_fields = ('nombre_completo', 'email','institucion')

@admin.register(Constancia)
class ConstanciaAdmin(admin.ModelAdmin):
    list_display = ('participante', 'curso', 'fecha_inicio', 'fecha_termino', 'fecha_emision')
    search_fields = ('participante__nombre_completo', 'curso__nombre')
    list_filter = ('fecha_emision', 'curso', 'firma_gerente', 'firma_especialista')
    readonly_fields = ('fecha_emision', 'codigo_verificacion','token_encuesta')
    
    def get_changeform_initial_data(self, request):
        try:
            gerente = Evaluador.objects.get(es_gerente=True)
            return {'firma_gerente': gerente}
        except Evaluador.DoesNotExist:
            return {}
        
@admin.register(EncuestaRespuesta)
class EncuestaRespuestaAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'email', 'fecha_respuesta', 'interes_productos')
    list_filter = ('interes_productos', 'fecha_respuesta')
    search_fields = ('nombre_completo', 'email', 'constancia__curso__nombre')
    # Hacemos todos los campos de solo lectura para evitar modificaciones accidentales
    readonly_fields = [f.name for f in EncuestaRespuesta._meta.fields]

    def has_add_permission(self, request):
        return False # No se pueden añadir respuestas manualmente

@admin.register(LeadVenta)
class LeadVentaAdmin(admin.ModelAdmin):
    list_display = ('get_participante_nombre', 'get_participante_email', 'get_curso_nombre', 'fecha_creacion')
    search_fields = ('participante__nombre_completo', 'participante__email', 'curso__nombre')
    list_filter = ('fecha_creacion', 'curso')
    readonly_fields = ('participante', 'curso', 'fecha_creacion')

    def has_add_permission(self, request):
        return False

    # Funciones para mostrar datos de los modelos relacionados
    @admin.display(description='Nombre del Participante')
    def get_participante_nombre(self, obj):
        return obj.participante.nombre_completo

    @admin.display(description='Email del Participante')
    def get_participante_email(self, obj):
        return obj.participante.email

    @admin.display(description='Curso de Interés')
    def get_curso_nombre(self, obj):
        return obj.curso.nombre