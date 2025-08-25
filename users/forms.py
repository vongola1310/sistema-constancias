# users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Evaluador, Curso, Participante,Institucion,Constancia

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