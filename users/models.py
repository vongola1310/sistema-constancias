# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class Evaluador(AbstractUser):
    # Asegúrate de que tu modelo tenga estos campos
    cargo = models.CharField(max_length=255, blank=True, verbose_name="Cargo o Puesto")
    foto = models.ImageField(upload_to='fotos/', null=True, blank=True, verbose_name="Foto de Perfil")
    firma_digital = models.ImageField(upload_to='firmas/', null=True, blank=True, verbose_name="Firma Digital (PNG)")
    es_gerente = models.BooleanField(default=False, verbose_name="¿Es el Gerente que firma por defecto?")

    def __str__(self):
        return self.get_full_name() or self.username

class Institucion(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Nombre de la Institución")
    ubicacion = models.CharField(max_length=255, blank=True, verbose_name="Ubicación (ej. Ciudad, Estado)")

    class Meta:
        verbose_name = "Institución"
        verbose_name_plural = "Instituciones"

    def __str__(self):
        return self.nombre

class Curso(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Curso")
    
    class Meta:
        verbose_name = "Definición de Curso"
        verbose_name_plural = "Definiciones de Cursos"

    def __str__(self):
        return self.nombre

class Participante(models.Model):
    OPCIONES_TITULO = [
        ('', 'Seleccionar Título...'),
        ('Lic.', 'Licenciado(a)'),
        ('Ing.', 'Ingeniero(a)'),
        ('Dr.', 'Doctor(a)'),
        ('Mtro.', 'Maestro(a)'),
        ('Q.F.B.', 'Químico Farmacéutico Biólogo'),
        ('Q.B.P.', 'Químico Bacteriólogo Parasitólogo'),
        ('Otro', 'Otro (sin título)'),
    ]
    nombre_completo = models.CharField(max_length=255)
    email = models.EmailField(unique=True, help_text="El correo debe ser único para cada participante.")

    titulo = models.CharField(
        max_length=50,
        choices=OPCIONES_TITULO, # Le asignamos la lista de opciones
        default='',
        blank=True,
        verbose_name="Título Profesional"
    )

    institucion = models.ForeignKey(
        Institucion, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Institución de Origen"
    )

    class Meta:
        verbose_name = "Participante"
        verbose_name_plural = "Participantes"

    def __str__(self):
        return self.nombre_completo

class Constancia(models.Model):

    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, verbose_name="Participante")
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, verbose_name="Curso")
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio del Evento")
    fecha_termino = models.DateField(verbose_name="Fecha de Término del Evento")
    duracion_en_horas = models.DecimalField(max_digits=4, decimal_places=1, verbose_name="Duración (Horas)")
    firma_gerente = models.ForeignKey(
        Evaluador,
        on_delete=models.PROTECT,
        related_name="constancias_como_gerente",
        verbose_name="Firma del Gerente"
    )
    firma_especialista = models.ForeignKey(
        Evaluador,
        on_delete=models.PROTECT,
        related_name="constancias_como_especialista",
        verbose_name="Firma del Especialista"
    )
    fecha_emision = models.DateField(auto_now_add=True, verbose_name="Fecha de Emisión")
    codigo_verificacion = models.CharField(max_length=20, unique=True, blank=True, verbose_name="Código de Verificación")
    es_webinar = models.BooleanField(default=False, verbose_name="¿Es de Webinar?")
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Vencimiento")
    token_encuesta = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)




    class Meta:
        verbose_name = "Constancia"
        verbose_name_plural = "Constancias"
        unique_together = ('participante', 'curso', 'fecha_inicio')

    def __str__(self):
        return f"Constancia para {self.participante} en el curso {self.curso}"
    
class EncuestaRespuesta(models.Model):
    constancia = models.OneToOneField(Constancia, on_delete=models.CASCADE, primary_key=True)

    # Preguntas 1 y 2
    nombre_completo = models.CharField(max_length=255, verbose_name="1. Ingresa tu nombre completo")
    email = models.EmailField(verbose_name="2. Correo electrónico")

    # Preguntas 3 y 4 (Abiertas)
    satisfaccion_general = models.TextField(verbose_name="3. En términos generales, ¿Qué grado de satisfacción experimentó con el seminario web?")
    evaluacion_general = models.TextField(verbose_name="4. En general, ¿Cómo evaluaría el seminario web?")

    # Preguntas 5, 6 y 7 (Abiertas)
    aspectos_interesantes = models.TextField(verbose_name="5. ¿Qué aspectos del seminario web le pareció más interesante?")
    aspectos_no_gustaron = models.TextField(verbose_name="6. ¿Qué aspectos del seminario web no le gustó?", blank=True)
    informacion_valiosa = models.TextField(verbose_name="7. ¿Cuál considera que es la información más significativa o valiosa que obtuvo?")

    # Pregunta 8 (Opciones)
    ORGANIZACION_CHOICES = [
        ('Extremadamente organizado', 'Extremadamente organizado'),
        ('Muy organizado', 'Muy organizado'),
        ('Algo organizado', 'Algo organizado'),
        ('No tan organizado', 'No tan organizado'),
        ('Nada organizado', 'Nada organizado'),
    ]
    organizacion = models.CharField(max_length=50, choices=ORGANIZACION_CHOICES, verbose_name="8. ¿Cómo calificaría el nivel de organización?")

    # Pregunta 9 (Opciones)
    DURACION_CHOICES = [
        ('Demasiada larga', 'Demasiada larga'),
        ('Muy larga', 'Muy larga'),
        ('Apenas lo justo', 'Apenas lo justo'),
        ('Muy corta', 'Muy corta'),
        ('Demasiada corta', 'Demasiada corta'),
    ]
    duracion = models.CharField(max_length=50, choices=DURACION_CHOICES, verbose_name="9. ¿Cómo considera la duración del seminario web?")

    # Pregunta 10 (Calificación numérica)
    recomendacion = models.IntegerField(
        verbose_name="10. En una escala del 1 al 10, ¿cuál es la probabilidad de que recomiende nuestros seminarios web?",
        choices=[(i, str(i)) for i in range(1, 11)]
    )

    # Pregunta 11 (Abierta)
    temas_futuros = models.TextField(verbose_name="11. ¿Qué temas le gustaría que se aborden en los seminarios web futuros?", blank=True)

    # Preguntas 12 y 13 (Opciones)
    HORARIO_CHOICES = [('Mañana', 'Mañana'), ('Tarde', 'Tarde'), ('Noche', 'Noche')]
    DIA_CHOICES = [('Lunes', 'Lunes'), ('Martes', 'Martes'), ('Miércoles', 'Miércoles'), ('Jueves', 'Jueves'), ('Viernes', 'Viernes')]
    horario_preferido = models.CharField(max_length=20, choices=HORARIO_CHOICES, verbose_name="12. ¿Cuál sería el horario más conveniente?")
    dia_preferido = models.CharField(max_length=20, choices=DIA_CHOICES, verbose_name="13. ¿Qué día de la semana considera más conveniente?")

    # Pregunta 14 (Abierta)
    comentarios_adicionales = models.TextField(verbose_name="14. ¿Desea compartir algún comentario o sugerencia adicional?", blank=True)

    # Pregunta de Lead
    interes_productos = models.BooleanField(
        verbose_name=" ¿Le interesaría recibir más información sobre los productos de EUROIMMUN?",
        default=False
    )
    
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Respuesta de {self.nombre_completo}"

class LeadVenta(models.Model):
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE)
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Evita que se cree el mismo lead dos veces
        unique_together = ('participante', 'curso')

    def __str__(self):
        return f"Lead: {self.participante.nombre_completo} (desde el curso {self.curso.nombre})"