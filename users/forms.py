# users/forms.py
from django import forms
from datetime import date
from decimal import Decimal
import re
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

class EditarConstanciaForm(forms.ModelForm):
    curso_nombre = forms.CharField(label="Nombre del curso o evento", max_length=255)
    fechas_evento = forms.CharField(
        label="Días de la capacitación",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '2026-09-08, 2026-09-10'}),
        help_text=(
            "Para indicar varios días, escribe las fechas como AAAA-MM-DD, separadas "
            "por comas o por saltos de línea. La primera y la última deben coincidir "
            "con las fechas de inicio y término. Si lo dejas vacío, el PDF mostrará "
            "la fecha de término."
        ),
    )
    duracion_en_horas = forms.DecimalField(
        label="Duración (horas)", max_digits=4, decimal_places=1,
        min_value=Decimal('0.1'),
        widget=forms.NumberInput(attrs={'step': '0.1'}),
    )

    class Meta:
        model = Constancia
        fields = [
            'curso_nombre', 'tipo', 'fecha_inicio', 'fecha_termino',
            'fechas_evento', 'duracion_en_horas', 'firma_gerente',
            'firma_especialista', 'fecha_vencimiento', 'codigo_verificacion',
        ]
        widgets = {
            campo: forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})
            for campo in ('fecha_inicio', 'fecha_termino', 'fecha_vencimiento')
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo_verificacion'].required = True
        if self.instance.pk:
            self.initial['curso_nombre'] = self.instance.curso.nombre
            self.initial['fechas_evento'] = '\n'.join(self.instance.fechas_evento or [])

    def clean_fechas_evento(self):
        texto = self.cleaned_data['fechas_evento']
        if not texto:
            return []
        try:
            fechas = sorted({
                date.fromisoformat(valor).isoformat()
                for valor in re.split(r'[,;\s]+', texto) if valor
            })
        except ValueError:
            raise forms.ValidationError(
                "Escribe fechas válidas con el formato AAAA-MM-DD, por ejemplo 2026-09-08."
            )
        if not fechas:
            raise forms.ValidationError("Escribe al menos una fecha o deja el campo vacío.")
        return fechas

    def clean(self):
        datos = super().clean()
        inicio = datos.get('fecha_inicio')
        termino = datos.get('fecha_termino')
        fechas = datos.get('fechas_evento')
        vencimiento = datos.get('fecha_vencimiento')
        if inicio and termino and termino < inicio:
            self.add_error('fecha_termino', "La fecha de término no puede ser anterior al inicio.")
        if fechas and inicio and termino:
            if fechas[0] != inicio.isoformat() or fechas[-1] != termino.isoformat():
                self.add_error(
                    'fechas_evento',
                    "La primera y la última fecha deben coincidir con el inicio y término del evento.",
                )
        if vencimiento and termino and vencimiento < termino:
            self.add_error('fecha_vencimiento', "El vencimiento no puede ser anterior al término del evento.")
        if inicio and datos.get('curso_nombre') and self.instance.participante_id:
            repetida = Constancia.objects.filter(
                participante_id=self.instance.participante_id,
                curso__nombre=datos['curso_nombre'],
                fecha_inicio=inicio,
            ).exclude(pk=self.instance.pk)
            if repetida.exists():
                raise forms.ValidationError(
                    "Este participante ya tiene una constancia para ese curso y fecha de inicio."
                )
        return datos

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
    archivo_csv = forms.FileField(
        label="Reporte de asistencia (Teams, WebEx, Zoom o Excel)"
    )
    archivo_padron = forms.FileField(
        required=False,
        label="Excel de inscritos (opcional, para recuperar correos faltantes)"
    )
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

class LibroCapacitacionesForm(forms.Form):
    archivo = forms.FileField(
        label="Libro de capacitaciones (.xlsx)",
        help_text=(
            "Cada hoja del Excel se detectará como una sesión distinta. "
            "Para varios días, incluye las columnas Día, Mes y Año al inicio "
            "de la hoja y debajo, por ejemplo: 8, 9, 10 | septiembre | 2026. "
            "También puedes escribir una fecha por fila, sin filas vacías entre fechas."
            " O bien: Fecha | 13,14 y 15 de septiembre del 2026."
        )
    )
    anio = forms.IntegerField(
        label="Año de las sesiones",
        initial=2026,
        min_value=2020,
        max_value=2100,
        help_text="Se usa cuando la fecha del Excel o el título no incluye el año."
    )
    calificacion_minima = forms.DecimalField(
        label="Calificación mínima para aprobar",
        initial=80,
        max_digits=5,
        decimal_places=1,
        min_value=0,
        max_value=100
    )
    firma_especialista = forms.ModelChoiceField(
        queryset=Evaluador.objects.all(),
        label="Especialista que firma"
    )

