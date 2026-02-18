# users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Evaluador, Curso, Participante,Institucion,Constancia,EncuestaRespuesta

class EvaluadorCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Evaluador
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email', 'cargo', 'foto', 'firma_digital')

class ProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = Evaluador
        fields = ['foto']
        widgets = {
            'foto': forms.FileInput,
        }

class SignatureForm(forms.ModelForm):
    class Meta:
        model = Evaluador
        fields = ['firma_digital']
        widgets = {
            'firma_digital': forms.FileInput,
        }

class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['nombre']

class ParticipanteForm(forms.ModelForm):
    class Meta:
        model = Participante
        fields = ['nombre_completo', 'email', 'titulo', 'institucion']

class InstitucionForm(forms.ModelForm):
    class Meta:
        model = Institucion
        fields = ['nombre', 'ubicacion']

class LoteConstanciaForm(forms.Form):
    # Campo para seleccionar un solo curso
    curso = forms.ModelChoiceField(
        queryset=Curso.objects.all(),
        label="Selecciona el Curso"
    )
    # Campo para seleccionar MÚLTIPLES participantes
    participantes = forms.ModelMultipleChoiceField(
        queryset=Participante.objects.all(),
        widget=forms.CheckboxSelectMultiple, # Esto crea la lista de checkboxes
        label="Selecciona los Participantes"
    )
    # Campos de la sesión específica del curso
    fecha_inicio = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Fecha de Inicio del Evento")
    fecha_termino = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Fecha de Término del Evento")
    duracion_en_horas = forms.DecimalField(max_digits=4, decimal_places=1, label="Duración (Horas)")
    firma_especialista = forms.ModelChoiceField(
        queryset=Evaluador.objects.all(),
        label="Selecciona el Especialista que firma"
    )
class WebinarStep1Form(forms.Form):
    curso_nombre = forms.CharField(label="Nombre del Evento/Webinar")
    fecha_inicio = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Fecha de Inicio")
    fecha_termino = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Fecha de Término")
    duracion_en_horas = forms.DecimalField(max_digits=4, decimal_places=1, label="Duración (Horas)")
    firma_especialista = forms.ModelChoiceField(
        queryset=Evaluador.objects.all(),
        label="Especialista que firma"
    )
    archivo_csv = forms.FileField(label="Selecciona el archivo CSV de WebEx")

class EncuestaForm(forms.ModelForm):
    class Meta:
        model = EncuestaRespuesta
        # Definimos explícitamente solo los campos que queremos que el usuario llene
        fields = [
            'satisfaccion_general', 'evaluacion_general', 'aspectos_interesantes',
            'aspectos_no_gustaron', 'informacion_valiosa', 'organizacion',
            'duracion', 'recomendacion', 'temas_futuros', 'horario_preferido',
            'dia_preferido', 'comentarios_adicionales', 'interes_productos'
        ]
        # La sección de widgets no cambia y está correcta
        widgets = {
            'satisfaccion_general': forms.Textarea(attrs={'rows': 3}),
            'evaluacion_general': forms.Textarea(attrs={'rows': 3}),
            'aspectos_interesantes': forms.Textarea(attrs={'rows': 3}),
            'aspectos_no_gustaron': forms.Textarea(attrs={'rows': 3}),
            'informacion_valiosa': forms.Textarea(attrs={'rows': 3}),
            'organizacion': forms.RadioSelect,
            'duracion': forms.RadioSelect,
            'recomendacion': forms.RadioSelect,
            'horario_preferido': forms.RadioSelect,
            'dia_preferido': forms.RadioSelect,
            'comentarios_adicionales': forms.Textarea(attrs={'rows': 3}),
            'interes_productos': forms.CheckboxInput(attrs={'class': 'h-5 w-5'}),
        }