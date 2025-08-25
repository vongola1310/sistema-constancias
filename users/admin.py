from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Evaluador, Curso, Participante, Constancia,Institucion

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
    readonly_fields = ('fecha_emision', 'codigo_verificacion')
    
    def get_changeform_initial_data(self, request):
        try:
            gerente = Evaluador.objects.get(es_gerente=True)
            return {'firma_gerente': gerente}
        except Evaluador.DoesNotExist:
            return {}